#!/usr/bin/env python3
"""transpose_lab.py —— 第 64 天主实验：Transpose 的语义。

任务（来自学习计划第 64 天）：
  学习：维度排列、物理数据移动和视图之间的差别；
  实践：定义或完善 mini.transpose，记录 Permutation 属性并验证其合法性；
  产出：Transpose Operation、Verifier 和测试（测试在 test_transpose.py）。

贯穿例子（延续第 63 天复盘的那份数据，值肉眼可核对）：
  逻辑张量 A(2,3) = [[1, 2, 3],        底层存储 S = [1, 2, 3, 4, 5, 6]
                     [4, 5, 6]]         行主序 strides (3, 1)
  三维放大 B(2,3,4) = arange(24)，strides (12, 4, 1)
  排列属性 permutation：
    mini 的约定（与 numpy、LLVM 18 linalg.transpose 一致，两侧均本机实测）：
      out_shape[i]   = in_shape[perm[i]]     （输出第 i 维拽输入第 perm[i] 维）
      视图版 out_strides[i] = in_strides[perm[i]]

mini.transpose 的三种命运（今天的核心区分）：
  命运① 视图   A.T            只改元信息：strides 重排，存储一字节不动，O(1)
  命运② 搬家   ascontiguousarray(A.T)  真实数据移动：存储重排，O(numel)
  命运③ 不落地 消费方交换下标  语义活在索引里（linalg 降级后的 load %a[%j, %i]）

Verifier 四关（检查顺序是设计决策，见段 6 的 linalg 反面教材）：
  E1 排列长度 == rank          E2 值域 0..rank-1
  E3 无重复（双射）            E4 结果形状逐维一致
  顺序必须 E1 → E2 → E3 → E4：E2 必须发生在「拿 perm[i] 去查 in_shape」之前。

用法：python3 transpose_lab.py   （在 code/ 目录下；输出另存 outputs/transpose_lab.txt）
"""

from __future__ import annotations

import platform
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))


def estrides(a: np.ndarray) -> tuple[int, ...]:
    """numpy 字节 stride → 元素 stride，与 MLIR strided<[...]> 同口径。"""
    return tuple(s // a.itemsize for s in a.strides)


def phys_offset(a: np.ndarray, idx) -> int:
    """逻辑下标落在自身底层缓冲的第几格（元素）——第 57 天的偏移公式。"""
    base = a.ctypes.data
    addr = base + sum(i * s for i, s in zip(idx, a.strides))
    return (addr - base) // a.itemsize


def linear_read_offsets(a: np.ndarray) -> list[int]:
    """按行主序从头读一遍，记录每个逻辑位置的物理偏移。"""
    return [phys_offset(a, idx) for idx in np.ndindex(*a.shape)]


# ============================================================
# mini.transpose 的核心语义（供 lab 与 test 共用）
# ============================================================

def infer_transposed_shape(shape, perm):
    """Shape 推导：out_shape[i] = in_shape[perm[i]。

    只做纯推导，不检查 perm 合法性——合法性由 verify_transpose 负责。
    调用方必须先通过 Verifier（E2 之前不许拿 perm[i] 索引 shape）。
    """
    return tuple(int(shape[p]) for p in perm)


def permute_strides(strides, perm):
    """视图配方：out_strides[i] = in_strides[perm[i]]。

    对任意合法排列，重排后的 strides 仍是合法仿射映射——
    这就是「转置永远可以视图化」的全部原因（与 reshape 的
    try_view 会失败形成对照，见第 59 天）。
    """
    return tuple(int(strides[p]) for p in perm)


def inverse_perm(perm):
    """逆排列 inv：inv[perm[i]] = i。转置两次 = 组合排列（Day 65 的入口）。"""
    inv = [0] * len(perm)
    for i, p in enumerate(perm):
        inv[p] = i
    return tuple(inv)


def perm_order(perm):
    """排列的阶：最少自乘几次回到恒等。对合(如 (1,0))阶为 2，
    3-循环(如 (1,2,0))阶为 3，恒等阶为 1。"""
    cur, k = tuple(perm), 1
    ident = tuple(range(len(perm)))
    while cur != ident:
        cur = tuple(cur[p] for p in perm)      # 组合一次
        k += 1
        if k > len(perm) + 1:                  # 防御：不该发生
            return -1
    return k


def verify_transpose(in_shape, perm, result_shape=None) -> list[str]:
    """mini.transpose Verifier：返回错误列表（空 = 合法）。

    四关顺序固定 E1→E2→E3→E4，E2 在任何 perm[i] 被用作下标之前。
    每条错误都写明「哪一关 / 期望 / 实际」——报错质量是 Verifier 的
    一部分（对照段 6 里 linalg 越界排列报出乱码维度的现场）。
    """
    errs: list[str] = []
    rank = len(in_shape)
    perm = tuple(int(p) for p in perm)

    # E1 长度
    if len(perm) != rank:
        errs.append(
            f"[E1] 排列长度 {len(perm)} 与输入秩 {rank} 不相等："
            f"permutation 必须给每一个输入维安排一个去处")
        return errs                     # 长度不对，后面无从查起

    # E2 值域（必须在用 perm[i] 索引 in_shape 之前！）
    for i, p in enumerate(perm):
        if not (0 <= p < rank):
            errs.append(
                f"[E2] 排列第 {i} 项 {p} 超出输入秩 {rank} 的合法范围 "
                f"0..{rank - 1}：拒绝，而不是拿它去查维度")
            return errs

    # E3 双射（无重复）
    if sorted(perm) != list(range(rank)):
        dup = sorted({p for p in perm if list(perm).count(p) > 1})
        errs.append(
            f"[E3] 排列 {list(perm)} 不是 {rank} 个维度的双射"
            f"（重复项 {dup}）：同一输入维不能被用两次")
        return errs

    # E4 结果形状逐维一致
    if result_shape is not None:
        result_shape = tuple(int(d) for d in result_shape)
        if len(result_shape) != rank:
            errs.append(
                f"[E4] 结果秩 {len(result_shape)} 与推导秩 {rank} 不相等")
        else:
            want = infer_transposed_shape(in_shape, perm)
            for i, (w, r) in enumerate(zip(want, result_shape)):
                if w != r:
                    errs.append(
                        f"[E4] 结果第 {i} 维应为 {w}（= 输入第 {perm[i]} 维），"
                        f"实际写的 {r}：约定 out_shape[i] = in_shape[perm[i]]")
    return errs


def ref_transpose(src: np.ndarray, perm) -> np.ndarray:
    """独立参考实现：不调 np.transpose，用下标算术直接搬值。

    注意方向：shape/strides 按 perm 拉（out_shape[i]=in_shape[perm[i]]），
    但「输出的下标元组 → 输入的下标元组」走的是逆排列：
      out[idx] = in[inv(idx)]，其中 in_idx[k] = idx[inv[k]]。
    2D 交换时 perm 是对合、perm == inv，两个方向重合——这正是
    3D 非对合排列最能暴露约定差异的原因（见段 5 的陷阱）。
    """
    inv = inverse_perm(perm)
    out_shape = infer_transposed_shape(src.shape, perm)
    out = np.empty(out_shape, dtype=src.dtype)
    for idx in np.ndindex(*out_shape):
        src_idx = tuple(idx[inv[k]] for k in range(len(perm)))
        out[idx] = src[src_idx]
    return out


@dataclass
class MiniTransposeOp:
    """mini.transpose Operation：一条 IR 文本 + 一个 Permutation 属性。

    文本形式（自定义可读格式，打印/解析往返一致）：
      %t = mini.transpose %in permutation = [1, 0] : (2x3xf32) -> (3x2xf32)
    """
    result_id: str                      # 结果值名，如 "%t"
    input_id: str                       # 输入值名，如 "%in"
    in_shape: tuple
    dtype: str = "f32"
    perm: tuple = ()
    result_shape: tuple | None = None   # None = 交给推导

    def __post_init__(self):
        self.in_shape = tuple(int(d) for d in self.in_shape)
        self.perm = tuple(int(p) for p in self.perm)
        if self.result_shape is None and verify_transpose(
                self.in_shape, self.perm, None) == []:
            self.result_shape = infer_transposed_shape(self.in_shape, self.perm)

    def verify(self) -> list[str]:
        return verify_transpose(self.in_shape, self.perm, self.result_shape)

    def print_ir(self) -> str:
        perm_s = "[" + ", ".join(str(p) for p in self.perm) + "]"
        in_t = "x".join(str(d) for d in self.in_shape) + "x" + self.dtype
        out_t = ("?" if self.result_shape is None
                 else "x".join(str(d) for d in self.result_shape)
                 + "x" + self.dtype)
        return (f"{self.result_id} = mini.transpose {self.input_id} "
                f"permutation = {perm_s} : ({in_t}) -> ({out_t})")


def parse_mini_transpose(line: str) -> MiniTransposeOp:
    """从一行 mini IR 文本解析出 MiniTransposeOp（打印→解析往返）。"""
    import re
    m = re.match(
        r"^(%\S+) = mini\.transpose (%\S+) permutation = \[([^\]]*)\] "
        r": \((\d+(?:x\d+)*)x([a-z]+\d+)\) "
        r"-> \((\?|\d+(?:x\d+)*)(?:x[a-z]+\d+)?\)$",
        line.strip())
    if m is None:
        raise ValueError(f"无法解析 mini.transpose 行: {line!r}")
    rid, iid, perm_s, in_s, dtype, out_s = m.groups()
    perm = tuple(int(p) for p in perm_s.replace(",", " ").split())
    in_shape = tuple(int(d) for d in in_s.split("x"))
    result_shape = None if out_s == "?" else tuple(
        int(d) for d in out_s.split("x"))
    return MiniTransposeOp(rid, iid, in_shape, dtype, perm, result_shape)


# ============================================================
# MLIR 侧：linalg.transpose 的真实裁决
# ============================================================

def find_mlir_opt() -> str | None:
    for cand in (shutil.which("mlir-opt"), "/usr/lib/llvm-18/bin/mlir-opt"):
        if cand and Path(cand).exists() and Path(cand).stat().st_mode & 0o111:
            return cand
    return None


def linalg_transpose_ir(in_t: str, out_t: str, perm: str) -> str:
    """构造一段只含 linalg.transpose 的 IR（类型与排列由调用方给定）。"""
    return f"""module {{
  func.func @transpose(%in: {in_t}, %out: {out_t}) {{
    linalg.transpose ins(%in: {in_t}) outs(%out: {out_t}) permutation = {perm}
    return
  }}
}}
"""


def mlir_verdict(ir_text: str) -> tuple[int, str]:
    """喂给 mlir-opt（parse + verify），返回 (退出码, 首行错误)。"""
    exe = find_mlir_opt()
    if exe is None:
        return -1, "mlir-opt 不可用"
    p = subprocess.run([exe, "-"], input=ir_text, capture_output=True, text=True)
    first = ""
    for ln in p.stderr.splitlines():
        if "error:" in ln:
            first = ln.split("error:", 1)[1].strip()
            break
    return p.returncode, first


# ============================================================
# 主实验
# ============================================================

def main() -> int:
    rng = random.Random(64)

    print("=" * 66)
    print("第 64 天主实验：Transpose 的语义（排列 / 视图 / 搬家）")
    print("=" * 66)

    print("\n== 0. 环境与主线 ==")
    print(f"python  {platform.python_version()}")
    print(f"numpy   {np.__version__}")
    print(f"arch    {platform.machine()}")
    mlir_opt = find_mlir_opt()
    if mlir_opt:
        ver = subprocess.run([mlir_opt, "--version"], capture_output=True,
                             text=True).stdout.splitlines()
        print(f"mlir-opt {mlir_opt}（{(ver or ['?'])[0]}）")
    else:
        print("mlir-opt 不可用")
    print("主线：一个 A(2,3) 的转置需求，三种命运（视图 / 搬家 / 不落地）；"
          "mini.transpose 的属性与四关 Verifier；与 linalg.transpose 实测对表。")

    # ---- 1. 三种命运的现场 ----
    print("\n== 1. 现场一：同一个转置需求，三种命运 ==")
    A = np.arange(1, 7, dtype=np.float32).reshape(2, 3)   # [[1,2,3],[4,5,6]]
    S = A.ravel()                                          # 底层存储 [1..6]

    V = A.T                                                # 命运① 视图
    C = np.ascontiguousarray(A.T)                          # 命运② 搬家

    print(f"A       shape {A.shape} strides {estrides(A)} 存储 {list(map(int, S))}")
    print(f"命运① V = A.T                shape {V.shape} strides {estrides(V)} "
          f"共享存储 {np.shares_memory(V, A)}")
    print(f"命运② C = ascontiguousarray  shape {C.shape} strides {estrides(C)} "
          f"共享存储 {np.shares_memory(C, A)} 存储 {list(map(int, C.ravel()))}")
    print("命运③ 不落地：消费方直接按交换下标读 A——A.T[0,1] 与 A[1,0] 是同一格：")
    print(f"        A.T[0,1] 的物理偏移 {phys_offset(V, (0, 1))}，"
          f"A[1,0] 的物理偏移 {phys_offset(A, (1, 0))}"
          f"（linalg 降级后的 load %a[%j, %i] 同款，见段 6）")
    print()

    print("读序偏移（按行主序从头读一遍，物理上走过的格子）：")
    print(f"  A（原样） : {linear_read_offsets(A)}   连续")
    print(f"  命运① V  : {linear_read_offsets(V)}   蹦着走——存储没动，账本换了")
    print(f"  命运② C  : {linear_read_offsets(C)}   规整——存储真的重排了")
    check("命运①视图：形状/值正确且与 A 共享存储",
          V.shape == (3, 2) and np.array_equal(V, A.T)
          and np.shares_memory(V, A))
    check("命运②搬家：值相同但存储独立、strides 规整",
          np.array_equal(C, V) and not np.shares_memory(C, A)
          and estrides(C) == (2, 1)
          and list(map(int, C.ravel())) == [1, 4, 2, 5, 3, 6])

    # 写穿联动：视图的「下游权利」之一
    V[0, 1] = 99.0
    check("写穿联动：V[0,1]=99 后 A[1,0] 同步变 99（视图共享存储）",
          A[1, 0] == 99.0 and V[0, 1] == 99.0)
    V[0, 1] = 4.0                                          # 恢复现场（V[0,1] 即 A[1,0]）
    check("恢复现场后 A 仍为 [[1,2,3],[4,5,6]]",
          np.array_equal(A, np.arange(1, 7, dtype=np.float32).reshape(2, 3)))

    # ---- 2. mini.transpose：属性、语义与 Verifier ----
    print("\n== 2. mini.transpose：Permutation 属性与四关 Verifier ==")
    op2d = MiniTransposeOp("%t", "%in", (2, 3), "f32", (1, 0))
    print(f"Operation（IR 文本）：{op2d.print_ir()}")
    print(f"属性 permutation = [1, 0]，秩 2，是双射，逆排列 = "
          f"{inverse_perm((1, 0))}，阶 = {perm_order((1, 0))}")
    print(f"推导：out_shape = in_shape[perm[i]] = "
          f"{infer_transposed_shape((2, 3), (1, 0))}")
    print(f"视图配方：out_strides = in_strides[perm[i]] = "
          f"{permute_strides((3, 1), (1, 0))}")
    print(f"Verifier 裁决：{op2d.verify() or '合法（0 条错误）'}")
    check("2D 转置 op：打印→解析往返一致",
          parse_mini_transpose(op2d.print_ir()) == op2d)
    check("2D 转置 op：Verifier 通过",
          op2d.verify() == [])

    print("\n四关各自的报错现场（检查顺序 E1→E2→E3→E4，值取自真实构造）：")
    bad_cases = [
        ("E1 长度", (2, 3), (0, 1, 2), (3, 2, 1),
         "排列比输入多一维"),
        ("E2 值域", (2, 3), (2, 0), (3, 2),
         "拿 2 去查 2 维输入的 shape——linalg 在这里读到乱码（段 6）"),
        ("E3 双射", (2, 3), (1, 1), (3, 3),
         "输入维 1 被用了两次，维 0 没了去处"),
        ("E4 形状", (2, 3), (1, 0), (2, 3),
         "排列合法，但结果类型写错（应为 3x2）"),
    ]
    for tag, sh, pm, rs, why in bad_cases:
        errs = verify_transpose(sh, pm, rs)
        shown = errs[0] if errs else "（未报错）"
        print(f"  {tag}: perm={list(pm)} result={list(rs)} ← {why}")
        print(f"        mini 报错: {shown}")
    check("四关全部命中且只报本关错误（E4 可报多个失配维）",
          all(verify_transpose(sh, pm, rs)
              and all(e.startswith(f"[{tag.split()[0]}]")
                      for e in verify_transpose(sh, pm, rs))
              for tag, sh, pm, rs, _ in bad_cases))

    print("\n恒等排列：合法但什么都没做（今天接受，明天 Day 65 的消除对象）：")
    ident = MiniTransposeOp("%t", "%in", (2, 3), "f32", (0, 1))
    print(f"  {ident.print_ir()}  → Verifier: {ident.verify() or '合法（no-op）'}")
    check("恒等排列合法（语义正确，收益问题留给 Canonicalizer）",
          ident.verify() == []
          and infer_transposed_shape((2, 3), (0, 1)) == (2, 3))

    # ---- 3. 判定表：mini 推导 vs numpy 实测 ----
    print("\n== 3. 判定表：mini 推导 vs numpy 实测 ==")
    B = np.arange(24, dtype=np.float32).reshape(2, 3, 4)   # 三维放大

    cases = [
        ("T1  2D 交换",       A, (1, 0)),
        ("T2  2D 恒等",       A, (0, 1)),
        ("T3  3D (1,2,0)",    B, (1, 2, 0)),
        ("T4  3D (2,0,1)",    B, (2, 0, 1)),
        ("T5  3D (2,1,0)",    B, (2, 1, 0)),
        ("T6  3D 只换后两维", B, (0, 2, 1)),
        ("T7  3D 只换前两维", B, (1, 0, 2)),
        ("T8  1D 恒等",       np.arange(5, dtype=np.float32), (0,)),
        ("T9  size-1 维",     np.ones((1, 3), dtype=np.float32), (1, 0)),
        ("T10 size-1 维反向", np.ones((3, 1), dtype=np.float32), (1, 0)),
        ("T11 转置再转置",    np.transpose(B, (1, 2, 0)), (2, 0, 1)),
        ("T12 先切片再转置",  np.arange(12, dtype=np.float32).reshape(3, 4)[:, :2],
         (1, 0)),
    ]
    print("用例              输入shape      perm       mini推导shape/strides"
          "            numpy实测shape/strides          对拍")
    all_ok = True
    for name, src, pm in cases:
        want_shape = infer_transposed_shape(src.shape, pm)
        want_st = permute_strides(estrides(src), pm)
        actual = np.transpose(src, pm)
        act_shape, act_st = actual.shape, estrides(actual)
        ok = (want_shape == act_shape and want_st == act_st
              and np.array_equal(actual, ref_transpose(src, pm))
              and np.shares_memory(actual, src))
        all_ok &= ok
        print(f"{name:<16} {str(src.shape):>12}  {str(pm):>9}   "
              f"{str(want_shape):>8}/{str(want_st):<12} "
              f"{str(act_shape):>8}/{str(act_st):<12} "
              f"{'ok' if ok else 'MISMATCH'}")
    check(f"判定表 {len(cases)}/{len(cases)}：shape、strides、值三方一致", all_ok)

    print("\n随机对拍（200 组随机张量 + 随机合法排列）：")
    rand_ok = 0
    for t in range(200):
        rank = rng.randint(1, 5)
        shape = tuple(rng.randint(1, 5) for _ in range(rank))
        pm = list(range(rank))
        rng.shuffle(pm)
        pm = tuple(pm)
        x = np.arange(int(np.prod(shape)), dtype=np.float32).reshape(shape)
        y = np.transpose(x, pm)
        if (infer_transposed_shape(shape, pm) == y.shape
                and permute_strides(estrides(x), pm) == estrides(y)
                and np.array_equal(y, ref_transpose(x, pm))
                and np.shares_memory(x, y)):
            rand_ok += 1
    check(f"随机对拍 {rand_ok}/200：推导 + 视图配方 + 独立参考 + 零拷贝全成立",
          rand_ok == 200)

    # ---- 4. 「转置永远可视图化」与搬家的代价 ----
    print("\n== 4. 视图的特权与搬家的代价 ==")
    print("与 reshape 的关键差别（第 59 天 try_view 会失败）：转置对任意合法排列")
    print("都能视图化——strides 重排后仍是合法仿射映射，不存在「装不下」的排列。")
    view_ok = 0
    for t in range(100):
        rank = rng.randint(2, 5)
        shape = tuple(rng.randint(1, 4) for _ in range(rank))
        pm = list(range(rank))
        rng.shuffle(pm)
        x = np.arange(int(np.prod(shape)), dtype=np.float32).reshape(shape)
        if np.shares_memory(np.transpose(x, tuple(pm)), x):
            view_ok += 1
    check(f"100 组随机转置全部零拷贝（视图特权）", view_ok == 100)

    print("\n搬家代价（2048x2048 f32 = 16 MiB，best-of-20 真实计时）：")

    def best_of(fn, repeat=20):
        ts = []
        for _ in range(repeat):
            t0 = time.perf_counter()
            fn()
            ts.append(time.perf_counter() - t0)
        return min(ts)

    big = np.ascontiguousarray(
        np.arange(2048 * 2048, dtype=np.float32).reshape(2048, 2048))
    bigT = big.T
    t_view = best_of(lambda: big.T)
    t_copy = best_of(lambda: np.ascontiguousarray(bigT))
    print(f"  big.T                     （视图，改账本）: {t_view*1e6:9.2f} µs/次")
    print(f"  ascontiguousarray(big.T)  （搬家，重排字节）: {t_copy*1e3:9.3f} ms/次")
    print(f"  差距约 {t_copy/t_view:.0f} 倍——同一个『转置』需求，"
          f"视图是 O(1) 元信息操作，搬家是 O(numel) 数据搬运")
    check("视图与搬家差 3 个数量级以上且语义各自正确",
          t_copy > 1000 * t_view
          and np.shares_memory(big.T, big)
          and np.array_equal(np.ascontiguousarray(bigT), bigT))

    # ---- 5. 排列的三条性质（为 Day 65 铺垫，只测不优化）----
    print("\n== 5. 排列的性质：恒等 / 对合 / 循环（Day 65 的原料） ==")
    props = [
        ("恒等 (0,1)", (0, 1), 1),
        ("对合 (1,0)（转两次=恒等）", (1, 0), 2),
        ("3-循环 (1,2,0)（转三次=恒等）", (1, 2, 0), 3),
        ("3-循环 (2,0,1)", (2, 0, 1), 3),
        ("4-循环 (1,2,3,0)", (1, 2, 3, 0), 4),
    ]
    for name, pm, order in props:
        inv = inverse_perm(pm)
        shape = (4, 3, 2, 5)[:len(pm)]
        x = np.arange(int(np.prod(shape)), dtype=np.float32).reshape(shape)
        twice = np.transpose(np.transpose(x, pm), inv)
        print(f"  {name:<28} 逆排列 {inv}  阶 {perm_order(pm)}")
        check(f"性质 {name}: 阶 = {order}，排列+逆排列复合回原样",
              perm_order(pm) == order and np.array_equal(twice, x))

    print("\n非对合排列的陷阱（为什么约定必须写进报错）：")
    b_perm = (1, 2, 0)          # 2x3x4 -> 3x4x2
    b_inv = inverse_perm(b_perm)
    print(f"  B(2,3,4) 经 perm {b_perm} → {infer_transposed_shape((2,3,4), b_perm)}；")
    print(f"  再做一次同款转置 ≠ 回到 B：3x4x2 经 {b_perm} → "
          f"{infer_transposed_shape((3,4,2), b_perm)}（是 (2,3,4) 的另一个循环）")
    print(f"  必须用逆排列 {b_inv} 才能回去：3x4x2 经 {b_inv} → "
          f"{infer_transposed_shape((3,4,2), b_inv)}")
    y1 = np.transpose(np.transpose(B, b_perm), b_perm)
    y2 = np.transpose(np.transpose(B, b_perm), b_inv)
    check("转两次(非对合)≠原样、转『排列+逆排列』=原样",
          not np.array_equal(y1, B) and np.array_equal(y2, B))

    # ---- 6. MLIR 对照：linalg.transpose 真实裁决 ----
    print("\n== 6. MLIR 对照：linalg.transpose 的真实裁决（本机 LLVM 18.1.8） ==")
    mlir_cases = [
        ("M1 合法 2D", "memref<2x3xf32>", "memref<3x2xf32>", "[1, 0]", 0),
        ("M2 约定A 4x2x3", "memref<2x3x4xf32>", "memref<4x2x3xf32>", "[2, 0, 1]", 0),
        ("M3 约定B 3x4x2", "memref<2x3x4xf32>", "memref<3x4x2xf32>", "[2, 0, 1]", 1),
        ("M4 E1 长度", "memref<2x3xf32>", "memref<3x2xf32>", "[0, 1, 2]", 1),
        ("M5 E3 双射", "memref<2x3xf32>", "memref<3x3xf32>", "[1, 1]", 1),
        ("M6 E2 值域", "memref<2x3xf32>", "memref<3x2xf32>", "[2, 0]", 1),
        ("M7 E4 形状", "memref<2x3xf32>", "memref<2x3xf32>", "[1, 0]", 1),
        ("M8 恒等合法", "memref<2x3xf32>", "memref<2x3xf32>", "[0, 1]", 0),
    ]
    verdicts = []
    for name, in_t, out_t, pm, expect in mlir_cases:
        code, msg = mlir_verdict(linalg_transpose_ir(in_t, out_t, pm))
        verdicts.append((name, code, msg))
        fit = "符合预期" if code == expect else "!!不符合预期"
        print(f"  {name:<14} {in_t:<18} → {out_t:<18} perm {pm:<11}"
              f" exit={code}（预期 {expect}，{fit}）")
        if msg:
            print(f"        报错: {msg[:96]}")
    check("8 个 MLIR 案例的退出码与预期完全一致",
          all(c == e for (_, c, _), (_, _, _, _, e) in zip(verdicts, mlir_cases)))

    print("\n约定钉死（M2 vs M3，只差输出类型的维序）：")
    print("  in 2x3x4, perm [2,0,1] → out 4x2x3 合法（exit=0）；3x4x2 被拒（exit=1）")
    print("  → linalg.transpose 与 numpy 同款约定 out_shape[i] = in_shape[perm[i]]，")
    print("    且 M3 的报错原文直接把约定写在错误里：")
    print("    \"dim(result, 0) = 3 doesn't match dim(input, permutation[0]) = 4\"")

    print("\n报错质量现场（M6 越界排列，连跑两次观察乱码是否稳定）：")
    c1, m1 = mlir_verdict(linalg_transpose_ir(
        "memref<2x3xf32>", "memref<3x2xf32>", "[2, 0]"))
    c2, m2 = mlir_verdict(linalg_transpose_ir(
        "memref<2x3xf32>", "memref<3x2xf32>", "[2, 0]"))
    print(f"  第一次: exit={c1}\n    {m1}")
    print(f"  第二次: exit={c2}\n    {m2}")
    print("  两次的『维度』数字不同——排列里的 2 越界后，诊断路径先拿它去查")
    print("  shape，读到未定义值再打印。操作仍被拒绝（exit=1），但报错信息")
    print("  失去了诊断价值。mini 的 E2 关就是为此而生：先查值域，再允许索引。")
    check("越界排列被拒绝且两次报错读到不同的乱码值（值域检查缺失的证据）",
          c1 == 1 and c2 == 1 and m1 != m2)

    # 循环降级：搬家的代码形态
    print("\n命运③的代码形态（linalg.transpose --convert-linalg-to-loops）：")
    if mlir_opt:
        ir2d = linalg_transpose_ir("memref<2x3xf32>", "memref<3x2xf32>", "[1, 0]")
        p = subprocess.run([mlir_opt, "--convert-linalg-to-loops", "-"],
                           input=ir2d, capture_output=True, text=True)
        if p.returncode == 0:
            (OUT / "transpose_2d.loops.mlir").write_text(
                p.stdout, encoding="utf-8")
            for ln in p.stdout.splitlines():
                if "load" in ln or "store" in ln or "scf.for" in ln:
                    print(f"    {ln.strip()}")
            print("  （完整输出存 outputs/transpose_2d.loops.mlir）")
            check("降级循环里 load 的下标是交换的（%arg3, %arg2）",
                  "load %arg0[%arg3, %arg2]" in p.stdout)
        else:
            print(f"  降级失败: {p.stderr[:120]}")
            check("循环降级", False)
    else:
        print("  mlir-opt 不可用，跳过")
        check("循环降级", False, "mlir-opt 不可用")

    # ---- 汇总 ----
    print()
    print("=" * 66)
    print(f"汇总：PASS {PASS} / FAIL {FAIL}")
    print("=" * 66)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
