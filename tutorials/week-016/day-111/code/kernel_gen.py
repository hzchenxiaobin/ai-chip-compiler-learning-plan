#!/usr/bin/env python3
"""D107 被测内核工厂：KernelConfig → 专用 Python 源码 → 函数（迷你 Lowering）。

bench.py 是测量协议；本文件只生产『被测对象』——tiled MatMul＋bias 的
纯 Python 内核。内核从一个 KernelConfig 生成：

    KernelConfig(tm, tn, tk, order="ikj", unroll=4)
                     ├─ tm/tn/tk：tile 三维（D94 的 Tiling，min 钳制接住边界）
                     ├─ order：  i/j/k 的循环顺序，外→内，6 种排列（D92）
                     └─ unroll：最内层循环展开份数（D96 的 U）

生成方式和 D85~96 的 Lowering 同构：配置 → 循环源码 → 可执行函数。
最内层是谁，就按谁做行提升（code motion）：
  j 最内层：hoist C[i] 行、A[i] 行、a=A[i][k]、B[k] 行 —— 全行访问（D97 的 reorder）
  k 最内层：hoist A[i] 行；B[k][j] 跨步访问（D97 的 baseline）
  i 最内层：hoist b=B[k][j] 标量；C[i][j]、A[i][k] 双跨步（最惨的一种）

正确性契约（与 D97 的 -ffp-contract=off 同一论据）：所有排列、tile、展开下，
每个 C[i][j] 都按 k 升序做一串 IEEE 双精度加法——累加序列逐位相同，
因此与参考实现逐位相等（正确性门用 bitwise == 比较，不是误差阈值）。

诚实的边界（README 5.2 会再讲）：这里的『性能』反映 CPython 字节码成本
（下标次数、加法、循环开销），不反映硬件缓存/向量化的收益——所以 U=8
在 C++ 里省循环开销（D96），在 CPython 里反而更慢。工具不假装它是硬件。

broken_no_tail() 故意去掉尾部循环——D96『跑得飞快、结果全错』内核的
Python 版，留给正确性门当靶子。
"""

from __future__ import annotations

import dataclasses

RNG = {"i": ("i0", "ihi"), "j": ("j0", "jhi"), "k": ("k0", "khi")}

TMPL = """def _kernel(A, B, C, M, N, K, TM, TN, TK):
    for i0 in range(0, M, TM):
        for j0 in range(0, N, TN):
            for k0 in range(0, K, TK):
                ihi = min(i0 + TM, M); jhi = min(j0 + TN, N); khi = min(k0 + TK, K)
{BODY}
"""


@dataclasses.dataclass(frozen=True)
class KernelConfig:
    """一个被测内核的完整身份（与 D106 的 KernelConfig 同构，去掉测不到的轴）。

    buffering/staging 不在今天的数据结构里：纯 Python 内核没有 DMA 缓冲，
    D102~103 的那根轴要等有真实内存系统的目标才测得出——测不到的轴
    不进配置，免得结果表里出现假装量过的列。
    """

    tm: int = 32
    tn: int = 32
    tk: int = 32
    order: str = "ijk"      # i/j/k 的排列，外→内，如 "ikj" 表示 j 最内层
    unroll: int = 1         # 最内层展开份数（D96 的 U）

    def __post_init__(self):
        if sorted(self.order) != ["i", "j", "k"]:
            raise ValueError(f"order 必须是 i/j/k 的排列，得到 {self.order!r}")
        for name in ("tm", "tn", "tk", "unroll"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} 必须 ≥ 1，得到 {getattr(self, name)}")

    @property
    def inner_dim(self) -> str:
        return self.order[-1]

    def describe(self) -> str:
        tile = (f"{self.tm}³" if self.tm == self.tn == self.tk
                else f"{self.tm}×{self.tn}×{self.tk}")
        return f"{tile} {self.order} U={self.unroll}"


# ---------------------------------------------------------------- 固定输入与参考实现


def make_inputs(M: int, N: int, K: int, seed: int = 42):
    """固定输入：同一 (M,N,K,seed) 永远生成同一份 A/B/bias（控制变量的地基）。

    A: M×K，B: K×N，取值 uniform(-1,1)；bias: N，取值 uniform(-0.5,0.5)。
    """
    import random
    rng = random.Random(seed)
    A = [[rng.uniform(-1.0, 1.0) for _ in range(K)] for _ in range(M)]
    B = [[rng.uniform(-1.0, 1.0) for _ in range(N)] for _ in range(K)]
    bias = [rng.uniform(-0.5, 0.5) for _ in range(N)]
    return A, B, bias


def alloc_c(bias, M: int, N: int):
    """C 初始化为 bias 行向量的 M 份拷贝（D87 输出初始化：bias 先占位）。"""
    return [[bias[j] for j in range(N)] for _ in range(M)]


def ref_matmul(A, B, bias, M: int, N: int, K: int):
    """参考实现：朴素三重循环，i 外 j 中 k 内，每个元素按 k 升序累加。

    它慢（没有 tile、没有行提升），但它只负责『对答案』，不进计时。
    """
    C = alloc_c(bias, M, N)
    for i in range(M):
        Ai = A[i]
        Ci = C[i]
        for j in range(N):
            c = Ci[j]
            for k in range(K):
                c += Ai[k] * B[k][j]
            Ci[j] = c
    return C


def max_abs_err(C, Cref) -> float:
    err = 0.0
    for row, rref in zip(C, Cref):
        for a, b in zip(row, rref):
            e = abs(a - b)
            if e > err:
                err = e
    return err


# ---------------------------------------------------------------- 源码生成


def _unroll(pad: int, lo: str, hi: str, U: int, stmt, with_tail: bool = True) -> list:
    """展开最内层：主循环步长 U、每步 U 条语句；剩余量走尾部循环（D96）。

    with_tail=False 时尾部循环整段不生成——『跑得飞快、结果全错』的
    no-tail 内核就是这么诞生的（D96 的教训，留给正确性门当靶子）。
    """
    n = f"({hi} - {lo})"
    p = " " * pad
    lines = [f"{p}n = {n} - {n} % {U}",
             f"{p}for v3 in range({lo}, {lo} + n, {U}):"]
    for u in range(U):
        idx = "v3" if u == 0 else f"v3 + {u}"
        lines.append(f"{p}    {stmt(idx)}")
    if with_tail:
        lines.append(f"{p}for v3 in range({lo} + n, {hi}):")
        lines.append(f"{p}    {stmt('v3')}")
    return lines


def _elem_loops(d1: str, d2: str, d3: str, U: int, pad: int, with_tail: bool = True) -> list:
    """生成元素级循环：v1 外、v2 中、v3（最内层，展开 U 份）。

    行提升按最内层是谁分三套——和 D92『顺序决定访问模式』一一对齐。
    """
    p = " " * pad
    p2 = " " * (pad + 4)
    p3 = " " * (pad + 8)
    lo1, hi1 = RNG[d1]
    lo2, hi2 = RNG[d2]
    lo3, hi3 = RNG[d3]
    lines = [f"{p}for v1 in range({lo1}, {hi1}):"]

    if d3 == "j":
        # C[i][j] += A[i][k] * B[k][j]：j 内层 → C/A/B 全部行访问
        if d1 == "i":
            lines.append(f"{p2}Ci = C[v1]; Ai = A[v1]")
            lines.append(f"{p2}for v2 in range({lo2}, {hi2}):")
            lines.append(f"{p3}a = Ai[v2]; Bv = B[v2]")
            stmt = lambda x: f"Ci[{x}] += a * Bv[{x}]"
        else:  # d1 == "k"
            lines.append(f"{p2}Bv = B[v1]")
            lines.append(f"{p2}for v2 in range({lo2}, {hi2}):")
            lines.append(f"{p3}Ci = C[v2]; a = A[v2][v1]")
            stmt = lambda x: f"Ci[{x}] += a * Bv[{x}]"
        lines += _unroll(pad + 8, lo3, hi3, U, stmt, with_tail)

    elif d3 == "k":
        # c += A[i][k] * B[k][j]：k 内层 → 标量累加器，B 跨步访问
        if d1 == "i":
            lines.append(f"{p2}Ai = A[v1]")
            lines.append(f"{p2}for v2 in range({lo2}, {hi2}):")
            lines.append(f"{p3}c = C[v1][v2]")
            stmt = lambda x: f"c += Ai[{x}] * B[{x}][v2]"
            tail = f"{p3}C[v1][v2] = c"
        else:  # d1 == "j"
            lines.append(f"{p2}for v2 in range({lo2}, {hi2}):")
            lines.append(f"{p3}Ai = A[v2]; c = C[v2][v1]")
            stmt = lambda x: f"c += Ai[{x}] * B[{x}][v1]"
            tail = f"{p3}C[v2][v1] = c"
        lines += _unroll(pad + 8, lo3, hi3, U, stmt, with_tail)
        lines.append(tail)

    else:  # d3 == "i"
        # C[i][j] += A[i][k] * b，b=B[k][j] 是标量；C、A 双跨步
        if d1 == "j":
            lines.append(f"{p2}for v2 in range({lo2}, {hi2}):")
            lines.append(f"{p3}b = B[v2][v1]")
            stmt = lambda x: f"C[{x}][v1] += A[{x}][v2] * b"
        else:  # d1 == "k"
            lines.append(f"{p2}for v2 in range({lo2}, {hi2}):")
            lines.append(f"{p3}b = B[v1][v2]")
            stmt = lambda x: f"C[{x}][v2] += A[{x}][v1] * b"
        lines += _unroll(pad + 8, lo3, hi3, U, stmt, with_tail)
    return lines


def kernel_source(cfg: KernelConfig, drop_tail: bool = False) -> str:
    """生成内核源码。drop_tail=True 时尾部循环整段不生成（故意做坏，给正确性门当靶子）。

    开发本文件时，模板缩进出过一次真 bug：元素循环掉到了 k0 循环外面，
    6 个配置全数 FAIL——第一时间拦住它的是正确性门，不是肉眼读代码。
    """
    d1, d2, d3 = cfg.order
    body = "\n".join(_elem_loops(d1, d2, d3, cfg.unroll, 16, with_tail=not drop_tail))
    return TMPL.replace("{BODY}", body)


def make_kernel(cfg: KernelConfig, drop_tail: bool = False):
    """配置 → 专用函数。exec 一次、缓存到 fn.src，供 show-src 直接打印。"""
    src = kernel_source(cfg, drop_tail=drop_tail)
    ns = {"min": min}
    exec(compile(src, f"<kernel:{cfg.describe()}>", "exec"), ns)
    fn = ns["_kernel"]

    def kernel(A, B, C, M, N, K, _fn=fn, _cfg=cfg):
        _fn(A, B, C, M, N, K, _cfg.tm, _cfg.tn, _cfg.tk)

    kernel.src = src
    kernel.cfg = cfg
    kernel.name = f"tiled-matmul/{cfg.describe()}" + ("/no-tail" if drop_tail else "")
    return kernel
