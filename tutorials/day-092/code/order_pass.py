#!/usr/bin/env python3
"""第 92 天：循环顺序与局部性——i/j/k 的 6 种排列，同一份语义、6 种访存行为。

学习计划（第 92 天）：
  学习：i/j/k 不同排列对 A、B、C 访问局部性的影响；
  实践：手工分析至少两种循环顺序的连续访问和复用情况；
  产出：循环顺序与访存行为对照表。

本机未安装 MLIR（与 Day 57~91 一致）：复用 Day 90 的 shape_pass.py
（Python 复刻 MLIR DialectConversion 语义的仿真工程，只取不改），
今天新增一个参数化的 LoopOrderPattern——同一个 mini.matmul，按 order
元组生成 6 种循环嵌套，再从解释执行器的真实访存日志里量化「局部性」：

  OT1  语义不变性：6 种顺序全部与同序参考实现位等价（k 处处升序 →
       舍入顺序不变）；ijk 复现 Day 89/90 的 18 op 结构
  OT2  手工分析对账：先在纸上写下预测（最内层、A/B/C 步长分类、流量、
       复用距离），再逐条与真实访存日志对账
  OT3  缓存模拟：对 16×16×16 的真实访存轨迹做直接映射缓存模拟
       （16B 行 × 32/64/128/256 行），看顺序如何改变缺失率
  OT4  对照表产出：outputs/order-table.txt（计划点名的交付物）
  OT5  忘记清零的回归：k 不在最内层却不清零 C → 读到垃圾值 → 结果错

用法：
    python3 order_pass.py                 # OT1~OT5 全跑，写 outputs/
    python3 order_pass.py --order ikj     # 单顺序深度分析（步长/流量/复用）
    python3 order_pass.py --cache 32      # 换缓存行数重跑模拟（对照实验）
    python3 order_pass.py --no-init       # 复现「k 外层忘清零」（OT5）

产出（outputs/）：
    order-table.txt   循环顺序与访存行为对照表（6 种顺序 × 结构/步长/流量/复用/缓存）
    cache-sim.txt     缓存模拟明细（4 种容量 × 6 种顺序，真实轨迹回放）
    ir-i-j-k.txt      i-j-k 顺序 IR（18 op，与 Day 89/90 同构）
    ir-i-k-j.txt      i-k-j 顺序 IR（21 op：清零 nest ＋ 内存累加）
    ir-k-i-j.txt      k-i-j 顺序 IR（21 op，k 在最外层）
"""

from __future__ import annotations

import argparse
import platform
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "day-090" / "code"))

import shape_pass as sp   # noqa: E402  （Day 90 的工程——今天只取不改）
from shape_pass import (  # noqa: E402
    EXPECTED_BODY, LoopSpec, build_main_graph, make_inputs, print_module,
    reference_matmul, run_pass, trip_count,
)
from shape_pass import ConversionPattern, Interp, MemRefOOBError, Value, make_memref   # noqa: E402
from shape_pass import is_static, memref_shape   # noqa: E402

OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

SEED = 92          # 第 92 天自己的输入种子（可复现）
M, K, N = 2, 3, 2  # 贯穿例：2×3 乘 3×2 → 2×2（与 Day 91 复盘例同形状，种子不同）

SIM_SHAPE = (16, 16, 16)   # 缓存模拟用的形状（A/B/C 各 1KB——容量效应看得见）
SIM_LINE = 4               # 缓存行 = 4 个 f32（16 字节）
SIM_PAD = 1                # 矩阵间隔 1 行（避免共享缓存行；对齐到行边界）
SIM_CACHES = [32, 64, 128, 256]   # 直接映射缓存行数 → 512B / 1KB / 2KB / 4KB

# 6 种排列（外 → 内）；Day 89~91 的实现是第一个
ORDERS = [("i", "j", "k"), ("i", "k", "j"), ("j", "i", "k"),
          ("j", "k", "i"), ("k", "i", "j"), ("k", "j", "i")]

PASS, FAIL = 0, 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"：{detail}" if detail else ""))
    return ok


def env_line():
    return (f"环境：{platform.system()} {platform.machine()}, "
            f"Python {platform.python_version()}, numpy {np.__version__}; "
            f"本机未安装 MLIR（Day 57~91 口径：Python 复刻 DialectConversion 语义仿真）")


def oname(order):
    return "-".join(order)


# ============================================================
# LoopOrderPattern：把「循环顺序」从常量变成参数（Day 93 配置化的前身）
# ============================================================

class LoopOrderPattern(ConversionPattern):
    """mini.matmul → 指定顺序的三重循环。

    与 Day 90 的 MatMulBodyPattern 同一套 match 契约（静态 2D、内维匹配），
    差别只在 rewrite：按 order=(o1,o2,o3) 从外到内套循环。

    两种形态（结构是数据，语义不变——OT1 验证）：
      · k 在最内层（ijk / jik）：与 Day 89/90 相同的 18 op——
        累加器走 iter_args（寄存器语义），k 扫完一次 store C[i,j]，
        零起点由 %zero 出门（Day 87 的成果原样保留）。
      · k 不在最内层（其余 4 种）：累加落到内存——C[i,j] 逐趟
        load→addf→store（读-改-写），因此需要显式清零 nest
        （for i { for j { store %zero } }，＋3 op）。

    注：所有顺序的 k 都升序迭代，每个 C[i,j] 的加法顺序不变 → 位等价。
    """

    root_name = "mini.matmul"
    benefit = 1
    debug_name = "LoopOrderPattern"

    def __init__(self, order=("i", "j", "k"), init=True):
        assert sorted(order) == ["i", "j", "k"], f"order 必须是 i/j/k 的排列，拿到 {order}"
        self.order = tuple(order)
        self.init = init
        self.specs = []

    def matchAndRewrite(self, op, adaptor, rewriter):
        # ---------- match：与 Day 90 同一套契约（只取不改的精神） ----------
        if len(adaptor.operands) != 2:
            return rewriter.notifyMatchFailure(
                op, f"期望 2 个操作数，实际 {len(adaptor.operands)}")
        ta, tb = adaptor.operands[0].type, adaptor.operands[1].type
        sa, sb = memref_shape(ta), memref_shape(tb)
        if sa is None or sb is None:
            return rewriter.notifyMatchFailure(
                op, f"操作数还不是 memref（拿到 {ta} / {tb}）")
        if len(sa) != 2 or len(sb) != 2:
            return rewriter.notifyMatchFailure(
                op, f"只支持 2 维矩阵乘，拿到 A{sa} @ B{sb}")
        if not (is_static(sa) and is_static(sb)):
            return rewriter.notifyMatchFailure(
                op, f"动态维度（A{sa} @ B{sb}）：静态 Pattern 宁拒不猜（Day 90 口径）")
        if sa[1] != sb[0]:
            return rewriter.notifyMatchFailure(
                op, f"内维不匹配：A.shape[1]={sa[1]} ≠ B.shape[0]={sb[0]}")
        M, K = sa
        N = sb[1]
        a, b = adaptor.operands[0], adaptor.operands[1]
        o1, o2, o3 = self.order

        # ---------- rewrite：一切修改走 rewriter ----------
        ub = {"i": M, "j": N, "k": K}
        src = {"i": f"M = A.shape[0] = {M}", "j": f"N = B.shape[1] = {N}",
               "k": f"K = 内维契约 A.shape[1] == B.shape[0] = {K}"}
        self.specs = [LoopSpec(f"%{v}", 0, ub[v], 1, src[v]) for v in self.order]

        used = set()

        def cname(v):
            n = f"%c{v}"
            while n in used:
                n += "'"
            used.add(n)
            return n

        # ① 输出缓冲 ＋ ② 零起点 ＋ ③ 5 个 index 常量（Day 87/88 原样）
        alloc = rewriter.create(
            "memref.alloc", result_names=["%c"], result_types=[make_memref((M, N))],
            comments=[f"输出缓冲 {M * N * 4} B：alloc 不清零（D87）"])
        zero = rewriter.create(
            "arith.constant", result_names=["%zero"], result_types=["f32"],
            attrs={"value": 0.0},
            comments=["零起点：k 在最内层时是 iter_args 初值；否则喂给清零 nest"])
        consts = [rewriter.create("arith.constant", result_names=[cname(v)],
                                  result_types=["index"], attrs={"value": v})
                  for v in (0, 1, M, N, K)]
        lo, st, bm, bn, bk = [c.results[0] for c in consts]

        iv = {v: Value(f"%{v}", "index") for v in "ijk"}
        buc = {"i": bm, "j": bn, "k": bk}

        def loop_comments(v):
            sp_ = self.specs[self.order.index(v)]
            return [f"四要素：[{sp_.lb},{sp_.ub}) step {sp_.step}，trip = {trip_count(sp_)}",
                    f"ub 来源：{sp_.ub_source}"]

        # ④ 清零 nest：k 不在最内层时必须显式清零（内存累加的零起点）
        if o3 != "k" and self.init:
            stz = rewriter.create(
                "memref.store", operands=[zero.results[0], alloc.results[0],
                                          iv["i"], iv["j"]],
                comments=["清零：C[i,j] ← 0（k 不在最内层 → 累加在内存，零起点要自己铺）"])
            fjz = rewriter.create("scf.for", operands=[lo, bn, st],
                                  attrs={"iv": "%j", "iv_value": iv["j"]},
                                  body=[stz], comments=loop_comments("j"))
            rewriter.create("scf.for", operands=[lo, bm, st],
                            attrs={"iv": "%i", "iv_value": iv["i"]},
                            body=[fjz],
                            comments=[*loop_comments("i"), "清零 nest：M·N 次 store，沿 C 的行连续"])

        # ⑤ 主循环 nest：从最内层往外建（f_in 就是最内层循环本尊）
        inner_note = [f"最内层：{o3} 每步 {2 if o3 == 'k' else 4} 次访存（"
                      f"{'A、B' if o3 == 'k' else 'A、B、C读、C写'}）"]
        if o3 == "k":
            # —— 形态 A：k 最内层（Day 89/90 的结构）——
            acc_arg = Value("%acc", "f32")
            xa = rewriter.create(
                "memref.load", operands=[a, iv["i"], iv["k"]],
                result_names=["%xa"], result_types=["f32"],
                comments=[f"读 A：A[i,k] → {K}·i+k（i←行，k←列）"])
            xb = rewriter.create(
                "memref.load", operands=[b, iv["k"], iv["j"]],
                result_names=["%xb"], result_types=["f32"],
                comments=[f"读 B：B[k,j] → {N}·k+j（k←行，j←列）"])
            p = rewriter.create("arith.mulf", operands=[xa.results[0], xb.results[0]],
                                result_names=["%p"], result_types=["f32"],
                                comments=["%p = A[i,k]·B[k,j]"])
            s = rewriter.create("arith.addf", operands=[acc_arg, p.results[0]],
                                result_names=["%s"], result_types=["f32"],
                                comments=["%acc（区域参数）＋ %p → %s"])
            yld = rewriter.create("scf.yield", operands=[s.results[0]],
                                  comments=["写回通道：本趟 %s → 下一趟 %acc"])
            f_in = rewriter.create(
                "scf.for", operands=[lo, bk, st, zero.results[0]],
                result_names=["%acc"], result_types=["f32"],
                attrs={"iv": "%k", "iv_value": iv["k"],
                       "iter_names": ["%acc"], "iter_args": [acc_arg]},
                body=[xa, xb, p, s, yld],
                comments=[*loop_comments("k"), *inner_note,
                          f"归约在最内层：累加器走 iter_args（寄存器语义）——"
                          f"{'Day 89/90 原顺序' if self.order == ('i', 'j', 'k') else '换序但 k 仍最内'}"])
            stm = rewriter.create(
                "memref.store", operands=[f_in.results[0], alloc.results[0],
                                          iv["i"], iv["j"]],
                comments=["写 C：k 扫完一趟 store 一次——每格恰写 1 次终值"])
            # 中层循环体 = [k 循环, store]；store 放中层（i、j 都在作用域内）
            mid_body = [f_in, stm]
        else:
            # —— 形态 B：k 不在最内层——累加在内存（C 逐趟读-改-写）——
            xa = rewriter.create(
                "memref.load", operands=[a, iv["i"], iv["k"]],
                result_names=["%xa"], result_types=["f32"],
                comments=["读 A：A[i,k]（下标不含 "
                          + ("j" if o3 == "j" else "i") + " → 最内层扫描时不变）"])
            xb = rewriter.create(
                "memref.load", operands=[b, iv["k"], iv["j"]],
                result_names=["%xb"], result_types=["f32"],
                comments=["读 B：B[k,j]（下标不含 "
                          + ("j" if o3 == "j" else "i") + " → 最内层扫描时"
                          + ("沿行连续" if o3 == "j" else "不变") + "）"])
            cv = rewriter.create(
                "memref.load", operands=[alloc.results[0], iv["i"], iv["j"]],
                result_names=["%cv"], result_types=["f32"],
                comments=["读 C（读-改-写）：k 不在最内层 → 部分和住在内存里"])
            p = rewriter.create("arith.mulf", operands=[xa.results[0], xb.results[0]],
                                result_names=["%p"], result_types=["f32"],
                                comments=["%p = A[i,k]·B[k,j]"])
            s = rewriter.create("arith.addf", operands=[cv.results[0], p.results[0]],
                                result_names=["%s"], result_types=["f32"],
                                comments=["%cv ＋ %p → %s（每趟都舍入——加法顺序仍是 k 升序）"])
            stm = rewriter.create(
                "memref.store", operands=[s.results[0], alloc.results[0],
                                          iv["i"], iv["j"]],
                comments=["写 C：本趟部分和落盘（下一趟再读回来加）"])
            f_in = rewriter.create("scf.for", operands=[lo, buc[o3], st],
                                   attrs={"iv": f"%{o3}", "iv_value": iv[o3]},
                                   body=[xa, xb, cv, p, s, stm],
                                   comments=[*loop_comments(o3), *inner_note])
            mid_body = [f_in]

        f2 = rewriter.create("scf.for", operands=[lo, buc[o2], st],
                             attrs={"iv": f"%{o2}", "iv_value": iv[o2]},
                             body=mid_body, comments=loop_comments(o2))
        rewriter.create("scf.for", operands=[lo, buc[o1], st],
                        attrs={"iv": f"%{o1}", "iv_value": iv[o1]},
                        body=[f2],
                        comments=[*loop_comments(o1),
                                  f"最外层：{o1}——{oname(self.order)} 顺序（外→内）"])
        rewriter.replaceOp(op, [alloc.results[0]])
        return True


# ============================================================
# 运行工具：跑一种顺序，带回真实访存日志
# ============================================================

def run_order(order, m, k, n, seed=SEED, init=True):
    """跑一次「转换＋解释执行」：返回 dict（res/func/interp/C/err/A/B）。"""
    func = build_main_graph(m, k, n)
    pat = LoopOrderPattern(order, init=init)
    _, res = run_pass(func, "full", patterns=[pat])
    if not res.ok:
        return dict(res=res, pat=pat, func=func, interp=None, C=None,
                    err=None, A=None, B=None, ref=None)
    A, B = make_inputs(m, k, n, seed)
    interp = Interp({"%a": A, "%b": B})
    err = None
    try:
        interp.run(func)
    except MemRefOOBError as exc:
        err = str(exc)
    C = None
    if err is None and interp.ret is not None:
        C = np.array([cell[1] for cell in interp.mem[interp.ret]],
                     dtype=np.float32).reshape(m, n)
    return dict(res=res, pat=pat, func=func, interp=interp, C=C, err=err,
                A=A, B=B, ref=reference_matmul(A, B))


# ============================================================
# 手工分析预测表：先在纸上写下预期，再由 OT2 对账（不抄日志）
# ============================================================

# 每种顺序的预测——全部来自纸面推理（小例 2×3@3×2 上验证）：
#   inner       最内层归纳变量
#   a / b       最内层扫描时 A / B 的步长分类：seq=连续 +1；fixed=下标不含最内层（体不变）；
#               stride:N / stride:K=每次跳 N / K 格（跨行）
#   c_body      C 是否进循环体：none=不进（寄存器累加）；seq / stride:N=RMW 步长
#   c_store     C 的 store 流步长（k 内层时 store 在中层循环尾部）
#   acc         累加器位置：register（iter_args）/ memory（C 逐趟 RMW）
#   init        是否需要显式清零 nest
#   reuse_a/b   同一格「最近一次重访」的平均间隔（访问次数）——注意这是元素级复用：
#               最内层下标不含它的张量才是 4（体不变），其余要等外层轮回
PREDICT = {
    "i-j-k": dict(inner="k", a="seq", b="stride:N", c_body="none", c_store="seq",
                  acc="register", init=False, reuse_a="2*K+1", reuse_b="N*(2*K+1)"),
    "i-k-j": dict(inner="j", a="fixed", b="seq", c_body="seq", c_store="seq",
                  acc="memory", init=True, reuse_a="4", reuse_b="4*K*N"),
    "j-i-k": dict(inner="k", a="seq", b="stride:N", c_body="none", c_store="stride:N",
                  acc="register", init=False, reuse_a="M*(2*K+1)", reuse_b="2*K+1"),
    "j-k-i": dict(inner="i", a="stride:K", b="fixed", c_body="stride:N", c_store="stride:N",
                  acc="memory", init=True, reuse_a="4*K*M", reuse_b="4"),
    "k-i-j": dict(inner="j", a="fixed", b="seq", c_body="seq", c_store="seq",
                  acc="memory", init=True, reuse_a="4", reuse_b="4*N"),
    "k-j-i": dict(inner="i", a="stride:K", b="fixed", c_body="stride:N", c_store="stride:N",
                  acc="memory", init=True, reuse_a="4*M", reuse_b="4"),
}

# 流量公式（与顺序无关的部分：A、B 每 body 各 load 一次；
# k 外层时 C 每 body 一读一写，清零另加 M·N 次 store）
def traffic_formula(order, m, k, n):
    if order[2] == "k":
        return dict(a_loads=m * n * k, b_loads=m * n * k,
                    c_loads=0, c_stores=m * n, init_stores=0)
    return dict(a_loads=m * n * k, b_loads=m * n * k,
                c_loads=m * n * k, c_stores=m * n * k, init_stores=m * n)


# ============================================================
# 日志分析：步长分类、流量、复用距离（全部从真实 access_log 计算）
# ============================================================

def addr_stream(log, mem, kind, skip=0):
    """某个 (mem, kind) 流的地址序列（skip 掐头——跳过清零段的 store）。"""
    return [addr for kd, m_, idx, addr, v in log
            if m_ == mem and kd == kind][skip:]


def classify_strides(addrs):
    """相邻差值分类 → (主导类别, 步长)。

    seq=fixed 主导 +1；fixed=差值 0 主导（体不变）；stride=S=主导跳 S 格。
    """
    if len(addrs) < 2:
        return ("none", 0)
    diffs = [b - a for a, b in zip(addrs, addrs[1:])]
    cnt = Counter(diffs)
    zero = cnt.pop(0, 0)
    if zero > len(diffs) - zero:          # 差值 0 占多数 → 体不变
        return ("fixed", 0)
    pos = Counter(d for d in diffs if d > 0)
    (step, times), = pos.most_common(1)
    return ("seq" if step == 1 else "stride", step)


def classify_strides_full(addrs):
    """同上，但区分 seq/stride/none 的完整签名（对账用）。"""
    cat, step = classify_strides(addrs)
    if cat == "none":
        return "none"
    if cat == "fixed":
        return "fixed"
    return "seq" if step == 1 else f"stride:{step}"


def reuse_distances(log, mem):
    """每个地址相邻两次访问的间隔（全局访问序号差）→ 所有间隔的均值。"""
    pos = {}
    for t, (kd, m_, idx, addr, v) in enumerate(log):
        if m_ == mem:
            pos.setdefault(addr, []).append(t)
    gaps = [b - a for ps in pos.values() for a, b in zip(ps, ps[1:])]
    return (sum(gaps) / len(gaps)) if gaps else None


def measured_streams(r, m, k, n):
    """从一次运行的真实日志抽取：各流步长分类、流量、复用距离。"""
    log = r["interp"].access_log
    init_len = m * n if (r["pat"].order[2] != "k" and r["pat"].init) else 0
    streams = {
        "a": classify_strides_full(addr_stream(log, "%a", "load")),
        "b": classify_strides_full(addr_stream(log, "%b", "load")),
        "c_body": ("none" if r["pat"].order[2] == "k"
                   else classify_strides_full(addr_stream(log, "%c", "load"))),
        "c_store": classify_strides_full(addr_stream(log, "%c", "store", skip=init_len)),
    }
    counts = Counter((kd, m_) for kd, m_, idx, addr, v in log)
    traffic = dict(a_loads=counts[("load", "%a")], b_loads=counts[("load", "%b")],
                   c_loads=counts[("load", "%c")],
                   c_stores=counts[("store", "%c")] - init_len,
                   init_stores=init_len)
    reuse = dict(a=reuse_distances(log, "%a"), b=reuse_distances(log, "%b"))
    return streams, traffic, reuse


# ============================================================
# 缓存模拟：对真实访存轨迹回放直接映射缓存
# ============================================================

def flat_bases(m, k, n, line=SIM_LINE, pad=SIM_PAD):
    """A/B/C 在扁平地址空间的基址（元素单位，行对齐 ＋ pad 行间隔）。"""
    def align(x):
        return ((x + line - 1) // line) * line
    bA = 0
    bB = align(m * k) + pad * line
    bC = align(bB + k * n) + pad * line
    return {"%a": bA, "%b": bB, "%c": bC}


def cache_sim(log, m, k, n, lines, line=SIM_LINE, pad=SIM_PAD):
    """直接映射缓存回放：write-allocate，store 与 load 同等对待。

    返回 dict(total, hits, misses, hit_rate, per_mem, unique_lines)。
    模型口径：行 = 4 个 f32；槽 = 块号 % 行数；无预取、无写缓冲——
    最简模型，数字只用于「顺序之间的对比」，不是任何真实硬件的测量。
    """
    base = flat_bases(m, k, n, line, pad)
    slots = {}
    per_mem = Counter()
    unique = set()
    hits = 0
    for kd, mem, idx, addr, v in log:
        blk = (base[mem] + addr) // line
        unique.add(blk)
        slot = blk % lines
        if slots.get(slot) == blk:
            hits += 1
        else:
            slots[slot] = blk          # write-allocate：store 未命中也装行
            per_mem[mem] += 1
    total = len(log)
    return dict(total=total, hits=hits, misses=total - hits,
                hit_rate=hits / total if total else 0.0,
                per_mem=dict(per_mem), unique_lines=len(unique))


# ============================================================
# OT1：语义不变性——6 种顺序与同序参考位等价
# ============================================================

def ot1_semantics(runs_small, runs_sim):
    print("\n—— OT1 语义不变性：换个顺序，结果变吗？ ——")
    ijk_ops = [op.name for op in runs_small["i-j-k"]["func"].walk()]
    check("OT1a i-j-k 复现 Day 89/90 的 18 op 结构", ijk_ops == list(EXPECTED_BODY),
          f"实测 {len(ijk_ops)} op（alloc/zero/常量×5/for×3/load×2/mulf/addf/yield/store）")
    ops_ok = all(len(list(r["func"].walk())) == (18 if o[2] == "k" else 21)
                 for o, r in zip(ORDERS, [runs_small[oname(o)] for o in ORDERS]))
    check("OT1b 六种顺序结构：k 内层 18 op；k 外层 21 op（清零 nest ＋3）", ops_ok,
          "结构是数据：换个排列不换积木，只换装配")
    eq_small = [bool(np.array_equal(runs_small[oname(o)]["C"], runs_small[oname(o)]["ref"]))
                for o in ORDERS]
    check("OT1c 小例 A(2,3)@B(3,2)：6/6 与同序参考位等价", all(eq_small),
          "k 处处升序 → 每个 C[i,j] 的加法与舍入顺序不变——换序不换数")
    eq_sim = [bool(np.array_equal(runs_sim[oname(o)]["C"], runs_sim[oname(o)]["ref"]))
              for o in ORDERS]
    check("OT1d 大例 A(16,16)@B(16,16)：6/6 位等价（语义不变与形状无关）", all(eq_sim),
          "含 k 外层的 4 种：内存累加也是 k 升序逐步舍入，与寄存器累加逐位相同")


# ============================================================
# OT2：手工分析对账——纸面预测 vs 真实访存日志
# ============================================================

def ot2_manual(runs_small):
    print("\n—— OT2 手工分析对账：纸上预测 vs 真实访存日志（小例 2×3@3×2） ——")
    # 步长符号 → 数值（A 的跨行步长是 K；B、C 的跨行步长是 N）
    def resolve(sym):
        if sym.startswith("stride:"):
            return f"stride:{K if sym.endswith('K') else N}"
        return sym

    ok_inner = ok_str = ok_traf = ok_reuse = True
    for o in ORDERS:
        name = oname(o)
        pred = PREDICT[name]
        r = runs_small[name]
        streams, traffic, reuse = measured_streams(r, M, K, N)
        ok_inner &= (o[2] == pred["inner"])
        for key in ("a", "b", "c_body", "c_store"):
            ok_str &= (streams[key] == resolve(pred[key]))
        tf = traffic_formula(o, M, K, N)
        for key in ("a_loads", "b_loads", "c_loads", "c_stores", "init_stores"):
            ok_traf &= (traffic[key] == tf[key])
        # 复用距离公式求值（元素级：同一格下次被读还要隔多少次访问）
        env = dict(M=M, K=K, N=N)
        ra = int(eval(pred["reuse_a"], {}, env))
        rb = int(eval(pred["reuse_b"], {}, env))
        ok_reuse &= (reuse["a"] == ra and reuse["b"] == rb)
    check("OT2a 最内层归纳变量 = 预测（6/6）", ok_inner,
          "；".join(f"{oname(o)}→{o[2]}" for o in ORDERS))
    check("OT2b A/B/C 步长分类 = 预测（6 顺序 × 4 流，真实日志逐条算）", ok_str,
          "seq=连续+1｜fixed=体不变｜stride:S=跳 S 格｜" + "；".join(
              f"{oname(o)}:{PREDICT[oname(o)]['a']}/{PREDICT[oname(o)]['b']}"
              f"/{'—' if PREDICT[oname(o)]['c_body'] == 'none' else PREDICT[oname(o)]['c_body']}"
              for o in ORDERS))
    check("OT2c 流量 = 公式（A/B 恒 MNK；C 由 k 位置决定）", ok_traf,
          "k 内层：C 0 读 + MN 写；k 外层：C MNK 读 + MNK 写 + MN 清零——"
          "2×3@3×2 上即 12/12/0/4/0 与 12/12/12/12/4")
    check("OT2d 元素级最近复用距离 = 纸面公式（均值，逐地址实测）", ok_reuse,
          "A：ijk 7、jik 14、ikj/kij 4、jki 24、kji 8；"
          "B：ijk 14、jik 7、ikj 24、kij 8、jki/kji 4——"
          "「体不变」的张量才是 4，其余等外层轮回")


# ============================================================
# OT3：缓存模拟——16³ 真实轨迹 × 4 种容量
# ============================================================

def ot3_cache(runs_sim, sims):
    print("\n—— OT3 缓存模拟：直接映射回放（16×16×16，行 16B，矩阵间隔 1 行） ——")
    m, k, n = SIM_SHAPE
    total_ok = True
    for o in ORDERS:
        name = oname(o)
        exp = (2 * m * n * k + m * n) if o[2] == "k" else (4 * m * n * k + m * n)
        total_ok &= (sims[(name, 32)]["total"] == exp)
    check("OT3a 总访问数 = 公式（k 内层 2MNK+MN=8448；k 外层 4MNK+MN=16640）",
          total_ok, "访问数与顺序无关的部分先对齐——差异全部来自「落在哪里」")
    fit = sims[(oname(ORDERS[0]), 256)]
    uniq = fit["unique_lines"]
    fit_ok = all(sims[(oname(o), 256)]["misses"] == uniq for o in ORDERS)
    check("OT3b 4KB（256 行）全装下：6 种顺序 miss 全部 = 数据行数", fit_ok,
          f"unique 行 = {uniq}（A 64 + B 64 + C 64，pad 行不触碰）——只剩强制缺失，顺序无关")
    s32 = {oname(o): sims[(oname(o), 32)]["misses"] for o in ORDERS}
    order32 = sorted(s32, key=s32.get)
    pred32 = ["i-k-j", "k-i-j", "i-j-k", "j-i-k", "k-j-i", "j-k-i"]
    check("OT3c 512B（32 行）排序 = 预测：ikj/kij < ijk < jik < kji/jki",
          order32 == pred32,
          "；".join(f"{nm} {s32[nm]}" for nm in pred32)
          + "——缓存装不下跨行步进时，连续访问的顺序赢")
    s64 = {oname(o): sims[(oname(o), 64)]["misses"] for o in ORDERS}
    flip = (s64["i-j-k"] < s64["i-k-j"] and s64["i-j-k"] < s64["k-i-j"])
    check("OT3d 1KB（64 行）翻转：i-j-k 反超（寄存器累加免掉 C 的 RMW 流量）", flip,
          "；".join(f"{nm} {s64[nm]}" for nm in ("i-j-k", "j-i-k", "i-k-j", "k-i-j"))
          + "——工作集（A 行 4 行 + B 列 16 行）装得下时，k 内层的「不碰 C」是硬优势")


# ============================================================
# OT4：对照表产出（计划点名的交付物）
# ============================================================

def ot4_table(runs_small, runs_sim, sims):
    print("\n—— OT4 对照表产出 ——")
    m, k, n = SIM_SHAPE
    L = ["循环顺序与访存行为对照表（第 92 天交付物）", env_line(), "",
         f"贯穿小例：A({M},{K}) @ B({K},{N}) → C({M},{N})，种子 {SEED}（流量与复用距离在此测量）",
         f"缓存模拟：A({m},{k}) @ B({k},{n})，直接映射，行 16B（4×f32），矩阵间隔 1 行",
         "  容量：32 行=512B / 64 行=1KB / 128 行=2KB / 256 行=4KB；write-allocate；无预取",
         "  口径：对解释执行器的真实访存日志回放——是模拟测量，不是任何真实硬件的实测", ""]
    L.append("总纲：A、B 的 load 总数与顺序无关（恒 2·M·N·K）；顺序改变的是三件事——")
    L.append("  ① 最内层下标决定每次访问的步长（空间局部性：seq 连续 / stride 跨行 / fixed 不变）")
    L.append("  ② k 的位置决定累加器住哪（寄存器 iter_args vs 内存 RMW → C 流量 MN vs 2·MNK+MN）")
    L.append("  ③ 外层排列决定同一格何时重访（时间局部性：复用距离）")
    L.append("")
    for o in ORDERS:
        name = oname(o)
        pred = PREDICT[name]
        r = runs_small[name]
        streams, traffic, reuse = measured_streams(r, M, K, N)
        nops = len(list(r["func"].walk()))
        eq = bool(np.array_equal(r["C"], r["ref"]))
        L.append("=" * 78)
        L.append(f"顺序 {name}：for {o[0]} {{ for {o[1]} {{ for {o[2]} {{ … }} }} }}"
                 f"（{o[2]} 最内层）")
        L.append("=" * 78)
        L.append(f"结构    ：{nops} op（{'18：k 在最内层，Day 89/90 同构' if o[2] == 'k' else '21：主循环 18 + 清零 nest 3'}）")
        L.append(f"累加器  ：{ '寄存器（iter_args %acc，k 内层）' if pred['acc'] == 'register' else '内存（C[i,j] 逐趟 load→addf→store）'}")
        L.append(f"清零    ：{ '不需要——%zero 作为 iter_args 初值出门（Day 87）' if not pred['init'] else f'需要——init nest 铺 {M * N} 次 store'}")
        L.append(f"最内层 {o[2]} 扫描时：A {PREDICT[name]['a']}｜B {PREDICT[name]['b']}"
                 f"｜C {PREDICT[name]['c_body'] if PREDICT[name]['c_body'] != 'none' else '不进体（累加在寄存器）'}")
        L.append(f"步长实测：A {streams['a']}｜B {streams['b']}｜"
                 f"C读 {streams['c_body']}｜C写 {streams['c_store']}（含清零段另计 {traffic['init_stores']} 次连续 store）")
        L.append(f"流量实测（小例）：A load {traffic['a_loads']}｜B load {traffic['b_loads']}｜"
                 f"C load {traffic['c_loads']}｜C store {traffic['c_stores']}"
                 f"（公式：{'0 读 + M·N 写' if o[2] == 'k' else 'M·N·K 读 + (M·N·K+M·N) 写'}）")
        L.append(f"复用距离实测（小例）：A 最近重访均值 {reuse['a']:.1f} 次访问｜"
                 f"B {reuse['b']:.1f} 次（预测 {pred['reuse_a']} / {pred['reuse_b']}）")
        row = "｜".join(f"{ln}行 {sims[(name, ln)]['misses']} miss"
                        f"（{sims[(name, ln)]['misses'] / sims[(name, ln)]['total']:.0%}）"
                        for ln in SIM_CACHES)
        L.append(f"缓存模拟（16³）：{row}")
        L.append(f"语义    ：与同序参考位等价 = {eq}")
    L.append("")
    L.append("=" * 78)
    L.append("汇总矩阵（行 = 顺序，外→内；数字为真实测量）")
    L.append("=" * 78)
    L.append(f"{'顺序':<8}{'最内':<4}{'A':<10}{'B':<10}{'C(体)':<10}{'累加':<6}"
             f"{'清零':<4}{'C流量(小例)':<16}{'A/B复用':<12}{'miss@512B':<10}{'miss@1KB':<9}")
    for o in ORDERS:
        name = oname(o)
        pred = PREDICT[name]
        _, traffic, reuse = measured_streams(runs_small[name], M, K, N)
        cflow = (f"{traffic['c_loads']}L+{traffic['c_stores']}S")
        reuse_s = f"{reuse['a']:.0f}/{reuse['b']:.0f}"
        L.append(f"{name:<8}{o[2]:<4}{pred['a']:<10}{pred['b']:<10}"
                 f"{('—' if pred['c_body'] == 'none' else pred['c_body']):<10}"
                 f"{('寄存' if pred['acc'] == 'register' else '内存'):<6}"
                 f"{('免' if not pred['init'] else '要'):<4}{cflow:<16}{reuse_s:<12}"
                 f"{sims[(name, 32)]['misses']:<10}{sims[(name, 64)]['misses']:<9}")
    L.append("")
    L.append("读表三问：")
    L.append("  ① 同一列纵向比：最内层换成 j（ikj/kij），B 从跳 N 变连续 +1，C 从不进体变连续 RMW；")
    L.append("  ② C 流量列：k 内层两家 0L+4S，k 外层四家 12L+12S＋4 清零——k 的位置一个决定，")
    L.append("     C 流量从 4 次写暴涨到 28 次访问（7 倍）；")
    L.append(" ③ miss 列横向看：512B 时连续派（ikj/kij）赢；1KB 时寄存器派（ijk/jik）反超——")
    L.append("    最优顺序取决于「缓存容量 vs 工作集」的相对大小，这正是 Tiling 要解决的问题（Day 94）。")
    (OUT / "order-table.txt").write_text("\n".join(L) + "\n", encoding="utf-8")

    # 缓存模拟明细
    L2 = ["缓存模拟明细（真实访存轨迹回放）", env_line(), "",
          f"形状 A({m},{k}) @ B({k},{n})；直接映射；行 16B；矩阵间隔 1 行（pad 不触碰）",
          f"总访问：k 内层 8448（A 4096 + B 4096 + C 256 store）；"
          f"k 外层 16640（A 4096 + B 4096 + C 4096 读 + C 4352 写）", ""]
    L2.append(f"{'顺序':<8}{'容量':<8}{'访问':<8}{'命中':<8}{'缺失':<8}{'命中率':<8}"
              f"{'A缺':<7}{'B缺':<7}{'C缺':<7}")
    for ln in SIM_CACHES:
        for o in ORDERS:
            name = oname(o)
            s = sims[(name, ln)]
            pm = s["per_mem"]
            L2.append(f"{name:<8}{ln * 16}B{'':<3}{s['total']:<8}{s['hits']:<8}"
                      f"{s['misses']:<8}{s['hit_rate']:.1%}{'':<1}"
                      f"{pm.get('%a', 0):<7}{pm.get('%b', 0):<7}{pm.get('%c', 0):<7}")
        L2.append("")
    L2.append("注：直接映射的冲突缺失会让特定步长模式额外吃亏（如 jik 的 B 列与 A 行撞槽）——")
    L2.append("    真实缓存有组相联度、预取和写缓冲；本表数字只用于顺序之间的对比。")
    (OUT / "cache-sim.txt").write_text("\n".join(L2) + "\n", encoding="utf-8")

    ok = (OUT / "order-table.txt").stat().st_size > 1000 and \
         (OUT / "cache-sim.txt").stat().st_size > 500
    check("OT4 对照表已写入 outputs/order-table.txt ＋ cache-sim.txt", ok,
          "6 种顺序 × 结构/步长/流量/复用/缓存，数字全部来自真实运行")


# ============================================================
# OT5：忘记清零的回归（k 外层却不清零 → 读垃圾 → 结果错）
# ============================================================

def ot5_no_init():
    print("\n—— OT5 忘记清零的回归：k 外层 ＋ 无 init nest ——")
    r = run_order(("k", "i", "j"), M, K, N, init=False)
    interp = r["interp"]
    uninit = interp.stats["uninit_reads"]
    eq = bool(np.array_equal(r["C"], r["ref"]))
    maxdiff = float(np.max(np.abs(r["C"] - r["ref"])))
    ok = (len(uninit) == M * N and not eq
          and len(list(r["func"].walk())) == 18)
    check("OT5 k-i-j 不清零：第一趟 k 就读到 M·N 条垃圾，结果 ≠ 参考", ok,
          f"未初始化读 {len(uninit)} 条（只有 k=0 那趟踩雷——之后读的是错误部分和；"
          f"垃圾 = 777+7·addr，Day 87 公式）；max|C−ref| = {maxdiff:.1f}；"
          f"18 op——结构看着正常，错在语义")
    lines = ["忘记清零的回归（k 不在最内层 ＋ 无 init nest）", env_line(), "",
             f"顺序 k-i-j，A({M},{K})@B({K},{N})，种子 {SEED}",
             f"未初始化读：{len(uninit)} 条（全部："
             + "；".join(f"{m}{idx}@{addr}" for m, idx, addr in uninit[:6]) + "）",
             f"垃圾值公式：garbage(addr) = 777 + 7·addr（Day 87 内存模型）",
             f"结果：max|C − ref| = {maxdiff:.3e}（远大于 0——垃圾进了累加链）",
             "",
             "机理：k 外层 → 第一趟 k=0 就执行 C[i,j] = 垃圾 + A·B，",
             "      零起点没有像 Day 87 那样被显式铺进内存。",
             "修复：形态 B（k 不在最内层）必须配 init nest（默认 init=True 就是修复后的形态）。"]
    (OUT / "no-init-check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================
# 单顺序深度分析（--order）：把一种顺序的访存行为摊开看
# ============================================================

def order_mode(order):
    o = tuple(order)
    r = run_order(o, M, K, N)
    name = oname(o)
    pred = PREDICT[name]
    streams, traffic, reuse = measured_streams(r, M, K, N)
    print(f"顺序 {name} 的访存行为（A({M},{K})@B({K},{N})，种子 {SEED}，真实执行）")
    print(f"  IR：{len(list(r['func'].walk()))} op；"
          f"LoopSpec（外→内）：{' 套 '.join(f'{s.iv}∈[{s.lb},{s.ub})' for s in r['pat'].specs)}")
    print(f"  累加器：{'寄存器（iter_args）' if o[2] == 'k' else '内存（C 逐趟 RMW）'}；"
          f"清零：{'免（%zero 出门）' if o[2] == 'k' else '要（init nest ' + str(M * N) + ' 次 store）'}")
    # 第一个最内层扫描的地址序列（手画对照）
    log = r["interp"].access_log
    init_len = M * N if (o[2] != "k" and r["pat"].init) else 0
    sweep = [e for e in log[init_len:init_len + (2 if o[2] == 'k' else 4) * max(M, K, N)]]
    print(f"  最内层 {o[2]} 的第一段访存（真实日志，格式：操作[线性地址]）：" if sweep else "")
    line = []
    for kd, mem, idx, addr, v in sweep:
        line.append(f"{kd[0].upper()}{mem.replace('%', '')}[{addr}]")
        if len(line) == 6:
            print("    " + " ".join(line))
            line = []
    if line:
        print("    " + " ".join(line))
    print(f"  步长实测：A {streams['a']}｜B {streams['b']}｜"
          f"C读 {streams['c_body']}｜C写 {streams['c_store']}"
          f"（预测 {pred['a']} / {pred['b']} / {pred['c_body']} / {pred['c_store']}）")
    print(f"  流量实测：A {traffic['a_loads']}｜B {traffic['b_loads']}｜"
          f"C {traffic['c_loads']}L+{traffic['c_stores']}S"
          f"（清零另 {traffic['init_stores']}S）")
    env = dict(M=M, K=K, N=N)
    print(f"  复用距离：A 最近重访均值 {reuse['a']:.1f} 次访问｜B {reuse['b']:.1f} 次"
          f"（预测 {pred['reuse_a']}={int(eval(pred['reuse_a'], {}, env))} / "
          f"{pred['reuse_b']}={int(eval(pred['reuse_b'], {}, env))}）")
    # 16³ 缓存模拟
    rs = run_order(o, *SIM_SHAPE)
    row = []
    for ln in SIM_CACHES:
        s = cache_sim(rs["interp"].access_log, *SIM_SHAPE, lines=ln)
        row.append(f"{ln * 16}B: {s['misses']} miss ({s['hit_rate']:.0%})")
    print(f"  缓存模拟（16³，真实轨迹回放）：" + "；".join(row))
    print(f"  语义：与同序参考位等价 = {bool(np.array_equal(r['C'], r['ref']))}")


# ============================================================
# 缓存对照实验（--cache）：换一个容量重跑 6 种顺序
# ============================================================

def cache_mode(lines):
    print(f"缓存对照实验：直接映射 {lines} 行 × 16B = {lines * 16}B（16×16×16 真实轨迹回放）")
    m, k, n = SIM_SHAPE
    rows = []
    for o in ORDERS:
        rs = run_order(o, *SIM_SHAPE)
        s = cache_sim(rs["interp"].access_log, m, k, n, lines=lines)
        rows.append((oname(o), s))
        print(f"  {oname(o):<8} 访问 {s['total']:<7} 缺失 {s['misses']:<7} "
              f"命中率 {s['hit_rate']:.1%}   A缺 {s['per_mem'].get('%a', 0):<6}"
              f"B缺 {s['per_mem'].get('%b', 0):<6}C缺 {s['per_mem'].get('%c', 0)}")
    best = min(rows, key=lambda t: t[1]["misses"])[0]
    print(f"  → 这个容量下绝对缺失最少的是 {best}；对照默认表（--sweep 或 cache-sim.txt）"
          f"看排名随容量怎么变")


def sweep_mode():
    m, k, n = SIM_SHAPE
    print("容量扫描（16×16×16，真实轨迹回放；miss 绝对数）")
    head = f"{'顺序':<8}" + "".join(f"{ln * 16}B{'':<7}" for ln in SIM_CACHES)
    print(head)
    for o in ORDERS:
        rs = run_order(o, *SIM_SHAPE)
        row = f"{oname(o):<8}"
        for ln in SIM_CACHES:
            s = cache_sim(rs["interp"].access_log, m, k, n, lines=ln)
            row += f"{s['misses']:<11}"
        print(row)


# ============================================================
# 主流程
# ============================================================

def collect():
    """跑齐 6 种顺序（小例 ＋ 16³），返回全部真实数据（make_images 复用）。"""
    runs_small = {oname(o): run_order(o, M, K, N) for o in ORDERS}
    runs_sim = {oname(o): run_order(o, *SIM_SHAPE) for o in ORDERS}
    sims = {}
    m, k, n = SIM_SHAPE
    for o in ORDERS:
        log = runs_sim[oname(o)]["interp"].access_log
        for ln in SIM_CACHES:
            sims[(oname(o), ln)] = cache_sim(log, m, k, n, lines=ln)
    # IR 快照（三个代表顺序）
    for nm in ("i-j-k", "i-k-j", "k-i-j"):
        o = tuple(nm.split("-"))
        r = run_order(o, M, K, N)
        ir = print_module(
            r["func"],
            [f"// 第 92 天：循环顺序 {nm}（{len(list(r['func'].walk()))} op，真实转换输出）",
             f"// 语义与 i-j-k 位等价（OT1）；差别只在访存行为（OT2/OT3）",
             env_line()])
        (OUT / f"ir-{nm}.txt").write_text(ir, encoding="utf-8")
    return runs_small, runs_sim, sims


def run_all():
    print("第 92 天 · 循环顺序与局部性：i/j/k 的 6 种排列，同一份语义、6 种访存行为")
    print(env_line())
    runs_small, runs_sim, sims = collect()
    ot1_semantics(runs_small, runs_sim)
    ot2_manual(runs_small)
    ot3_cache(runs_sim, sims)
    ot4_table(runs_small, runs_sim, sims)
    ot5_no_init()
    print()
    print(f"—— 检查测试 {PASS} PASS / {FAIL} FAIL ——")
    print("order-table.txt / cache-sim.txt / ir-i-j-k.txt / ir-i-k-j.txt / "
          "ir-k-i-j.txt / no-init-check.txt 已写入 outputs/")
    return FAIL == 0


def main():
    ap = argparse.ArgumentParser(description="第 92 天：循环顺序与局部性")
    ap.add_argument("--order", choices=[oname(o) for o in ORDERS],
                    help="单顺序深度分析（步长/流量/复用/缓存）")
    ap.add_argument("--cache", type=int, metavar="LINES",
                    help="换缓存行数重跑 6 种顺序的模拟（对照实验）")
    ap.add_argument("--sweep", action="store_true", help="容量扫描表")
    ap.add_argument("--no-init", action="store_true",
                    help="复现「k 外层忘清零」（OT5 的交互版）")
    args = ap.parse_args()
    if args.order:
        order_mode(args.order.split("-"))
    elif args.cache:
        cache_mode(args.cache)
    elif args.sweep:
        sweep_mode()
    elif args.no_init:
        ot5_no_init()
    else:
        sys.exit(0 if run_all() else 1)


if __name__ == "__main__":
    main()
