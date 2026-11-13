#!/usr/bin/env python3
"""test_counterexamples.py —— 第 70 天（第 10 周复盘）独立验收测试。

与 counterexample_lab.py 共享同一套 mini IR / 内存账本实现，
但用例独立编写（种子、图形状与主实验不同），按 A–G 七段验收：

  A  内存账本模型：视图/物化两世界的 bookkeeping 与 numpy 真实地址对账
  B  反例回归：R1–R7 每条反例的关键事实用独立种子复测
  C  守卫测试：每条 Pattern 在反例上拒绝、在正例上触发
  D  DCE 副作用：naive 误删 / guarded 保留，随机图压力测试
  E  结构哈希规范化：改名不改结构 → 哈希相等
  F  随机性质：值等价但内存轨迹不同的随机视图链（命题的随机化版本）
  G  MLIR 探针：5 个 stock 管道探针的计数断言（无 mlir-opt 则跳过）

运行：python3 test_counterexamples.py   （在 code/ 目录下）
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from counterexample_lab import (  # noqa: E402
    ELEMENTWISE_WHITELIST, Graph, guarded_dce, merge_adjacent_reshapes,
    merge_adjacent_reshapes_buggy, merge_adjacent_transposes, naive_dce,
    push_transpose_through_elementwise, eliminate_noop_cast,
    eliminate_cast_pair_naive, eliminate_copy_naive,
    eliminate_identity_transpose_naive, run_trace,
    find_mlir_opt, run_mlir, count_op)

_n = 0
_np = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _n, _np
    _n += 1
    if cond:
        _np += 1
    suffix = f"（{detail}）" if detail else ""
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{suffix}")


def hr(title: str) -> None:
    print("\n== " + title + " ==")


# ------------------------------------------------------------
# 工具：随机视图链（F 段用）
# ------------------------------------------------------------

def random_view_chain(rng: random.Random) -> Graph:
    """arg(2,3) 或 (3,2) → 若干 transpose（恒为合法 perm）→ reshape 到 (6,)。"""
    g = Graph("rnd")
    x = g.arg((2, 3))
    cur = x
    for _ in range(rng.randint(1, 3)):
        cur = g.transpose(cur, (1, 0))
    cur = g.reshape(cur, (6,))
    g.returns = [cur]
    return g


# ============================================================
# A. 内存账本模型
# ============================================================

def sec_a() -> None:
    hr("A. 内存账本模型：bookkeeping 与 numpy 真实地址对账")

    g = Graph("a1")
    x = g.arg((2, 3))
    t = g.transpose(x, (1, 0))
    r = g.relu(t)
    g.returns = [r]
    tr = run_trace(g.clone(), seed=101, mode="view", verbose=False)

    # A1: transpose 视图不换 buffer、strides 按置换重排
    ev = [e for e in tr.events if "transpose" in e]
    check("A1 视图世界 transpose 0 字节、strides (3,1)->(1,3)",
          tr.traffic == 48 and any("strides(3, 1)->(1, 3)" in e for e in ev))

    # A2: MemRec 的 offset 与 numpy 视图的真实字节地址一致
    tr2 = run_trace(g.clone(), seed=101, mode="view", verbose=False)
    arr = tr2.outputs[0]
    mem = tr2.out_mem[0]
    flat = arr.reshape(-1)
    base = arr.base if arr.base is not None else arr
    # relu 分配的新 buffer：offset 0、C-连续
    check("A2 MemRec(offset=0, C-连续) 与 numpy 视图一致",
          mem.offset == 0 and mem.strides == (2, 1)
          and arr.flags["C_CONTIGUOUS"]
          and int(arr.ctypes.data - np.asarray(base).ctypes.data) == 0)

    # A3: 物理世界同一张图 traffic 恰为 3 倍（transpose+relu+reshape 链）
    g3 = Graph("a3")
    x3 = g3.arg((2, 3))
    t3 = g3.transpose(x3, (1, 0))
    r3 = g3.relu(t3)
    s3 = g3.reshape(r3, (6,))
    g3.returns = [s3]
    tv = run_trace(g3.clone(), seed=101, mode="view", verbose=False)
    tp = run_trace(g3.clone(), seed=101, mode="physical", verbose=False)
    check("A3 同图两世界 traffic 48B vs 144B、输出逐位相等",
          tv.traffic == 48 and tp.traffic == 144 and tv.allocs == 1
          and tp.allocs == 3
          and np.array_equal(tv.outputs[0], tp.outputs[0]))

    # A4: 视图世界 reshape 只在输入 C-连续时 0 字节
    g4 = Graph("a4")
    x4 = g4.arg((2, 3))
    t4 = g4.transpose(x4, (1, 0))          # (3,2) 非连续视图
    s4 = g4.reshape(t4, (6,))
    g4.returns = [s4]
    tr4 = run_trace(g4.clone(), seed=101, mode="view", verbose=False)
    check("A4 非连续输入上的 reshape 是拷贝（48B）",
          tr4.traffic == 48 and any("非连续" in e for e in tr4.events))

    g5 = Graph("a5")
    x5 = g5.arg((2, 3))
    s5 = g5.reshape(x5, (6,))              # 输入连续
    g5.returns = [s5]
    tr5 = run_trace(g5.clone(), seed=101, mode="view", verbose=False)
    check("A5 连续输入上的 reshape 是 0 字节视图", tr5.traffic == 0)

    # A6: force_physical 单点物化（R5 的机制前提）
    g6 = Graph("a6")
    x6 = g6.arg((2, 3))
    t6 = g6.transpose(x6, (1, 0))
    r6 = g6.relu(t6)
    g6.returns = [r6]
    tr6 = run_trace(g6.clone(), seed=101, mode="view",
                    force_physical={t6}, verbose=False)
    check("A6 force_physical 让单个 transpose 物化（traffic 96B = "
          "转置 48B + relu 48B）",
          tr6.traffic == 96 and any("物化" in e and "transpose" in e
                                    for e in tr6.events))


# ============================================================
# B. 反例回归（独立种子）
# ============================================================

def sec_b() -> None:
    hr("B. 反例回归：R1–R7 关键事实复测（独立种子）")

    # R1: cast 往返丢位
    g = Graph("b1")
    x = g.arg((3, 4))
    c1 = g.cast(x, "f32", "f16")
    c2 = g.cast(c1, "f16", "f32")
    g.returns = [c2]
    g2 = Graph("b1x")
    x2 = g2.arg((3, 4))
    g2.returns = [x2]
    a, b = g.eval(seed=202)[0], g2.eval(seed=202)[0]
    n_diff = int((a != b).sum())
    check("B1 R1 复测：f32→f16→f32 往返 12 元素几乎全变（≥10/12）",
          n_diff >= 10, f"{n_diff}/12")

    # R2: 双层同目标 reshape 透传错版
    g3 = Graph("b2")
    x3 = g3.arg((8,))
    r1 = g3.reshape(x3, (2, 4))
    r2 = g3.reshape(r1, (2, 4))
    g3.returns = [r2]
    g3b = g3.clone()
    merge_adjacent_reshapes_buggy(g3b)
    s_bug, _ = g3b.infer_shapes()
    check("B2 R2 复测：透传错版把 return shape 从 (2,4) 变 (8,)",
          s_bug[g3b.returns[0]] == (8,)
          and g3.eval(seed=203)[0].shape == (2, 4))

    # R3: copy 消除的写集合漂移
    g4 = Graph("b3")
    x4 = g4.arg((3, 4))
    y4 = g4.copy(x4)
    z4 = g4.relu(y4)
    g4.returns = [x4, z4]
    keep = run_trace(g4.clone(), seed=204, mode="view",
                     inplace_elementwise=True, verbose=False)
    g4b = g4.clone()
    eliminate_copy_naive(g4b)
    gone = run_trace(g4b.clone(), seed=204, mode="view",
                     inplace_elementwise=True, verbose=False)
    check("B3 R3 复测：消除 copy 后输入缓冲被写、输出被污染",
          keep.input_bufs_written == set()
          and gone.input_bufs_written == {-1}
          and not np.array_equal(keep.outputs[0], gone.outputs[0]))

    # R4: store 的副作用
    g5 = Graph("b4")
    x5 = g5.arg((3, 4))
    s5 = g5.store(x5)
    g5.returns = []
    full = run_trace(g5.clone(), seed=205, mode="view", verbose=False)
    g5b = g5.clone()
    naive_dce(g5b)
    gone4 = run_trace(g5b.clone(), seed=205, mode="view", verbose=False)
    g5c = g5.clone()
    guarded_dce(g5c)
    kept4 = run_trace(g5c.clone(), seed=205, mode="view", verbose=False)
    check("B4 R4 复测：naive 删 store（G 空）、guarded 保留（G 有数据）",
          g5b.by_name(s5) is None and gone4.ext_state is None
          and full.ext_state is not None and kept4.ext_state is not None
          and g5c.by_name(s5) is not None)

    # R5: 双消费者物化摊销
    def build_r5() -> Graph:
        g6 = Graph("b5")
        a6 = g6.arg((2, 3))
        v6 = g6.transpose(a6, (1, 0))
        p6 = g6.transpose(v6, (0, 1))
        s1 = g6.reshape(p6, (6,))
        s2 = g6.reshape(p6, (3, 2))
        g6.returns = [s1, s2]
        return g6

    g6 = build_r5()
    p_name = g6.ops[2].name
    phys_keep = run_trace(g6.clone(), seed=206, mode="view",
                          force_physical={p_name}, verbose=False)
    g6b = build_r5()
    eliminate_identity_transpose_naive(g6b)
    phys_gone = run_trace(g6b.clone(), seed=206, mode="view",
                          force_physical={p_name}, verbose=False)
    check("B5 R5 复测：双消费者下消除物化点 traffic 翻倍（48→96B）",
          phys_keep.traffic == 48 and phys_gone.traffic == 96
          and all(np.array_equal(a, b) for a, b in
                  zip(phys_keep.outputs, phys_gone.outputs)))

    # R6: 多使用者传播
    g7 = Graph("b6")
    x7 = g7.arg((3, 4))
    r7 = g7.relu(x7)
    t7 = g7.transpose(r7, (1, 0))
    g7.returns = [r7, t7]
    g7b = g7.clone()
    push_transpose_through_elementwise(g7b, respect_unique=False)
    check("B6 R6 复测：强行传播 op +1、转置数不变、值等价",
          g7b.n_ops() == g7.n_ops() + 1
          and g7b.count_kind("transpose") == g7.count_kind("transpose")
          and all(np.array_equal(a, b) for a, b in
                  zip(g7.eval(seed=207), g7b.eval(seed=207))))

    # R7: reduce 传播 —— axis 跟着 perm 换才等价
    g8 = Graph("b7")
    x8 = g8.arg((3, 4))
    rs8 = g8.reduce_sum(x8, axis=1)       # (3,1)
    t8 = g8.transpose(rs8, (1, 0))        # (1,3)
    g8.returns = [t8]
    lhs = g8.eval(seed=208)[0]
    # 转置不变量：新 axis = inv_perm[旧 axis]；对换 perm=(1,0) 时两者相等
    fixed = _build_transposed_reduce(0).eval(seed=208)[0]   # axis=0（换过）
    wrong = _build_transposed_reduce(1).eval(seed=208)[0]   # axis=1（原样）
    check("B7 R7 复测：axis 跟着 perm 换才等价（原样 axis 不等）",
          lhs.shape == (1, 3) and fixed.shape == (1, 3)
          and np.array_equal(lhs, fixed)
          and wrong.shape == (4, 1) and not np.array_equal(lhs, wrong))


def _build_transposed_reduce(axis: int) -> Graph:
    g = Graph("b7n")
    x = g.arg((3, 4))
    t = g.transpose(x, (1, 0))            # (4,3)
    rs = g.reduce_sum(t, axis=axis)
    g.returns = [rs]
    return g


# ============================================================
# C. 守卫测试：反例上拒绝、正例上触发
# ============================================================

def sec_c() -> None:
    hr("C. 守卫测试：每条 Pattern 在反例上拒绝、在正例上触发")

    # C1: noop cast —— f32→f16 拒绝；f32→f32 触发
    g = Graph("c1")
    x = g.arg((2, 3))
    g.cast(x, "f32", "f16")
    g.returns = [g.ops[-1].name]
    check("C1 eliminate_noop_cast 拒绝 f32→f16",
          not eliminate_noop_cast(g))
    g2 = Graph("c1b")
    x2 = g2.arg((2, 3))
    c2 = g2.cast(x2, "f32", "f32")
    g2.returns = [c2]
    check("C2 eliminate_noop_cast 触发 f32→f32 并透传",
          eliminate_noop_cast(g2) and g2.returns == [x2])

    # C3: cast pair 诱人版会触发（并制造数值错误）——验证它确实是"诱人"的
    g3 = Graph("c3")
    x3 = g3.arg((2, 3))
    d1 = g3.cast(x3, "f32", "f16")
    d2 = g3.cast(d1, "f16", "f32")
    g3.returns = [d2]
    g3b = g3.clone()
    check("C3 诱人版 cast 对消会触发（反例之所以是陷阱）",
          eliminate_cast_pair_naive(g3b) and g3b.returns == [x3])

    # C4: reshape 合并守卫版 vs 错版
    g4 = Graph("c4")
    x4 = g4.arg((6,))
    e1 = g4.reshape(x4, (2, 3))
    e2 = g4.reshape(e1, (3, 2))
    g4.returns = [e2]
    g4b = g4.clone()
    merge_adjacent_reshapes(g4b)
    naive_dce(g4b)
    check("C4 守卫版合并成一层且值等价",
          g4b.count_kind("reshape") == 1
          and np.array_equal(g4b.eval(seed=301)[0], g4.eval(seed=301)[0]))

    # C5: 传播 C1/C2 双门
    g5 = Graph("c5")
    x5 = g5.arg((2, 3))
    rs = g5.reduce_sum(x5, axis=0)
    t5 = g5.transpose(rs, (1, 0))
    g5.returns = [t5]
    check("C5 传播拒绝 reduce_sum（C1 白名单）",
          not push_transpose_through_elementwise(g5)
          and "reduce_sum" not in ELEMENTWISE_WHITELIST)
    g6 = Graph("c6")
    x6 = g6.arg((2, 3))
    r6 = g6.relu(x6)
    t6 = g6.transpose(r6, (1, 0))
    g6.returns = [t6, r6]
    check("C6 传播拒绝多使用者（C2 唯一使用者门）",
          not push_transpose_through_elementwise(g6))
    g7 = Graph("c7")
    x7 = g7.arg((2, 3))
    r7 = g7.relu(x7)
    t7 = g7.transpose(r7, (1, 0))
    g7.returns = [t7]
    g7b = g7.clone()
    ok = push_transpose_through_elementwise(g7b)
    check("C7 单使用者 relu 传播触发且值等价",
          ok and all(np.array_equal(a, b) for a, b in
                     zip(g7.eval(seed=302), g7b.eval(seed=302))))

    # C8: 转置合并守卫（非恒等合并成一次）
    g8 = Graph("c8")
    x8 = g8.arg((2, 3))
    t1 = g8.transpose(x8, (1, 0))
    t2 = g8.transpose(t1, (1, 0))
    g8.returns = [t2]
    g8b = g8.clone()
    merge_adjacent_transposes(g8b)
    naive_dce(g8b)
    check("C8 T(T(x)) 恒等透传后图只剩 arg",
          g8b.n_ops() == 0 and np.array_equal(
              g8b.eval(seed=303)[0], g8.eval(seed=303)[0]))


# ============================================================
# D. DCE 副作用压力测试
# ============================================================

def sec_d() -> None:
    hr("D. DCE 副作用：随机图上 naive 丢 store、guarded 不丢")

    rng = random.Random(7070)
    n_bad = 0
    for trial in range(30):
        g = Graph(f"d{trial}")
        x = g.arg((2, 3))
        cur = x
        for _ in range(rng.randint(0, 3)):
            if rng.random() < 0.5:
                cur = g.transpose(cur, (1, 0))
            else:
                cur = g.relu(cur)
        if rng.random() < 0.7:
            g.store(cur)
        if rng.random() < 0.5:
            g.returns = [cur]
        else:
            g.returns = []
        g2 = g.clone()
        naive_dce(g2)
        if any(op.kind == "store" for op in g.ops):
            has_store_after_naive = any(op.kind == "store"
                                        for op in g2.ops)
            if has_store_after_naive:
                n_bad += 1        # naive 竟然保留了（不应发生）
            g3 = g.clone()
            guarded_dce(g3)
            if not any(op.kind == "store" for op in g3.ops):
                n_bad += 1        # guarded 竟然丢了（不应发生）
    check("D1 30 组随机图：有 store 时 naive 必删、guarded 必留",
          n_bad == 0)

    # D2: 值等价性——guarded DCE 后图的可返回值不变
    g = Graph("d2")
    x = g.arg((2, 3))
    r = g.relu(x)
    g.store(x)
    g.returns = [r]
    g2 = g.clone()
    guarded_dce(g2)
    check("D2 guarded DCE 不动 return 可达集（值不变）",
          np.array_equal(g.eval(seed=401)[0], g2.eval(seed=401)[0])
          and any(op.kind == "store" for op in g2.ops))


# ============================================================
# E. 结构哈希规范化
# ============================================================

def sec_e() -> None:
    hr("E. 结构哈希：改名不改结构 → 哈希相等")

    def build(tag: str, base: int) -> Graph:
        g = Graph(tag)
        x = g.arg((2, 3))
        t = g.transpose(x, (1, 0))
        r = g.relu(t)
        s = g.reshape(r, (6,))
        g.returns = [s]
        # 手工重命名（模拟另一套 SSA 编号）
        for i, op in enumerate(g.ops):
            old = op.name
            new = f"%{base + i}"
            op.name = new
            for op2 in g.ops:
                op2.inputs = [new if n == old else n
                              for n in op2.inputs]
            g.returns = [new if rr == old else rr for rr in g.returns]
        return g

    g1 = build("e1", 100)
    g2 = build("e2", 500)
    check("E1 改名不改结构 → state_hash 相等",
          g1.state_hash() == g2.state_hash())
    g3 = build("e3", 900)
    g3.ops[1].perm = (0, 1)     # 改 transpose 的 perm → 结构变了
    check("E2 perm 属性不同 → state_hash 不同",
          g1.state_hash() != g3.state_hash())
    # E3: 视图/物理两个世界共用同一张图（同一哈希）——命题的形式前提
    tr_v = run_trace(g1.clone(), seed=501, mode="view", verbose=False)
    tr_p = run_trace(g1.clone(), seed=501, mode="physical", verbose=False)
    check("E3 同一 state_hash 的图两世界 traffic 不同、值相等",
          tr_v.traffic != tr_p.traffic
          and np.array_equal(tr_v.outputs[0], tr_p.outputs[0]))


# ============================================================
# F. 随机性质：值等价但内存轨迹不同
# ============================================================

def sec_f() -> None:
    hr("F. 随机性质：随机视图链上命题成立（值等价、账本可分）")

    rng = random.Random(8080)
    n_prop = 0
    n_tot = 0
    for trial in range(40):
        g = random_view_chain(rng)
        tv = run_trace(g.clone(), seed=trial, mode="view", verbose=False)
        tp = run_trace(g.clone(), seed=trial, mode="physical",
                       verbose=False)
        n_tot += 1
        if (np.array_equal(tv.outputs[0], tp.outputs[0])
                and tv.traffic != tp.traffic):
            n_prop += 1
    check("F1 40 组随机视图链：两世界值全等且 traffic 全不同",
          n_prop == n_tot, f"{n_prop}/{n_tot}")

    # F2: 三明治相消的随机化——值等价、视图世界输出布局可能改变
    n_layout = 0
    for trial in range(20):
        g = Graph(f"f2{trial}")
        x = g.arg((2, 3))
        t1 = g.transpose(x, (1, 0))
        r = g.relu(t1)
        t2 = g.transpose(r, (1, 0))
        g.returns = [t2]
        g2 = g.clone()
        push_transpose_through_elementwise(g2)
        merge_adjacent_transposes(g2)
        naive_dce(g2)
        a = run_trace(g.clone(), seed=trial, mode="view", verbose=False)
        b = run_trace(g2.clone(), seed=trial, mode="view", verbose=False)
        if (np.array_equal(a.outputs[0], b.outputs[0])
                and a.out_mem[0].strides == (1, 2)
                and b.out_mem[0].strides == (3, 1)):
            n_layout += 1
    check("F2 20 组三明治：相消值等价且输出 strides (1,2)→(3,1)",
          n_layout == 20, f"{n_layout}/20")


# ============================================================
# G. MLIR 探针
# ============================================================

def sec_g() -> None:
    hr("G. MLIR 探针：stock 管道计数断言")

    if find_mlir_opt() is None:
        print("[SKIP] mlir-opt 不可用，本段跳过")
        return

    _, out = run_mlir(HERE / "probe_cast_roundtrip.mlir", ["--canonicalize"])
    check("G1 truncf+extf 往返不被 --canonicalize 折叠",
          count_op(out, "arith.truncf") == 1
          and count_op(out, "arith.extf") == 1)

    _, out = run_mlir(HERE / "probe_reshape_chain.mlir", ["--canonicalize"])
    check("G2 tensor.reshape 链不被 --canonicalize 合并",
          count_op(out, "tensor.reshape") == 2)

    _, out1 = run_mlir(HERE / "probe_copy_identity.mlir", ["--canonicalize"])
    _, out2 = run_mlir(HERE / "probe_copy_identity.mlir", ["--cse"])
    check("G3 memref.copy 在 canonicalize / cse 下都保留",
          count_op(out1, "memref.copy") == 1
          and count_op(out2, "memref.copy") == 1)

    _, out1 = run_mlir(HERE / "probe_side_effect.mlir", ["--cse"])
    _, out2 = run_mlir(HERE / "probe_side_effect.mlir", ["--canonicalize"])
    check("G4 store 保留、死的纯 addf 被删（两个 pass 一致）",
          count_op(out1, "memref.store") == 1
          and count_op(out2, "memref.store") == 1
          and count_op(out1, "arith.addf") == 0
          and count_op(out2, "arith.addf") == 0)

    _, out1 = run_mlir(HERE / "probe_identity_transpose.mlir",
                       ["--canonicalize"])
    _, out2 = run_mlir(HERE / "probe_identity_transpose.mlir", ["--cse"])
    check("G5 恒等排列 linalg.transpose 两个 pass 下都保留",
          count_op(out1, "linalg.transpose") == 1
          and count_op(out2, "linalg.transpose") == 1)


def main() -> int:
    print("第 70 天验收测试：反例集 + 内存账本（独立用例）")
    sec_a()
    sec_b()
    sec_c()
    sec_d()
    sec_e()
    sec_f()
    sec_g()
    print(f"\n汇总：PASS {_np} / FAIL {_n - _np}（共 {_n} 项）")
    return 0 if _np == _n else 1


if __name__ == "__main__":
    raise SystemExit(main())
