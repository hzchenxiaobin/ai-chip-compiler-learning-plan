#!/usr/bin/env python3
"""test_combo_lab.py —— 第 69 天（图优化组合测试）独立验收测试。

与 combo_lab.py 共享同一套 mini IR / Pattern / PassManager 实现，
但用例独立编写，按 A–G 七段验收（与 Day 68 的 test_layout_prop.py 同风格）：

  A  Verifier：非法 perm / reshape numel / add shape 必须被拦下
  B  Pattern 单测：每条规则最小触发 + 守卫拒绝（白名单 / 唯一使用者 /
     无操作 Cast 限定 / 多使用者门）
  C  组合用例：10-op 混合链 -> 稳定 IR（轮次 / 终点形态 / 数值 / 幂等 / 哈希）
  D  顺序研究：传播×融合竞争出两个不动点；cast×融合合流到同一终点
  E  无限变换：规则环 / undo 对 / 哈希陷阱 / 单调配度驯服
  F  压力对拍：60 组随机混合图（独立种子，与主实验的 200 组不同）
  G  MLIR 探针：4 个 stock 管道探针的计数断言（无 mlir-opt 则跳过）

运行：python3 test_combo_lab.py   （在 code/ 目录下）
"""

from __future__ import annotations

import random
import sys
from itertools import permutations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from combo_lab import (  # noqa: E402
    ELEMENTWISE_WHITELIST, RECOMMENDED_PATTERNS, SWAP_RANK, Graph, Op,
    canonical_swap, eliminate_noop_cast, eliminate_transparent_reshape,
    find_mlir_opt, fold_transpose_into_constant, fuse_add_relu,
    graphs_equal_num, inversions, merge_adjacent_reshapes,
    merge_adjacent_transposes, numel, op_stats, push_transpose_through_elementwise,
    run_passes, run_passes_traced, swap_adjacent, t_shape, unfuse_add_relu,
)

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


def hr(title: str) -> None:
    print("\n" + "-" * 68)
    print(title)
    print("-" * 68)


# ============================================================
# A. Verifier
# ============================================================

def test_verifier() -> None:
    hr("A. Verifier")
    g = Graph("bad_perm")
    x = g.arg((2, 3))
    t = g.add_op("transpose", [x], perm=(0, 0))
    g.returns = [t]
    _, errs = g.infer_shapes()
    check("A1 非法 perm 被拦下", any("V1" in e for e in errs), str(errs))

    g = Graph("bad_rank")
    x = g.arg((2, 3))
    t = g.add_op("transpose", [x], perm=(0, 1, 2))
    g.returns = [t]
    _, errs = g.infer_shapes()
    check("A2 perm 与 rank 不符被拦下", any("V1" in e for e in errs))

    g = Graph("bad_reshape")
    x = g.arg((2, 3))
    r = g.add_op("reshape", [x], new_shape=(4, 4))
    g.returns = [r]
    _, errs = g.infer_shapes()
    check("A3 reshape numel 不守恒被拦下", any("V4" in e for e in errs))

    g = Graph("bad_add")
    x = g.arg((2, 3))
    y = g.arg((3, 2))
    a = g.add(x, y)
    g.returns = [a]
    _, errs = g.infer_shapes()
    check("A4 add 两侧 shape 不一致被拦下", any("V2" in e for e in errs))

    g = Graph("ok_chain")
    x = g.arg((2, 3, 4))
    t = g.transpose(x, (2, 0, 1))
    r = g.relu(t)
    g.returns = [r]
    _, errs = g.infer_shapes()
    check("A5 合法链零错误", not errs)
    shapes, _ = g.infer_shapes()
    check("A6 transpose shape 推导正确", shapes[t] == (4, 2, 3),
          f"{shapes[t]}")


# ============================================================
# B. Pattern 单测（触发 + 守卫）
# ============================================================

def test_patterns() -> None:
    hr("B. Pattern 单测")

    # B1 转置合并：互逆 -> 透传
    g = Graph("b1")
    x = g.arg((2, 3))
    t1 = g.transpose(x, (1, 0))
    t2 = g.transpose(t1, (1, 0))
    g.returns = [t2]
    ok = merge_adjacent_transposes(g)
    check("B1 互逆转置合并为透传", ok and g.returns == [x]
          and g.count_kind("transpose") == 0)

    # B2 转置合并：一般情形 r[i]=p1[p2[i]]
    g = Graph("b2")
    x = g.arg((2, 3, 4))
    t1 = g.transpose(x, (1, 2, 0))
    t2 = g.transpose(t1, (1, 2, 0))
    g.returns = [t2]
    ok = merge_adjacent_transposes(g)
    t = [op for op in g.ops if op.kind == "transpose"]
    r_expect = (2, 0, 1)   # p1[p2[i]] = (p1[1], p1[2], p1[0])
    check("B2 一般合并排列正确", ok and len(t) == 1 and t[0].perm == r_expect,
          f"r={t[0].perm if t else None}")

    # B3 reshape 合并：外层目标
    g = Graph("b3")
    x = g.arg((2, 3))
    r1 = g.reshape(x, (6,))
    r2 = g.reshape(r1, (3, 2))
    g.returns = [r2]
    ok = merge_adjacent_reshapes(g)
    rr = [op for op in g.ops if op.kind == "reshape"]
    check("B3 reshape 合并到外层目标", ok and len(rr) == 1
          and rr[0].new_shape == (3, 2) and rr[0].inputs == [x])

    # B3' 同目标双层 reshape 不能透传成 x（Reshape(Reshape(x,t),t)=Reshape(x,t)）
    g = Graph("b3p")
    x = g.arg((2, 3))
    r1 = g.reshape(x, (6,))
    r2 = g.reshape(r1, (6,))
    g.returns = [r2]
    merge_adjacent_reshapes(g)
    rr = [op for op in g.ops if op.kind == "reshape"]
    okn, _ = graphs_equal_num(Graph("b3p0"), g) if False else (True, "")
    g0 = Graph("b3p0")
    x0 = g0.arg((2, 3))
    r01 = g0.reshape(x0, (6,))
    r02 = g0.reshape(r01, (6,))
    g0.returns = [r02]
    okn, _ = graphs_equal_num(g0, g)
    check("B3' 同目标双层 reshape 合并成单层（不是透传）",
          len(rr) == 1 and rr[0].new_shape == (6,) and okn)

    # B4 透明 reshape
    g = Graph("b4")
    x = g.arg((2, 3))
    r = g.reshape(x, (2, 3))
    g.returns = [r]
    ok = eliminate_transparent_reshape(g)
    check("B4 同 shape reshape 透传", ok and g.returns == [x])

    # B5 noop cast 透传；f32->f16 不动
    g = Graph("b5")
    x = g.arg((2, 3))
    c = g.cast(x, "f32", "f32")
    r = g.relu(c)
    g.returns = [r]
    ok = eliminate_noop_cast(g)
    check("B5 noop cast 透传", ok and g.returns == [r]
          and g.count_kind("cast") == 0)

    g = Graph("b5n")
    x = g.arg((2, 3))
    c = g.cast(x, "f32", "f16")
    r = g.relu(c)
    g.returns = [r]
    ok = eliminate_noop_cast(g)
    check("B5' 精度改变（f32->f16）的 cast 不消除",
          not ok and g.count_kind("cast") == 1)

    # B6 常量折叠
    g = Graph("b6")
    c = g.const([[1.0, -2.0], [3.0, -4.0]])
    t = g.transpose(c, (1, 0))
    g.returns = [t]
    ok = fold_transpose_into_constant(g)
    c2 = g.by_name(g.returns[0])
    check("B6 transpose(常量) 折成转置后的常量",
          ok and c2.kind == "const"
          and np.array_equal(c2.value, np.array([[1.0, 3.0],
                                                 [-2.0, -4.0]],
                                                dtype=np.float32)))

    # B7 融合 + 多使用者门
    g = Graph("b7")
    x = g.arg((2, 3))
    y = g.arg((2, 3))
    a = g.add(x, y)
    r = g.relu(a)
    g.returns = [r]
    ok = fuse_add_relu(g)
    check("B7 add+relu 融合", ok and g.count_kind("fused_add_relu") == 1)

    g = Graph("b7n")
    x = g.arg((2, 3))
    y = g.arg((2, 3))
    a = g.add(x, y)
    r = g.relu(a)
    z = g.neg(a)          # add 的第二个使用者
    g.returns = [r, z]
    ok = fuse_add_relu(g)
    check("B7' 多使用者的 add 拒绝融合（Day 52 的门）",
          not ok and g.count_kind("fused_add_relu") == 0)

    # B8 传播 + 白名单 + 唯一使用者
    g = Graph("b8")
    x = g.arg((2, 3))
    r = g.relu(x)
    t = g.transpose(r, (1, 0))
    g.returns = [t]
    ok = push_transpose_through_elementwise(g)
    ks = g.kinds_seq()
    check("B8 T(relu(x)) -> relu(T(x))", ok and ks == ("transpose", "relu"))

    g = Graph("b8w")
    x = g.arg((2, 3))
    r = g.reshape(x, (3, 2))      # reshape 不在白名单
    t = g.transpose(r, (1, 0))
    g.returns = [t]
    ok = push_transpose_through_elementwise(g)
    check("B8' reshape 挡住传播（白名单）",
          not ok and g.kinds_seq() == ("reshape", "transpose"))

    g = Graph("b8u")
    x = g.arg((2, 3))
    r = g.relu(x)
    t = g.transpose(r, (1, 0))
    z = g.neg(r)                   # relu 的第二个使用者
    g.returns = [t, z]
    ok = push_transpose_through_elementwise(g)
    check("B8'' 多使用者的 E 拒绝传播（不增殖）",
          not ok and g.kinds_seq() == ("relu", "transpose", "neg"))

    # B9 白名单内容
    check("B9 白名单 = relu/neg/floor（fused 不在内）",
          ELEMENTWISE_WHITELIST == ("relu", "neg", "floor")
          and "fused_add_relu" not in ELEMENTWISE_WHITELIST)


# ============================================================
# C. 组合用例：混合链 -> 稳定 IR
# ============================================================

def build_mixed_chain() -> Graph:
    g = Graph("mixed_chain")
    x = g.arg((2, 3))
    y = g.arg((2, 3))
    t1 = g.transpose(x, (1, 0))
    t2 = g.transpose(t1, (1, 0))
    c = g.cast(t2, "f32", "f32")
    a = g.add(c, y)
    r = g.relu(a)
    big_t = g.transpose(r, (1, 0))
    s1 = g.reshape(big_t, (6,))
    s2 = g.reshape(s1, (3, 2))
    g.returns = [s2]
    return g


def test_combo_case() -> None:
    hr("C. 组合用例（10-op 混合链 -> 稳定 IR）")
    g0 = build_mixed_chain()
    check("C1 初始 10 op / 8 计算 op", g0.n_all() == 10 and g0.n_ops() == 8)
    check("C2 初始冗余盘点（T3 / cast1 / reshape2）",
          g0.count_kind("transpose") == 3
          and g0.count_kind("cast") == 1
          and g0.count_kind("reshape") == 2)

    g = g0.copy()
    rounds, verdict = run_passes(g, RECOMMENDED_PATTERNS)
    check("C3 收敛到 fixpoint", verdict == "fixpoint", f"{rounds} 轮")
    check("C4 轮次 <= 8", rounds <= 8, f"{rounds} 轮")
    check("C5 终点形态 = fused + 1 个卡住的转置",
          g.kinds_seq() == ("fused_add_relu", "transpose"),
          f"{g.kinds_seq()}")
    check("C6 总 op 10 -> 4", g.n_all() == 4, f"{g.n_all()}")
    ok, msg = graphs_equal_num(g0, g)
    check("C7 数值逐位相等", ok, msg)

    h = g.state_hash()
    r2, v2 = run_passes(g, RECOMMENDED_PATTERNS)
    check("C8 幂等：二次运行零轮次", r2 == 0 and v2 == "fixpoint")
    check("C9 哈希不变", g.state_hash() == h)
    check("C10 五种冗余清理结果（cast 0 / reshape 0 / T 2 消）",
          g.count_kind("cast") == 0 and g.count_kind("reshape") == 0
          and g.count_kind("transpose") == 1)


# ============================================================
# D. 顺序研究
# ============================================================

def build_window() -> Graph:
    g = Graph("window")
    x = g.arg((2, 3))
    y = g.arg((2, 3))
    a = g.add(x, y)
    r = g.relu(a)
    t = g.transpose(r, (1, 0))
    g.returns = [t]
    return g


def test_order() -> None:
    hr("D. 顺序研究")
    ord_push = [push_transpose_through_elementwise, fuse_add_relu]
    ord_fuse = [fuse_add_relu, push_transpose_through_elementwise]

    ga = build_window()
    run_passes(ga, ord_push)
    gb = build_window()
    run_passes(gb, ord_fuse)
    check("D1 传播在前：relu(T(add))，5 op", ga.n_all() == 5
          and ga.kinds_seq() == ("add", "transpose", "relu"),
          f"{ga.kinds_seq()}")
    check("D2 融合在前：T(fused)，4 op", gb.n_all() == 4
          and gb.kinds_seq() == ("fused_add_relu", "transpose"),
          f"{gb.kinds_seq()}")
    check("D3 两个不动点不同（哈希不等）",
          ga.state_hash() != gb.state_hash())
    ok_a, _ = graphs_equal_num(build_window(), ga)
    ok_b, _ = graphs_equal_num(build_window(), gb)
    check("D4 两个不动点数值都对", ok_a and ok_b)

    # 合流对：cast x 融合
    def build_cast_between() -> Graph:
        g = Graph("cast_between")
        x = g.arg((2, 3))
        y = g.arg((2, 3))
        a = g.add(x, y)
        c = g.cast(a, "f32", "f32")
        r = g.relu(c)
        g.returns = [r]
        return g

    g1 = build_cast_between()
    run_passes(g1, [eliminate_noop_cast, fuse_add_relu])
    g2 = build_cast_between()
    run_passes(g2, [fuse_add_relu, eliminate_noop_cast])
    check("D5 cast×融合合流：两个顺序同一终点",
          g1.state_hash() == g2.state_hash()
          and g1.kinds_seq() == ("fused_add_relu",))


# ============================================================
# E. 无限变换与驯服
# ============================================================

def test_infinite() -> None:
    hr("E. 无限变换与驯服")
    perm3 = (2, 0, 1)
    swap_rules = []
    for a, b in [("transpose", "relu"), ("transpose", "floor"),
                 ("relu", "floor")]:
        swap_rules.append(lambda g, a=a, b=b: swap_adjacent(g, a, b))
        swap_rules.append(lambda g, a=a, b=b: swap_adjacent(g, b, a))

    def build_chain3(order3) -> Graph:
        g = Graph("chain3")
        x = g.arg((2, 3, 4))
        cur = x
        for kind in order3:
            if kind == "transpose":
                cur = g.transpose(cur, perm3)
            else:
                cur = g.add_op(kind, [cur])
        g.returns = [cur]
        return g

    # E1 规则环：6 个起点全部振荡
    all_osc = True
    for order3 in permutations(["transpose", "relu", "floor"]):
        g = build_chain3(order3)
        _, vv = run_passes(g, swap_rules, max_rounds=30)
        if vv != "oscillation":
            all_osc = False
    check("E1 6 个起点全部 oscillation（无不动点可达）", all_osc)

    # E2 每条交换规则语义正确（振荡中数值不变）
    nums_ok = True
    for order3 in permutations(["transpose", "relu", "floor"]):
        g = build_chain3(order3)
        g0 = g.copy()
        for _ in range(6):
            for p in swap_rules:
                if p(g):
                    break
        okn, _ = graphs_equal_num(g0, g)
        if not okn:
            nums_ok = False
    check("E2 交换规则数值始终不变", nums_ok)

    # E3 undo 对
    def build_fuse_case() -> Graph:
        g = Graph("fuse_case")
        x = g.arg((2, 3))
        y = g.arg((2, 3))
        a = g.add(x, y)
        r = g.relu(a)
        g.returns = [r]
        return g

    g = build_fuse_case()
    rr, vv = run_passes(g, [fuse_add_relu, unfuse_add_relu], max_rounds=30)
    check("E3 fuse/unfuse 同场 -> oscillation（2 轮检出）",
          vv == "oscillation" and rr == 2, f"{rr} 轮 {vv}")

    # E4 哈希陷阱：原始名哈希测不出环
    g = build_fuse_case()
    rr, vv = run_passes(g, [fuse_add_relu, unfuse_add_relu],
                        max_rounds=40, hash_fn=Graph.raw_hash)
    check("E4 原始 SSA 名哈希漏检（只能 max_rounds 兜底）",
          vv == "max_rounds" and rr == 40, f"{rr} 轮 {vv}")

    # E5 单调配度驯服：逆序数每步恰降 1，6 个起点同一规范形
    canon = set()
    mono_ok = True
    for order3 in permutations(["transpose", "relu", "floor"]):
        g = build_chain3(order3)
        g0 = g.copy()
        invs = [inversions(g)]
        while canonical_swap(g):
            invs.append(inversions(g))
        okn, _ = graphs_equal_num(g0, g)
        if not okn or invs[-1] != 0 or any(
                invs[i] - invs[i + 1] != 1 for i in range(len(invs) - 1)):
            mono_ok = False
        canon.add(g.state_hash())
    check("E5 逆序数每步恰降 1 且数值不变（单调配度）", mono_ok)
    check("E6 6 个起点到达同一规范形", len(canon) == 1, f"{len(canon)} 个")


# ============================================================
# F. 压力对拍（独立种子 60 组）
# ============================================================

def test_stress() -> None:
    hr("F. 压力对拍（60 组随机混合图，独立种子）")

    def all_shapes(num, rank):
        if rank == 1:
            return [(num,)]
        out = []
        for d in range(1, num + 1):
            if num % d == 0:
                for sub in all_shapes(num // d, rank - 1):
                    out.append((d,) + sub)
        return out

    shape_pool = {num: {k: all_shapes(num, k) for k in (1, 2, 3)}
                  for num in (6, 24)}
    rng = random.Random(20261112)
    n_ok = 0
    N = 60
    for gi in range(N):
        rank = rng.choice([2, 3])
        base_shape = (2, 3) if rank == 2 else (2, 3, 4)
        g = Graph(f"t{gi}")
        cur = g.arg(base_shape)
        if rng.random() < 0.30:
            cur = g.add(cur, g.arg(base_shape))
        elif rng.random() < 0.15:
            cval = (np.arange(numel(base_shape), dtype=np.float32)
                    .reshape(base_shape) - numel(base_shape) / 2)
            cur = g.const(cval)
        shape = base_shape
        for _ in range(rng.randint(4, 9)):
            kind = rng.choice(["transpose", "relu", "neg", "floor",
                               "cast", "reshape", "reshape"])
            if kind == "transpose":
                p = list(range(len(shape)))
                rng.shuffle(p)
                cur = g.transpose(cur, tuple(p))
                shape = t_shape(shape, tuple(p))
            elif kind == "cast":
                cur = g.cast(cur, "f32", "f32")
            elif kind == "reshape":
                pool = shape_pool[numel(shape)]
                shape = rng.choice(pool[rng.choice([1, 2, 3])])
                cur = g.reshape(cur, shape)
            else:
                cur = g.add_op(kind, [cur])
        g.returns = [cur]
        _, errs = g.infer_shapes()
        if errs:
            continue
        gb = g.copy()
        sb, sa = op_stats(g), None
        rr, vv = run_passes(g, RECOMMENDED_PATTERNS)
        sa = op_stats(g)
        rr2, _ = run_passes(g, RECOMMENDED_PATTERNS)
        okn, _ = graphs_equal_num(gb, g, seeds=(3, 4))
        if (vv == "fixpoint" and rr2 == 0 and okn
                and sa["ops"] <= sb["ops"]):
            n_ok += 1
    check("F1 60 组全部通过（数值/fixpoint/幂等/op 不增）",
          n_ok == N, f"{n_ok}/{N}")


# ============================================================
# G. MLIR 探针
# ============================================================

def test_mlir() -> None:
    hr("G. MLIR 探针")
    import combo_lab

    if find_mlir_opt() is None:
        print("  mlir-opt 不可用，G 段跳过")
        return

    def run(f, args):
        return combo_lab.run_mlir(HERE / f, args)

    def count(text, pat):
        return combo_lab.count_lines(text, pat)

    # G1 幂等
    _, o1 = run("idem_canon.mlir", ["--canonicalize"])
    _, o2 = run("idem_canon.mlir", ["--canonicalize", "--canonicalize"])
    check("G1 canonicalize 幂等（x2 == x1）", o1 == o2)
    check("G1' 恒等 tensor.cast 被删（剩余 0）", count(o1, "tensor.cast") == 0)

    _, o1 = run("idem_cse.mlir", ["--cse"])
    _, o2 = run("idem_cse.mlir", ["--cse", "--cse"])
    check("G2 cse 幂等（x2 == x1）", o1 == o2)
    check("G2' 两个相同 generic 合并成 1 个",
          count(o1, "linalg.generic") == 1)

    # G3 顺序敏感（arith）
    _, oa = run("order_arith.mlir", ["--canonicalize", "--cse"])
    _, ob = run("order_arith.mlir", ["--cse", "--canonicalize"])
    _, oc = run("order_arith.mlir", ["--cse", "--canonicalize", "--cse"])
    check("G3 canon->cse = 1 个 addf", count(oa, "arith.addf") == 1)
    check("G3' cse->canon = 2 个 addf（顺序敏感）",
          count(ob, "arith.addf") == 2)
    check("G3'' 补一趟 cse 追平", count(oc, "arith.addf") == 1)

    # G4 cast 解锁 cse
    _, oa = run("order_cast.mlir", ["--canonicalize", "--cse"])
    _, ob = run("order_cast.mlir", ["--cse", "--canonicalize"])
    check("G4 canon->cse = 1 个 generic（cast 先删）",
          count(oa, "linalg.generic") == 1)
    check("G4' cse->canon = 2 个 generic（CSE 先跑没机会）",
          count(ob, "linalg.generic") == 2)


def main() -> int:
    print(f"python {sys.version.split()[0]} / numpy {np.__version__}")
    test_verifier()
    test_patterns()
    test_combo_case()
    test_order()
    test_infinite()
    test_stress()
    test_mlir()
    print("\n" + "=" * 68)
    print(f"验收测试：通过 {PASS} 项，失败 {FAIL} 项")
    print("=" * 68)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
