#!/usr/bin/env python3
"""D110 简单 Cost Model：不跑内核，给候选排序。

一句话：把 kernel_gen.py 生成的循环结构『读』成一个语句执行次数表，
再乘上十几根校准过的语句单价，得到每个候选的预测毫秒——
36 个候选的排名在毫秒级算完，实测只留给前几名。

三层结构（对应 README 第 4 节的图 2）：
  ① 静态计数器 count_ops()：候选 (M,N,K,tm,tn,tk,order,U) → 每类语句执行多少次。
     逐行镜像 kernel_gen.py 的生成规则：tile 外壳 → v1/v2 行提升 → v3 主循环+尾部。
     计数单位是『源码行』：kernel_gen 把成对的行提升写在同一行
     （Ci = C[v1]; Ai = A[v1]），一行一次执行、一个单价。
  ② 校准 calibrate()：16 根语句行单价，全部来自微基准（函数局部变量＋真实
     float 列表，镜像内核内层写法——D109 探针 A 的教训：全局变量会量歪）。
  ③ 预测 predict_ms()：t_pred = Σ 次数 × 单价。另有流量项（元素访问 × 4B ÷
     D109 探针 B 的 Python 级带宽）与 Roofline 下界（flops ÷ D109 探针 A 的
     解释屋顶）——两者都不参与排序，用来展示模型自己的『瓶颈判定』。

真值校验（--exp verify）：小 shape 上用 sys.settrace 逐行数执行次数，
与静态计数器逐项对账——计数器若数错，后面的单价再准也是白搭。

诚实的边界：模型看得见语句行数，看不见 CPython 3.11 自适应特化的全部细节
（同一条语句在不同上下文里的单价会漂移）。所以模型负责把 36 个砍到 5 个，
冠军仍然由实测决定——精度报告（--exp accuracy）里每一处错误排序都是证据。

用法：
  python3 cost_model.py --exp calibrate   # 校准 16 根单价 → outputs/calibration.txt
  python3 cost_model.py --exp verify      # settrace 真值 vs 静态计数器（小 shape）
  python3 cost_model.py --exp rank        # 三 shape 全候选模型排序 → outputs/model-table.txt
  python3 cost_model.py --exp accuracy    # 对照 D108 实测：ρ / recall@K / 误差 → outputs/accuracy.txt
  python3 cost_model.py --exp self-test   # 断言自检
  python3 cost_model.py --exp env         # 环境记录
"""

from __future__ import annotations

import dataclasses
import gc
import itertools
import json
import os
import re
import statistics
import sys
import time

from kernel_gen import KernelConfig, kernel_source, make_inputs, make_kernel

BAR = "=" * 78
HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(HERE, "inputs")
OUTPUTS = os.path.join(HERE, "outputs")

# 输入血统（D109 立的规矩：哈希钉死，不过就拒绝分析）
RESULTS_PATH = os.path.join(INPUTS, "results-d108.jsonl")
RESULTS_SHA = "e8c8daa36e55da1e81e1dd797a537a6848c292851bb612093a6cf271de31037f"
PROBES_PATH = os.path.join(INPUTS, "probes-d109.json")
PROBES_SHA = "cf8bc8316dfb7784f21bfdd913cef47f21dd461488e56726eb7e00f28e91827d"

# 与 D108 tune.py 同构的搜索空间（重新实现 + 用 D108 记录数对账，见 self-test）
SHAPES = (
    ("S1", 64, 64, 64),
    ("S2", 96, 96, 96),
    ("S3", 90, 96, 64),
)
CUBE_TILES = (32, 64)
UNROLLS = (1, 4)
ORDERS = tuple("".join(p) for p in itertools.permutations("ijk"))
DEFAULT_CFG = KernelConfig(32, 32, 32, "ijk", 1)


# ---------------------------------------------------------------- 搜索空间（对账 D108）

def build_space(shape_id, M, N, K):
    """与 D108 tune.build_space 相同的正确候选空间。"""
    tiles = [t for t in CUBE_TILES if t <= min(M, N, K)]
    if (M, N, K) not in [(t, t, t) for t in tiles]:
        tiles.append((M, N, K))
    cands = []
    for t in tiles:
        tm, tn, tk = (t, t, t) if isinstance(t, int) else t
        for order in ORDERS:
            for u in UNROLLS:
                cands.append(KernelConfig(tm, tn, tk, order, u))
    return cands


# ---------------------------------------------------------------- ① 静态计数器

@dataclasses.dataclass
class OpCounts:
    """一个候选的语句执行次数表——count_ops 的产物、predict 的输入。

    计数单位是『源码行』（CPython 行事件的粒度，也是校准的粒度）。

    预测用字段（单价见 Costs）：
      j0/ju k0/ku i0/iu ：内层语句（最内层分别是 j/k/i；下标 v3 朴素 / v3+u
                          展开版多两次下标加法，单价不同；j0 含尾部朴素语句）
      hs1/hs2/hsm/hd1   ：行提升行——单下标 / 两个单下标 / 单＋双下标 / 双下标
      s2                ：k 家族尾部写回行（C[v1][v2] = c）
      loop/range2/range3：循环机器（每次迭代 / 二参、三参 range 的每次建立）
      pre/min3          ：展开前奏行 / tile 外壳三连 min 行
    校验用字段（settrace 对账专用，不进预测）：
      it_i0/it_j0/it_k0 ：tile 三重循环的总迭代数（it_k0 = tile 数）
      it_v1/it_v2       ：元素级外层/中层循环的总迭代数（it_v2 = v2 体执行数）
      it_main/it_tail   ：v3 主循环/尾部循环的总迭代数
      inner0_main/tail  ：主循环里 u=0 语句 / 尾部朴素语句的次数
    """
    j0: int = 0
    ju: int = 0
    k0: int = 0
    ku: int = 0
    i0: int = 0
    iu: int = 0
    hs1: int = 0
    hs2: int = 0
    hsm: int = 0
    hd1: int = 0
    s2: int = 0
    loop: int = 0
    range2: int = 0
    range3: int = 0
    pre: int = 0
    min3: int = 0
    it_i0: int = 0
    it_j0: int = 0
    it_k0: int = 0
    it_v1: int = 0
    it_v2: int = 0
    it_main: int = 0
    it_tail: int = 0
    inner0_main: int = 0
    inner0_tail: int = 0
    elem_access: int = 0

    def total_stmts(self) -> int:
        return self.j0 + self.ju + self.k0 + self.ku + self.i0 + self.iu \
            + self.hs1 + self.hs2 + self.hsm + self.hd1 + self.s2

    def inner_plain(self) -> int:
        return self.j0 + self.k0 + self.i0

    def inner_plus(self) -> int:
        return self.ju + self.ku + self.iu


# 各家族的行提升行数：键 = (最内层, 最外层)；值 = (v1 体行, v2 体行)，按行计。
# 行的种类：hs1=单下标行；hs2=两个单下标（一行两句）；hsm=单＋双下标（一行两句）；
#           hd1=双下标行。与 kernel_gen._elem_loops 的六种分支一一对应；
#           k 家族（ijk/jik）另有 v2 体尾部写回行 s2。
HOISTS = {
    ("j", "i"): ("hs2", "hs2"),   # ikj: Ci=C[v1];Ai=A[v1] / a=Ai[v2];Bv=B[v2]
    ("j", "k"): ("hs1", "hsm"),   # kij: Bv=B[v1] / Ci=C[v2];a=A[v2][v1]
    ("k", "i"): ("hs1", "hd1"),   # ijk: Ai=A[v1] / c=C[v1][v2] ＋ 尾部写回
    ("k", "j"): (None, "hsm"),    # jik: （无）/ Ai=A[v2];c=C[v2][v1] ＋ 尾部写回
    ("i", "j"): (None, "hd1"),    # jki: （无）/ b=B[v2][v1]
    ("i", "k"): (None, "hd1"),    # kji: （无）/ b=B[v1][v2]
}


def _tile_extents(M, N, K, TM, TN, TK):
    """逐 tile 的真实工作量：边界 tile 被 min() 钳制（S3 的 M=90 就靠它）。"""
    for i0 in range(0, M, TM):
        for j0 in range(0, N, TN):
            for k0 in range(0, K, TK):
                yield (min(i0 + TM, M) - i0, min(j0 + TN, N) - j0,
                       min(k0 + TK, K) - k0)


def count_ops(M: int, N: int, K: int, cfg: KernelConfig) -> OpCounts:
    """静态计数：镜像 kernel_gen.py 的生成结构，一行不漏地数执行次数。"""
    c = OpCounts()
    TM, TN, TK, U = cfg.tm, cfg.tn, cfg.tk, cfg.unroll
    d1, d2, d3 = cfg.order

    c.it_i0 = (M + TM - 1) // TM
    c.it_j0 = c.it_i0 * ((N + TN - 1) // TN)
    c.it_k0 = c.it_j0 * ((K + TK - 1) // TK)
    c.min3 = c.it_k0
    v1_line, v2_line = HOISTS[(d3, d1)]

    for mi, njt, kk in _tile_extents(M, N, K, TM, TN, TK):
        e = {"i": mi, "j": njt, "k": kk}
        it1, it2, it3 = e[d1], e[d2], e[d3]

        # v1 循环（2 参 range）建立 1 次、迭代 it1 次；每个 v1 体里建一个 v2 循环
        c.it_v1 += it1
        c.it_v2 += it1 * it2
        if v1_line:
            setattr(c, v1_line, getattr(c, v1_line) + it1)
        setattr(c, v2_line, getattr(c, v2_line) + it1 * it2)
        if d3 == "k":                       # k 内层家族：v2 体尾部写回累加器
            c.s2 += it1 * it2

        # 每个 v2 体：前奏行 + 主循环（3 参）+ 尾部循环（2 参，空也要建）
        n_main = it3 // U
        n_tail = it3 - n_main * U
        c.pre += it1 * it2
        c.it_main += n_main * it1 * it2
        c.it_tail += n_tail * it1 * it2

        # 内层语句：主循环每组 U 条（第 1 条朴素、其余 U-1 条带 +u 下标），尾部朴素
        c.inner0_main += n_main * it1 * it2
        c.inner0_tail += n_tail * it1 * it2
        plain = (n_main + n_tail) * it1 * it2
        plus = (U - 1) * n_main * it1 * it2
        if d3 == "j":
            c.j0 += plain
            c.ju += plus
        elif d3 == "k":
            c.k0 += plain
            c.ku += plus
        else:
            c.i0 += plain
            c.iu += plus

    # 循环机器：tile 三重循环 + v1/v2 + v3 主/尾
    c.loop = c.it_i0 + c.it_j0 + c.it_k0 + c.it_v1 + c.it_v2 + c.it_main + c.it_tail
    # range 建立：i0 一次；j0 每 i0 一次；k0 每 (i0,j0) 一次；主循环每 v2 体一次（3 参）；
    # v1 每 tile 一次、v2 每 v1 一次、尾部每 v2 体一次（2 参）
    c.range3 = 1 + c.it_i0 + c.it_j0 + c.it_v2
    c.range2 = c.it_k0 + c.it_v1 + c.it_v2

    # 流量项（不进时间模型）：叶子元素访问次数，×4B 按 D109 名义口径折算。
    #   j 语句：C 读+写、B 读 = 3；k 语句：A 读、B 读 = 2（写走 s2）；
    #   i 语句：C 读+写、A 读 = 3；行提升行里只有 hsm/hd1 摸叶子（各 1 次）
    c.elem_access = 3 * (c.j0 + c.ju) + 2 * (c.k0 + c.ku) \
        + 3 * (c.i0 + c.iu) + c.hsm + c.hd1 + c.s2
    return c


# ---------------------------------------------------------------- ② 校准：14 根语句行单价

@dataclasses.dataclass
class Costs:
    """微基准量出的语句行单价（ns/行）。全部函数局部变量＋真实 float 列表。"""
    j0: float = 0.0
    ju: float = 0.0
    k0: float = 0.0
    ku: float = 0.0
    i0: float = 0.0
    iu: float = 0.0
    hs1: float = 0.0
    hs2: float = 0.0
    hsm: float = 0.0
    hd1: float = 0.0
    s2: float = 0.0
    loop: float = 0.0
    range2: float = 0.0
    range3: float = 0.0
    pre: float = 0.0
    min3: float = 0.0
    wall_ms: float = 0.0


def _t_med(fn, n, reps=5, warmup=2):
    """微基准的中位总耗时（秒）。预热让 3.11 自适应特化到位再计时。"""
    for _ in range(warmup):
        fn(n)
    xs = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn(n)
        xs.append(time.perf_counter() - t0)
    return statistics.median(xs)


_SLOPE_SIZES = (32, 64, 96)              # 三尺寸最小二乘斜率：抹掉循环建立摊销，
                                         # 数据 ≤ 80KB 镜像内核真实工作集（S2=73KB）


def _slope_ns(f, n, reps=7):
    """语句行单价 = 三个内层尺寸的最小二乘耗时斜率（ns/行）。

    为什么用斜率而不是单个尺寸直接除：单尺寸会把 range 建立成本摊进每行
    （模型已单独计了 range 项，会重复）；斜率把它减掉。
    为什么用三尺寸最小二乘而不是两点：j0 与 k0 是近对（真差只有几 ns），
    两点斜率被一次 1~2 ns 的噪声拉动就能翻转 j/k 家族次序——实测踩过：
    同一台机器相邻两个进程分别量出 k0−j0=+1.5 和 −1.2 ns，模型 top-5 的
    家族构成随之洗牌。三尺寸中位数×最小二乘把这条近对的读数稳定下来。
    为什么尺寸 ≤ 96：内核 v3 循环一段不超过 tile 边长（≤96），下标全在
    CPython 小整数缓存（−5..256）内、数据集在 L1/L2 里——校准数据必须
    长成内核的样子，否则量的是 cache miss 和大整数分配，不是语句。
    """
    ts = [_t_med(lambda k: f(k, s), n, reps) for s in _SLOPE_SIZES]
    xs = _SLOPE_SIZES
    mx, mt = sum(xs) / len(xs), sum(ts) / len(ts)
    num = sum((x - mx) * (t - mt) for x, t in zip(xs, ts))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den / n * 1e9


def _per_exec_ns(f, n, c_loop, reps=5):
    """机器行单价（range 建立/前奏/min 行）：96 次一组的内层循环里量，
    每次执行价 = t/(n·96) − 纯循环机器价（外层污染全部抵消）。"""
    t = _t_med(lambda k: f(k), n, reps)
    return t / (n * 96) * 1e9 - c_loop


def calibrate() -> Costs:
    """16 根单价一次量完。每根都镜像内核内层的写法。

    镜像三纪律（每一条都踩过坑）：
      ① 函数局部变量（D109 探针 A 的教训：全局变量 LOAD_GLOBAL 会量歪）；
      ② 数据集 ≤ 80KB：内核真实工作集就这么大，量大了量进 cache miss；
      ③ 下标 ≤ 96：CPython 只缓存 −5..256 的小整数，量大了量进整数分配。
    """
    import random
    rng = random.Random(7)
    W = 100

    def grow():
        return [rng.uniform(-1.0, 1.0) for _ in range(W)]

    rowC = grow()
    rowA = grow()
    rowB = grow()
    B = [grow() for _ in range(W)]                # 双下标用的行堆（~80KB）
    C_ = [grow() for _ in range(W)]
    A_ = [grow() for _ in range(W)]
    a = rowA[0]
    v2 = 3
    lo, hi, U = 0, W, 4
    i0, TMv, Mv = 16, 32, 96

    gc_old = gc.isenabled()
    gc.disable()
    t0 = time.perf_counter()
    try:
        # ---- 语句行：双尺寸斜率（rhi 由闭包传入 48/96）
        def f_loop(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    pass

        def f_j0(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    rowC[v] += a * rowB[v]

        def f_ju(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    rowC[v + 1] += a * rowB[v + 1]

        def f_k0(n, rhi):
            c = 0.0
            for _ in range(n):
                for v in range(rhi):
                    c += rowA[v] * B[v][v2]
            return c

        def f_ku(n, rhi):
            c = 0.0
            for _ in range(n):
                for v in range(rhi):
                    c += rowA[v + 1] * B[v + 1][v2]
            return c

        def f_i0(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    C_[v][v2] += A_[v][v2] * a

        def f_iu(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    C_[v + 1][v2] += A_[v + 1][v2] * a

        def f_hs1(n, rhi):                        # Bv = B[v1]
            x = 0.0
            for _ in range(n):
                for v in range(rhi):
                    x = B[v]
            return x

        def f_hs2(n, rhi):                        # Ci = C[v1]; Ai = A[v1]（一行两句）
            x = y = 0.0
            for _ in range(n):
                for v in range(rhi):
                    x = C_[v]; y = A_[v]
            return x is y

        def f_hsm(n, rhi):                        # Ci = C[v2]; a = A[v2][v1]（单＋双）
            x = a2 = 0.0
            for _ in range(n):
                for v in range(rhi):
                    x = C_[v]; a2 = A_[v][v2]
            return a2

        def f_hd1(n, rhi):                        # b = B[v1][v2]
            x = 0.0
            for _ in range(n):
                for v in range(rhi):
                    x = B[v][v2]
            return x

        def f_s2(n, rhi):                         # C[v1][v2] = c
            c = 0.5
            for _ in range(n):
                for v in range(rhi):
                    C_[v][v2] = c

        c = Costs()
        c.loop = _slope_ns(f_loop, 1024)
        for key, f in (("j0", f_j0), ("ju", f_ju), ("k0", f_k0), ("ku", f_ku),
                       ("i0", f_i0), ("iu", f_iu), ("hs1", f_hs1),
                       ("hs2", f_hs2), ("hsm", f_hsm), ("hd1", f_hd1),
                       ("s2", f_s2)):
            setattr(c, key, _slope_ns(f, 1024))

        # ---- 机器行：96 次一组的内层计数循环，减掉纯循环机器价
        def f_r2(n):                              # 二参 range 的建立（1 次迭代）
            m2 = 0
            rlo_, rhi_ = 3, 4
            for _ in range(n):
                for v in range(rlo_, rhi_):
                    m2 = v
            return m2

        def f_r3(n):                              # 主循环形态 range(lo, lo+m, U)
            m3 = 0
            rlo_, one = 3, 1
            for _ in range(n):
                for v in range(rlo_, rlo_ + one, U):
                    m3 = v
            return m3

        def f_pre(n):
            m = 0
            for _ in range(n):
                for q in range(96):
                    m = (hi - lo) - (hi - lo) % U
            return m

        def f_min3(n):
            x = y = z = 0
            for _ in range(n):
                for q in range(96):
                    x = min(i0 + TMv, Mv); y = min(i0 + TMv, Mv); z = min(i0 + TMv, Mv)
            return x + y + z

        # range2/range3：内层循环只有 1 次迭代 → 每次『建立』价 = t/n − 1×loop
        c.range2 = _t_med(f_r2, 16384) / 16384 * 1e9 - c.loop
        c.range3 = _t_med(f_r3, 16384) / 16384 * 1e9 - c.loop
        c.pre = _per_exec_ns(f_pre, 2048, c.loop)
        c.min3 = _per_exec_ns(f_min3, 2048, c.loop)
        c.wall_ms = (time.perf_counter() - t0) * 1000.0
    finally:
        if gc_old:
            gc.enable()
    return c


CALIB_CACHE = os.path.join(OUTPUTS, "calibration.json")


def get_costs():
    """读校准缓存（--exp calibrate 落盘），没有就现场校准。

    缓存纪律（D109 probes.json 的同款规矩）：同一次复现内，calibration.txt /
    model-table.txt / accuracy.txt / 引导搜索共享同一组单价——否则跨进程漂移
    （D107 实测 ~8.6%，今天校准的运行间漂移同量级）会让文件之间互相打架。
    删掉 calibration.json 可强制重校。
    """
    if os.path.exists(CALIB_CACHE):
        with open(CALIB_CACHE, encoding="utf-8") as fh:
            d = json.load(fh)
        c = Costs(**{k: v for k, v in d["costs"].items()
                     if k in Costs.__dataclass_fields__})
        return c, f"缓存 {os.path.basename(CALIB_CACHE)}（{d.get('timestamp', '')}校准）"
    c = calibrate()
    return c, "现场校准（无缓存；--exp calibrate 可落盘共享）"


# ---------------------------------------------------------------- ③ 预测

def predict_ms(cnt: OpCounts, costs: Costs) -> float:
    """t_pred = Σ 行数 × 行单价（毫秒）。流量项另算——见 traffic_ms()。"""
    ns = (cnt.j0 * costs.j0 + cnt.ju * costs.ju
          + cnt.k0 * costs.k0 + cnt.ku * costs.ku
          + cnt.i0 * costs.i0 + cnt.iu * costs.iu
          + cnt.hs1 * costs.hs1 + cnt.hs2 * costs.hs2
          + cnt.hsm * costs.hsm + cnt.hd1 * costs.hd1 + cnt.s2 * costs.s2
          + cnt.loop * costs.loop + cnt.range2 * costs.range2
          + cnt.range3 * costs.range3 + cnt.pre * costs.pre
          + cnt.min3 * costs.min3)
    return ns / 1e6


def traffic_ms(cnt: OpCounts, bw_gbps: float, bytes_per_visit: int = 4) -> float:
    """流量项：元素访问 × 每访问字节数 ÷ 带宽。只报账，不进排序。

    两种口径（D109 的教训：带宽必须与被分析的执行层同层）：
      bytes_per_visit=4  → C 级通路（BW 用探针 C 的 2.68 GB/s）：真正的内存
                            搬运时间，µs 量级——证明内存根本不是约束；
      bytes_per_visit=8  → Python 级当量（BW 用探针 B 的 0.385 GB/s）：每次
                            元素访问的解释器成本。它与语句成本是同一批事件
                            （D109：解释世界的『带宽』就是解释器本身），
                            只用来交叉验证量级，绝不能与 t_pred 相加——加了
                            就是把同一笔账记两遍。
    """
    return cnt.elem_access * bytes_per_visit / (bw_gbps * 1e9) * 1e3


def roofline_bound_ms(M, N, K, p_gflops: float) -> float:
    """D109 的坐标系当免费下界：t ≥ flops ÷ 解释屋顶（与候选无关，shape 级）。"""
    return 2 * M * N * K / (p_gflops * 1e9) * 1e3


# ---------------------------------------------------------------- settrace 真值校验
#
# CPython 3.11 的行事件语义（先实测再依赖，见 README 5.2）：
#   `for` 行在循环入口和每次迭代成功时各触发一次 → hits = 建立数 + 迭代数；
#   普通语句行每次执行触发一次；循环耗尽不触发。

_PATTERNS = [
    (re.compile(r"^\s*for i0 in range"), "for_i0"),
    (re.compile(r"^\s*for j0 in range"), "for_j0"),
    (re.compile(r"^\s*for k0 in range"), "for_k0"),
    (re.compile(r"ihi = min"), "min3"),
    (re.compile(r"^\s*for v1 in range"), "for_v1"),
    (re.compile(r"^\s*for v2 in range"), "for_v2"),
    (re.compile(r"^\s*n = "), "pre"),
    # 尾部循环 range(lo + n, hi)：`+ n` 后紧跟逗号；主循环 range(lo, lo + n, U)
    # 的 `+ n` 后也是逗号但前面有第二个参数——用 `\w+ \+ n,` 钉住首参即尾循环
    (re.compile(r"^\s*for v3 in range\(\w+ \+ n,"), "for_tail"),
    (re.compile(r"^\s*for v3 in range"), "for_main"),
    (re.compile(r"\+= .*Bv\[v3"), "inner_j"),
    (re.compile(r"c \+= Ai\[v"), "inner_k"),
    (re.compile(r"C\[v3"), "inner_i"),
    (re.compile(r"C\[v\d\]\[v\d\] = c"), "s2"),
    (re.compile(r";"), "hoist_pair"),
    (re.compile(r"= \w+\[v\d\]\[v\d\]"), "hd1"),
    (re.compile(r"= \w+\[v"), "hs1"),
]


def classify_source(src: str):
    """生成源码逐行归类。返回 {行号: 类名}；内层语句再细分 main_u0/main_uN/tail。"""
    classes = {}
    in_main = False
    for idx, line in enumerate(src.splitlines(), start=1):
        if "for v3 in range" in line:
            # 主循环第二参是 `lo + n`；尾循环的首参就是 `lo + n`——用首参位置区分
            in_main = not re.match(r"\s*for v3 in range\(\w+ \+ n,", line)
        for pat, name in _PATTERNS:
            if pat.search(line):
                if name == "inner_j" or name == "inner_k" or name == "inner_i":
                    if "v3 + " in line:
                        name = "inner_u"
                    elif in_main:
                        name = "inner_main0"
                    else:
                        name = "inner_tail0"
                elif name == "hoist_pair":    # 配对行：后半句是双下标 → hsm，否则 hs2
                    name = "hsm" if re.search(r";\s*\w+ = \w+\[v\d\]\[v\d\]", line) \
                        else "hs2"
                classes[idx] = name
                break
    return classes


def trace_counts(cfg: KernelConfig, M, N, K):
    """小 shape 上真跑一遍，用行事件数出每类语句行的真实执行次数。"""
    kernel = make_kernel(cfg)
    classes = classify_source(kernel.src)
    hits = {}

    def tracer(frame, event, arg):
        if frame.f_code.co_name != "_kernel":
            return None
        if event == "line":
            hits[frame.f_lineno] = hits.get(frame.f_lineno, 0) + 1
        return tracer

    A, B, bias = make_inputs(M, N, K, seed=3)
    C = [[bias[j] for j in range(N)] for _ in range(M)]
    sys.settrace(tracer)
    try:
        kernel(A, B, C, M, N, K)
    finally:
        sys.settrace(None)
    got = {}
    for ln, n in hits.items():
        name = classes.get(ln)
        if name is None:
            name = f"UNCLASSIFIED_L{ln}"
        got[name] = got.get(name, 0) + n
    return got


def trace_to_truth(got: dict) -> dict:
    """行事件 → 与 OpCounts 校验字段同口径的量（for 行 = 建立数 + 迭代数）。"""
    t = {}
    t["it_i0"] = got.get("for_i0", 0) - 1              # i0 行 = 1 建立 + it_i0 迭代
    t["it_j0"] = got.get("for_j0", 0) - t["it_i0"]     # j0 行 = it_i0 建立 + it_j0 迭代
    t["it_k0"] = got.get("for_k0", 0) - t["it_j0"]
    t["min3"] = got.get("min3", 0)
    t["it_v1"] = got.get("for_v1", 0) - t["it_k0"]     # v1 行 = it_k0 建立 + it_v1 迭代
    t["it_v2"] = got.get("for_v2", 0) - t["it_v1"]
    t["pre"] = got.get("pre", 0)                       # 前奏行 = v2 体执行数 = it_v2
    t["it_main"] = got.get("for_main", 0) - t["it_v2"]
    t["it_tail"] = got.get("for_tail", 0) - t["it_v2"]
    t["inner0_main"] = got.get("inner_main0", 0)
    t["inner0_tail"] = got.get("inner_tail0", 0)
    t["inner_u"] = got.get("inner_u", 0)
    for k in ("hs1", "hs2", "hsm", "hd1", "s2"):
        t[k] = got.get(k, 0)
    return t


VERIFY_KEYS = ["it_i0", "it_j0", "it_k0", "min3", "it_v1", "it_v2", "pre",
               "it_main", "it_tail", "inner0_main", "inner0_tail", "inner_u",
               "hs1", "hs2", "hsm", "hd1", "s2"]


def verify_experiment() -> str:
    """静态计数器 vs settrace 真值：小 shape 全订单×全 U×多 tile 边界。"""
    lines = [BAR, " 真值校验：静态计数器 vs sys.settrace 逐行计数（小 shape）", BAR]
    cases = []
    for order in ORDERS:                       # 单 tile，U 全谱：1/2/3/4
        for u in (1, 2, 3, 4):
            cases.append((12, 12, 12, KernelConfig(12, 12, 12, order, u)))
    for order in ORDERS:                       # 多 tile＋边界 tile＋U 不整除
        for u in (1, 4):
            cases.append((20, 18, 16, KernelConfig(8, 6, 16, order, u)))
    cases.append((20, 18, 16, KernelConfig(16, 16, 16, "ikj", 4)))
    cases.append((10, 9, 8, KernelConfig(10, 9, 8, "ikj", 4)))   # 单 tile 非立方
    cases.append((10, 9, 8, KernelConfig(3, 4, 5, "jik", 4)))    # 碎 tile＋尾 2

    n_bad = 0
    for M, N, K, cfg in cases:
        cnt = count_ops(M, N, K, cfg)
        truth = trace_to_truth(trace_counts(cfg, M, N, K))
        mine = {k: (cnt.inner_plus() if k == "inner_u" else getattr(cnt, k))
                for k in VERIFY_KEYS}
        bad = {k for k in truth if mine.get(k) != truth[k]}
        if bad:
            n_bad += 1
            lines.append(f" ✗ {cfg.describe():<22} 不一致：{sorted(bad)}")
            lines.append(f"     计数器 {mine}")
            lines.append(f"     真值   {truth}")
        unclassified = [k for k in truth if k.startswith("UNCLASSIFIED")]
        if unclassified:
            n_bad += 1
            lines.append(f" ✗ {cfg.describe():<22} 有未归类行：{unclassified}")
    lines.append(f" 校验 {len(cases)} 个配置 × {len(VERIFY_KEYS)} 项计数："
                 f"{'全部一致' if n_bad == 0 else f'{n_bad} 个失败'}")
    lines.append(" 语义前提（CPython 3.11 实测）：for 行事件 = 循环建立数 + 迭代数")
    return "\n".join(lines)


# ---------------------------------------------------------------- D108 记录读取

def _check_sha(path, want):
    import hashlib
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    if digest != want:
        raise SystemExit(f"{os.path.basename(path)} 血统校验失败：{digest}")


def load_d108() -> list:
    _check_sha(RESULTS_PATH, RESULTS_SHA)
    out = []
    with open(RESULTS_PATH, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def load_probes() -> dict:
    _check_sha(PROBES_PATH, PROBES_SHA)
    with open(PROBES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def cfg_of(rec) -> KernelConfig:
    k = rec["kernel"]
    return KernelConfig(k["tm"], k["tn"], k["tk"], k["order"], k["unroll"])


def stage_truth(records, stage):
    """D108 某段通过记录 → {shape: [(cfg, median_ms, name), ...]}。"""
    truth = {}
    for r in records:
        if r["tune"]["stage"] != stage or not r["correctness"]["passed"]:
            continue
        truth.setdefault(r["tune"]["shape_id"], []).append(
            (cfg_of(r), r["stats_ms"]["median"], r["kernel"]["name"]))
    return truth


def screen_wall_ms(records):
    """D108 筛选段每 shape 的 Σwall（bench_one 整次调用墙钟，含门+预热+计时）。"""
    out = {}
    for r in records:
        if r["tune"]["stage"] == "screen":
            out[r["tune"]["shape_id"]] = out.get(r["tune"]["shape_id"], 0.0) \
                + r["wall_ms"]
    return out


def final_wall_ms(records):
    out = {}
    for r in records:
        if r["tune"]["stage"] == "final":
            out[r["tune"]["shape_id"]] = out.get(r["tune"]["shape_id"], 0.0) \
                + r["wall_ms"]
    return out


# ---------------------------------------------------------------- 统计小工具

def spearman(xs, ys) -> float:
    """Spearman 秩相关（并列取平均秩）。零依赖实现。"""
    def ranks(v):
        order_ = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order_):
            j = i
            while j + 1 < len(order_) and v[order_[j + 1]] == v[order_[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for t in range(i, j + 1):
                r[order_[t]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx)
           * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def fmt_ms(x):
    return f"{x:8.2f}" if x >= 10 else f"{x:8.3f}"


# ---------------------------------------------------------------- 实验：校准

def exp_calibrate() -> str:
    c = calibrate()
    with open(CALIB_CACHE, "w", encoding="utf-8") as fh:
        json.dump({"schema": "d110.calibration/1",
                   "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "costs": dataclasses.asdict(c)}, fh, ensure_ascii=False, indent=1)
    probes = load_probes()
    rows = [
        ("j0", "j 内层行  Ci[v] += a*Bv[v]", "全行访问（D92 最快内层）"),
        ("ju", "j 内层＋展开  Ci[v+1] += …", "多 2 次下标加法：U=4 的税"),
        ("k0", "k 内层行  c += Ai[v]*B[v][v2]", "B 列跨步＋双下标"),
        ("ku", "k 内层＋展开  c += Ai[v+1]*…", ""),
        ("i0", "i 内层行  C[v][v2] += A[v][v2]*b", "双跨步，最惨家族"),
        ("iu", "i 内层＋展开  C[v+1][v2] += …", ""),
        ("hs1", "行提升·单下标  Bv = B[v]", "复用在 CPython 里的化身"),
        ("hs2", "行提升·双单下标  Ci=C[v]; Ai=A[v]", "kernel_gen 一行两句"),
        ("hsm", "行提升·单＋双下标  Ci=C[v]; a=A[v][v1]", ""),
        ("hd1", "行提升·双下标  b = B[v][v2]", ""),
        ("s2", "k 家族尾部写回  C[v][v2] = c", ""),
        ("loop", "循环迭代机器 FOR_ITER+STORE", ""),
        ("range2", "二参 range 建立＋迭代器", ""),
        ("range3", "三参 range 建立＋迭代器", ""),
        ("pre", "展开前奏 n = (hi-lo)-(hi-lo)%U", ""),
        ("min3", "tile 外壳三连 min 行", ""),
    ]
    out = [BAR, " D110 Cost Model 校准：16 根语句行单价（微基准中位数，ns/行）", BAR,
           f" 校准墙钟：{c.wall_ms:.0f} ms（一次付清，三 shape 共用）",
           f" 镜像纪律：函数局部变量＋真实 float 列表（D109 探针 A 的教训）", ""]
    for key, desc, note in rows:
        out.append(f"  {key:>7}  {desc:<36} {getattr(c, key):7.1f} ns   {note}")
    out += ["",
            " 参照系（D109 探针缓存 inputs/probes-d109.json）：",
            f"  解释屋顶 P = {probes['A']['value_gflops'] * 1000:.1f} MFLOPS"
            f"（探针 A；FMA 每 FLOP ≈ {1 / probes['A']['value_gflops']:.0f} ns）",
            f"  Python 级带宽 = {probes['B']['value_gbps']:.3f} GB/s（探针 B，流量项用）",
            "",
            " 单价结构自检：",
            f"  i0 最贵（下标 4 次家族）：{c.i0 > c.k0 and c.i0 > c.j0}"
            f"（i0={c.i0:.1f} > k0={c.k0:.1f} / j0={c.j0:.1f} ns，方向必须对）",
            f"  j0 与 k0 是近对：差 {abs(c.k0 - c.j0):.1f} ns"
            f"（{'k0' if c.k0 > c.j0 else 'j0'} 略贵）——家族次序由这条近对决定，",
            "   噪声敏感：翻转不致命（top-K 预筛兜底），但会把 kij/ikj 与 ijk/jik 互调",
            f"  ju > j0（展开税）: {c.ju > c.j0}，每行 +{c.ju - c.j0:.1f} ns",
            f"  hsm > hs2 > hs1 > 0：{c.hsm > c.hs2 > c.hs1 > 0}"
            f"（{c.hsm:.1f} / {c.hs2:.1f} / {c.hs1:.1f} ns）"]
    return "\n".join(out)


# ---------------------------------------------------------------- 实验：模型排序表

def exp_rank() -> str:
    costs, src_note = get_costs()
    probes = load_probes()
    records = load_d108()
    truth = stage_truth(records, "screen")
    out = [BAR, " Cost Model 排序：三 shape 全候选（预测 vs D108 实测）", BAR,
           " 口径：实测 = D108 筛选段 3+7 中位数（inputs/results-d108.jsonl，不重测）",
           f"       预测 = Σ 语句行数 × 校准单价（零内核执行；单价来自{src_note}）", ""]
    for sid, M, N, K in SHAPES:
        cands = build_space(sid, M, N, K)
        rows = []
        for cfg in cands:
            cnt = count_ops(M, N, K, cfg)
            pred = predict_ms(cnt, costs)
            act = next((ms for c, ms, _ in truth[sid] if c == cfg), None)
            rows.append((pred, act, cfg, cnt))
        rows.sort(key=lambda r: r[0])
        t_bound = roofline_bound_ms(M, N, K, probes["A"]["value_gflops"])
        max_c = max(traffic_ms(r[3], probes["C"]["value_gbps"], 4) for r in rows)
        max_py = max(traffic_ms(r[3], probes["B"]["value_gbps"], 8) for r in rows)
        min_pred = min(r[0] for r in rows)
        out.append(f" [{sid}] {M}×{N}×{K}：{len(cands)} 个候选；"
                   f"Roofline 下界 = flops ÷ P = {t_bound:.2f} ms（与候选无关）")
        out.append(f"  流量项（实际访问次数×4B ÷ C 级 2.68 GB/s，含 tile 重读）最大 "
                   f"{max_c:.2f} ms ≈ 最快预测的 {max_c / min_pred * 100:.0f}% —— "
                   f"内存时间比解释时间低一个数量级；它与语句成本是同一批事件的不同计价，"
                   f"不叠加（Python 级当量 {max_py:.0f} ms 与预测同量级，D109：解释世界的"
                   f"『带宽』就是解释器本身）")
        out.append("  模型名次  配置                        预测 ms   实测 ms   误差%   实测名次")
        act_order = {c: i + 1 for i, (c, ms, _) in
                     enumerate(sorted(truth[sid], key=lambda t: t[1]))}
        for i, (pred, act, cfg, _) in enumerate(rows, 1):
            err = (pred - act) / act * 100 if act else float("nan")
            out.append(f"  {i:>5}    {cfg.describe():<26} {fmt_ms(pred)}  "
                       f"{fmt_ms(act) if act else '    —   '}  {err:+6.1f}  "
                       f"{act_order.get(cfg, '—'):>4}")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- 实验：精度报告

def exp_accuracy() -> str:
    costs, _ = get_costs()
    records = load_d108()
    truth = stage_truth(records, "screen")
    out = [BAR, " 模型精度：与 D108 实测对照（模型误差与错误排序的账）", BAR]
    for sid, M, N, K in SHAPES:
        pairs = []
        for cfg, act, name in truth[sid]:
            pred = predict_ms(count_ops(M, N, K, cfg), costs)
            pairs.append((pred, act, cfg))
        preds = [p for p, a, c in pairs]
        acts = [a for p, a, c in pairs]
        rho = spearman(preds, acts)
        order_actual = sorted(pairs, key=lambda t: t[1])
        order_model = sorted(pairs, key=lambda t: t[0])
        rank_model = {c: i + 1 for i, (p, a, c) in enumerate(order_model)}
        _, champ_act, champ_cfg = order_actual[0]
        champ_pred = predict_ms(count_ops(M, N, K, champ_cfg), costs)

        errs = sorted((p - a) / a * 100 for p, a, c in pairs)
        med_err = statistics.median(errs)
        mae = statistics.mean(abs(e) for e in errs)

        out.append(f"\n [{sid}] {M}×{N}×{K}（n={len(pairs)}，D108 筛选中位数）")
        out.append(f"  Spearman ρ（预测 vs 实测）        = {rho:.3f}")
        out.append(f"  真冠军 {champ_cfg.describe()}")
        out.append(f"    实测 {champ_act:.2f} ms / 模型预测 {champ_pred:.2f} ms"
                   f"（误差 {(champ_pred - champ_act) / champ_act * 100:+.1f}%，"
                   f"模型第 {rank_model[champ_cfg]} 名）")
        for kk in (1, 2, 3, 4, 5, 8):
            hit = champ_cfg in [c for p, a, c in order_model[:kk]]
            out.append(f"  recall@{kk}（真冠军在模型前 {kk} 名里）  = "
                       f"{'命中' if hit else '漏掉'}")
        top5_actual = {c for p, a, c in order_actual[:5]}
        top5_model = {c for p, a, c in order_model[:5]}
        out.append(f"  实测 top-5 ∩ 模型 top-5          = {len(top5_actual & top5_model)}/5")
        out.append(f"  误差%（预测−实测）/实测：中位 {med_err:+.1f}%，"
                   f"MAE {mae:.1f}%，范围 {errs[0]:+.1f}% ~ {errs[-1]:+.1f}%")

        # 错误排序最多的候选：|模型名次 − 实测名次| 前三名
        rank_actual = {c: i + 1 for i, (p, a, c) in enumerate(order_actual)}
        jumps = sorted(pairs,
                       key=lambda t: -abs(rank_model[t[2]] - rank_actual[t[2]]))[:3]
        out.append("  名次跳变最大（错误排序现场）：")
        for p, a, c in jumps:
            out.append(f"    {c.describe():<26} 实测第 {rank_actual[c]:>2} 名"
                       f" ↔ 模型第 {rank_model[c]:>2} 名"
                       f"（实测 {a:.2f} / 预测 {p:.2f} ms，误差 {(p - a) / a * 100:+.1f}%）")

        # 分家族偏差：模型在哪里系统性看走眼
        fam = {}
        for p, a, c in pairs:
            key = (c.order[-1] + "内层", f"U={c.unroll}")
            fam.setdefault(key, []).append((p - a) / a * 100)
        out.append("  分家族平均误差%（正=模型高估耗时）：")
        for key in sorted(fam):
            v = fam[key]
            out.append(f"    {key[0]} {key[1]}  n={len(v):>2}  "
                       f"均值 {statistics.mean(v):+.1f}%  范围 {min(v):+.1f}%~{max(v):+.1f}%")
    return "\n".join(out)


# ---------------------------------------------------------------- 自检

def exp_self_test() -> str:
    from bench import capture_env
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # 0. 环境
    env = capture_env()
    ok("环境：CPython 3.11", env["python"].startswith("3.11"), env["python"])

    # 1. 输入血统
    try:
        records = load_d108()
        ok("输入血统：results-d108.jsonl sha256 钉死", True, f"{len(records)} 条")
    except SystemExit as e:
        ok("输入血统：results-d108.jsonl sha256 钉死", False, str(e))
        records = []
    try:
        probes = load_probes()
        ok("输入血统：probes-d109.json sha256 钉死", True)
    except SystemExit as e:
        ok("输入血统：probes-d109.json sha256 钉死", False, str(e))
        probes = {"A": {"value_gflops": 0.0547}, "B": {"value_gbps": 0.385}}

    # 2. 搜索空间与 D108 记录数对账
    screen_n = {}
    for r in records:
        if r["tune"]["stage"] == "screen":
            screen_n[r["tune"]["shape_id"]] = screen_n.get(r["tune"]["shape_id"], 0) + 1
    for sid, M, N, K in SHAPES:
        n_cand = len(build_space(sid, M, N, K))
        n_poison = 2 if sid == "S3" else 0
        ok(f"空间对账 {sid}：{n_cand} 正确候选 + {n_poison} 投毒 = D108 筛选记录",
           screen_n.get(sid) == n_cand + n_poison,
           f"模型空间 {n_cand}+{n_poison} vs D108 {screen_n.get(sid)}")

    # 3. 计数器真值（精选代表配置，完整矩阵见 --exp verify）
    for M, N, K, cfg in [(12, 12, 12, KernelConfig(12, 12, 12, "kij", 4)),
                         (20, 18, 16, KernelConfig(8, 6, 16, "ijk", 4)),
                         (10, 9, 8, KernelConfig(3, 4, 5, "jki", 4))]:
        cnt = count_ops(M, N, K, cfg)
        truth = trace_to_truth(trace_counts(cfg, M, N, K))
        mine = {k: (cnt.inner_plus() if k == "inner_u" else getattr(cnt, k))
                for k in VERIFY_KEYS}
        bad = [k for k in VERIFY_KEYS if mine[k] != truth[k]]
        ok(f"计数器真值 {cfg.describe()}", not bad,
           f"不一致项：{bad}" if bad else f"{len(VERIFY_KEYS)} 项全对")

    # 4. 计数器内部一致性：朴素内层 = 主循环 u0 + 尾部朴素
    for sid, M, N, K in SHAPES:
        for cfg in build_space(sid, M, N, K)[:6]:
            cnt = count_ops(M, N, K, cfg)
            ok(f"内部一致 {cfg.describe()}",
               cnt.inner_plain() == cnt.inner0_main + cnt.inner0_tail
               and cnt.inner_plus() == cnt.ju + cnt.ku + cnt.iu)

    # 5. 校准单价的方向与量级（与全部报告共享同一份缓存，口径一致）
    c, cal_src = get_costs()
    ok("单价方向：i0 最贵（i0 > k0 且 i0 > j0，下标 4 次家族）",
       c.i0 > c.k0 and c.i0 > c.j0,
       f"{c.i0:.1f} > k0={c.k0:.1f} / j0={c.j0:.1f} ns；{cal_src}")
    ok("单价近对：|k0 − j0| < 8 ns（家族次序的决定项，翻转风险见模型误差账）",
       abs(c.k0 - c.j0) < 8,
       f"差 {abs(c.k0 - c.j0):.1f} ns（{'k0' if c.k0 > c.j0 else 'j0'} 略贵）")
    ok("单价方向：展开版比朴素版贵（ju > j0）", c.ju > c.j0, f"{c.ju - c.j0:+.1f} ns/行")
    ok("单价方向：hsm > hs2 > hs1 > 0", c.hsm > c.hs2 > c.hs1 > 0,
       f"{c.hs1:.1f} / {c.hs2:.1f} / {c.hsm:.1f} ns")
    ok("单价量级：语句 10~200 ns、循环机器 < 30 ns",
       all(10 < x < 200 for x in (c.j0, c.k0, c.i0, c.hs1, c.hs2, c.hsm)) and c.loop < 30,
       f"loop={c.loop:.1f} ns")

    # 6. 预测的三个物理约束：下界、流量占比、家族次序
    for sid, M, N, K in SHAPES:
        t_bound = roofline_bound_ms(M, N, K, probes["A"]["value_gflops"])
        worst_traffic = 0.0
        fam_best = {}
        preds_all = []
        for cfg in build_space(sid, M, N, K):
            cnt = count_ops(M, N, K, cfg)
            pred = predict_ms(cnt, c)
            preds_all.append(pred)
            worst_traffic = max(worst_traffic,
                                traffic_ms(cnt, probes["C"]["value_gbps"], 4) / pred)
            fam = cfg.order[-1]
            fam_best[fam] = min(fam_best.get(fam, 1e9), pred)
        ok(f"{sid}：全部预测 ≥ Roofline 下界的 90%",
           all(p >= t_bound * 0.9 for p in preds_all),
           f"下界 {t_bound:.1f} ms，最小预测 {min(preds_all):.1f} ms"
           f"（留 10% 余量：探针 A 与内核语句风格略有差异）")
        ok(f"{sid}：C 级流量项 < 预测的 10%（重读全算上，内存仍低一个量级）",
           worst_traffic < 0.10, f"最大 {worst_traffic * 100:.1f}%")
        ok(f"{sid}：i 家族预测最贵（结构稳健）；j/k 家族是近对",
           fam_best["i"] > max(fam_best["j"], fam_best["k"]),
           f"j={fam_best['j']:.1f} k={fam_best['k']:.1f} < i={fam_best['i']:.1f} ms"
           f"（j/k 次序跟单价近对走，翻转会换冠军——但都在 top-K 里）")

    # 7. 精度底线：ρ 与 recall（模型必须『有用』才配当预筛）
    truth = stage_truth(records, "screen")
    for sid, M, N, K in SHAPES:
        pairs = [(predict_ms(count_ops(M, N, K, cfg), c), act, cfg)
                 for cfg, act, name in truth[sid]]
        rho = spearman([p for p, a, cf in pairs], [a for p, a, cf in pairs])
        order_model = sorted(pairs, key=lambda t: t[0])
        order_actual = sorted(pairs, key=lambda t: t[1])
        champ = order_actual[0][2]
        hit5 = champ in [cf for p, a, cf in order_model[:5]]
        rank = [cf for p, a, cf in order_model].index(champ) + 1
        ok(f"{sid}：Spearman ρ ≥ 0.75", rho >= 0.75, f"ρ = {rho:.3f}")
        ok(f"{sid}：真冠军进模型 top-5", hit5,
           f"冠军 {champ.describe()} 在模型第 {rank} 名")

    # 汇总
    n_pass = sum(1 for _, good, _ in checks if good)
    out = [BAR, f" D110 自检：{n_pass}/{len(checks)} 项通过", BAR]
    for name, good, detail in checks:
        out.append(f" {'✓' if good else '✗'} {name}" + (f"  [{detail}]" if detail else ""))
    return "\n".join(out)


# ---------------------------------------------------------------- 主入口

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D110 简单 Cost Model")
    ap.add_argument("--exp", required=True,
                    choices=["calibrate", "verify", "rank", "accuracy",
                             "self-test", "env"])
    args = ap.parse_args()
    os.makedirs(OUTPUTS, exist_ok=True)
    if args.exp == "env":
        from bench import capture_env
        env = capture_env()
        print(BAR)
        print(" 环境：D110 简单 Cost Model 排序")
        print(BAR)
        for k, v in env.items():
            print(f" {k}: {v}")
        print(" 输入：inputs/results-d108.jsonl（sha256 钉死，D108 全部 110 条）")
        print("       inputs/probes-d109.json（D109 屋顶缓存：流量项/下界用）")
        print(" 依赖：零第三方；kernel_gen.py/bench.py 为 D108 逐字节副本")
        print(" 模型：静态语句行计数 × 16 根微基准单价；不执行任何被测内核")
    elif args.exp == "calibrate":
        print(exp_calibrate())
    elif args.exp == "verify":
        print(verify_experiment())
    elif args.exp == "rank":
        print(exp_rank())
    elif args.exp == "accuracy":
        print(exp_accuracy())
    elif args.exp == "self-test":
        print(exp_self_test())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
