#!/usr/bin/env python3
"""test_layout_prop.py —— 第 68 天（Layout 转换传播）独立验收测试。

独立于 layout_prop_lab.py 的实验场景：这里自建全部图例，从语义侧
（numpy 直算）和图侧（mini Pattern 跑 PassManager）两条线分别验证，
再互相对拍。全部通过则说明教程第 5 节的产出可用。

运行：python3 test_layout_prop.py   （在 code/ 目录下，退出码 0 = 全过）
"""

from __future__ import annotations

import sys

import numpy as np

from layout_prop_lab import (
    ELEMENTWISE_WHITELIST,
    Graph,
    fold_transpose_into_constant,
    graphs_equal_num,
    inv_perm,
    merge_adjacent_transposes,
    push_transpose_through_elementwise,
    push_transpose_through_elementwise_unchecked,
    push_transpose_up_through_elementwise,
    run_passes,
    traffic_report,
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


def sec(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> int:
    sec("A. 等价性：T(E(x)) == E(T(x)) 的语义验证（numpy 直算）")

    rng = np.random.default_rng(6801)
    ok_a = 0
    for _ in range(15):
        rank = int(rng.integers(2, 5))
        shape = tuple(int(rng.integers(2, 5)) for _ in range(rank))
        perm = tuple(rng.permutation(rank))
        x = (rng.standard_normal(shape) * 3).astype(np.float32)
        lhs = np.transpose(np.maximum(x, 0), perm)
        rhs = np.maximum(np.transpose(x, perm), 0)
        if np.array_equal(lhs, rhs):
            ok_a += 1
    check("A1 relu 穿转置等价（15 组随机 shape×perm）", ok_a == 15, f"{ok_a}/15")

    ok_a2 = 0
    for _ in range(15):
        rank = int(rng.integers(2, 5))
        shape = tuple(int(rng.integers(2, 5)) for _ in range(rank))
        perm = tuple(rng.permutation(rank))
        x = (rng.standard_normal(shape) * 3).astype(np.float32)
        if np.array_equal(np.transpose(-x, perm), -np.transpose(x, perm)):
            ok_a2 += 1
    check("A2 neg 穿转置等价（15 组）", ok_a2 == 15, f"{ok_a2}/15")

    # add：两侧同 perm 才等价；只 perm 一侧则不相等
    a = np.array([[1., -2., 3.], [-4., 5., -6.]], np.float32)
    b = np.array([[0.5, 1.5, -2.5], [3.0, -0.5, 2.0]], np.float32)
    p = (1, 0)
    both = np.transpose(a + b, p)
    each = np.transpose(a, p) + np.transpose(b, p)
    one_side = np.transpose(a, p) + b if np.transpose(a, p).shape == b.shape \
        else None
    check("A3 add 两侧同 perm 等价", np.array_equal(both, each))
    check("A4 add 只 perm 一侧不等或 shape 不匹配（不能只推一边）",
          one_side is None or not np.array_equal(both, one_side))

    # reduce 正确重映射：k' = p^-1(k)
    ok_a5 = 0
    for _ in range(15):
        rank = int(rng.integers(2, 5))
        shape = tuple(int(rng.integers(2, 5)) for _ in range(rank))
        perm = tuple(rng.permutation(rank))
        k = int(rng.integers(0, rank))
        x = (rng.standard_normal(shape) * 3).astype(np.float32)
        lhs = np.transpose(x.sum(axis=k, keepdims=True, dtype=np.float32),
                           perm)
        rhs = np.transpose(x, perm).sum(
            axis=inv_perm(perm)[k], keepdims=True, dtype=np.float32)
        if lhs.shape == rhs.shape and np.array_equal(lhs, rhs):
            ok_a5 += 1
    check("A5 reduce 重映射 T(reduce(x,k)) == reduce(T(x), p^-1(k))",
          ok_a5 == 15, f"{ok_a5}/15")

    sec("B. Pattern 触发与拒绝（图侧行为）")

    g = Graph("b1")
    x = g.arg((2, 3))
    r = g.relu(x)
    t = g.transpose(r, (1, 0))
    g.returns = [t]
    g_ref = g.copy()
    fired = push_transpose_through_elementwise(g)
    shapes, errs = g.infer_shapes()
    check("B1 T(Relu(x)) 触发改写", fired)
    check("B2 改写后 IR = Relu(Transpose(x))（relu 的输入是 transpose）",
          len(g.ops) == 3 and g.ops[1].kind == "transpose"
          and g.ops[2].kind == "relu"
          and g.ops[2].inputs == [g.ops[1].name])
    check("B3 改写后输出 shape 不变", g.returns and
          shapes[g.returns[0]] == (3, 2))
    ok, d = graphs_equal_num(g_ref, g)
    check("B4 改写后数值等价", ok, d)

    # 白名单外一概拒绝
    for kind, build in [
        ("arg", lambda gg: gg.arg((2, 3))),
        ("const", lambda gg: gg.const(np.ones((2, 3), np.float32))),
    ]:
        gb = Graph(f"b_{kind}")
        v = build(gb)
        tb = gb.transpose(v, (1, 0))
        gb.returns = [tb]
        check(f"B5 T({kind}) 不触发（{kind} 不是逐元素算子）",
              push_transpose_through_elementwise(gb) is False)

    # reduce / reshape 拒绝
    gr = Graph("b_reduce")
    xr = gr.arg((2, 3))
    yr = gr.reduce_sum(xr, axis=1)
    tr = gr.transpose(yr, (1, 0))
    gr.returns = [tr]
    check("B6 T(ReduceSum) 不触发（不在白名单）",
          push_transpose_through_elementwise(gr) is False)

    gs = Graph("b_reshape")
    xs = gs.arg((2, 3))
    ys = gs.reshape(xs, (3, 2))
    ts = gs.transpose(ys, (1, 0))
    gs.returns = [ts]
    check("B7 T(Reshape) 不触发（不在白名单）",
          push_transpose_through_elementwise(gs) is False)

    # C2：唯一使用者
    gm = Graph("b_multi")
    xm = gm.arg((2, 3))
    rm = gm.relu(xm)
    tm = gm.transpose(rm, (1, 0))
    nm = gm.neg(rm)
    gm.returns = [tm, nm]
    gm_ref = gm.copy()
    check("B8 Relu 结果有两个使用者时拒绝",
          push_transpose_through_elementwise(gm) is False)
    ok, d = graphs_equal_num(gm_ref, gm)
    check("B9 拒绝时图未被改动", ok and len(gm.ops) == len(gm_ref.ops))

    # transpose 本身不在白名单（不会被自己穿过自己）
    gt = Graph("b_tt")
    xt = gt.arg((2, 3, 4))
    t1 = gt.transpose(xt, (1, 2, 0))
    t2 = gt.transpose(t1, (2, 0, 1))
    gt.returns = [t2]
    gt_ref = gt.copy()
    check("B10 T(Transpose) 不走传播 Pattern（交给合并规则）",
          push_transpose_through_elementwise(gt) is False)
    check("B11 相邻转置由合并规则处理（2 -> 0，互逆）",
          merge_adjacent_transposes(gt) and gt.count_kind("transpose") == 0)
    ok, d = graphs_equal_num(gt_ref, gt)
    check("B12 合并互逆对数值等价", ok, d)

    sec("C. 三明治：传播 → 合并 → 相消（收益链路）")

    def make_sandwich(p_out, p_in, shape=(2, 3)):
        g = Graph("sandwich")
        x = g.arg(shape)
        w = g.transpose(x, p_in)
        e = g.relu(w)
        z = g.transpose(e, p_out)
        g.returns = [z]
        return g

    g2 = make_sandwich((1, 0), (1, 0))
    g2_ref = g2.copy()
    tb = traffic_report(g2)
    rounds, status = run_passes(
        g2, [push_transpose_through_elementwise,
             merge_adjacent_transposes, fold_transpose_into_constant])
    ta = traffic_report(g2)
    check("C1 互逆三明治 2 -> 0 个转置",
          g2.count_kind("transpose") == 0, f"{rounds} 轮，{status}")
    ok, d = graphs_equal_num(g2_ref, g2)
    check("C2 互逆三明治数值等价", ok, d)
    check("C3 纯搬运元素移动降为 0",
          tb["element_moves"] > 0 and ta["element_moves"] == 0,
          f"{tb['element_moves']} -> {ta['element_moves']}")

    # 非互逆：p_out=(1,2,0), p_in=(1,2,0)：r = q[p[i]] = (2,0,1) ≠ 恒等
    g3 = make_sandwich((1, 2, 0), (1, 2, 0), shape=(2, 3, 4))
    g3_ref = g3.copy()
    tb3 = traffic_report(g3)
    run_passes(g3, [push_transpose_through_elementwise,
                    merge_adjacent_transposes,
                    fold_transpose_into_constant])
    ta3 = traffic_report(g3)
    check("C4 非互逆三明治 2 -> 1 个转置（合并特例）",
          g3.count_kind("transpose") == 1)
    ok, d = graphs_equal_num(g3_ref, g3)
    check("C5 非互逆三明治数值等价", ok, d)
    check("C6 纯搬运减半（元素移动 2n -> n 规模）",
          ta3["element_moves"] * 2 == tb3["element_moves"],
          f"{tb3['element_moves']} -> {ta3['element_moves']}")

    # 常量折叠路径
    g4 = Graph("c_const")
    w = g4.const(np.arange(12, dtype=np.float32).reshape(3, 4) - 6.0)
    r4 = g4.relu(w)
    t4 = g4.transpose(r4, (1, 0))
    g4.returns = [t4]
    g4_ref = g4.copy()
    run_passes(g4, [push_transpose_through_elementwise,
                    merge_adjacent_transposes,
                    fold_transpose_into_constant])
    check("C7 常量路径：转置折进常量（0 个转置）",
          g4.count_kind("transpose") == 0
          and any(o.kind == "const" and o.value.shape == (4, 3)
                  for o in g4.ops))
    ok, d = graphs_equal_num(g4_ref, g4)
    check("C8 常量路径数值等价", ok, d)

    sec("D. 反面教材：无视唯一使用者的劣化")

    gd = Graph("d_pess")
    xd = gd.arg((2, 3))
    rd = gd.relu(xd)
    td = gd.transpose(rd, (1, 0))
    nd = gd.neg(rd)
    gd.returns = [td, nd]
    gd_ref = gd.copy()
    ops_before = len(gd.ops)
    fired = push_transpose_through_elementwise_unchecked(gd)
    ops_after = len(gd.ops)
    ok, d = graphs_equal_num(gd_ref, gd, seeds=(0, 1, 2))
    check("D1 强推后数值仍等价（合法性没破）", ok, d)
    check("D2 但算子增殖（劣化，这就是 C2 的理由）",
          fired and ops_after == ops_before + 1,
          f"op {ops_before} -> {ops_after}")

    sec("E. 方向门：双向振荡 vs 单向收敛（Day 69 预告）")

    def make_tr():
        g = Graph("e_dir")
        x = g.arg((2, 3))
        r = g.relu(x)
        t = g.transpose(r, (1, 0))
        g.returns = [t]
        return g

    g_both = make_tr()
    rounds_b, status_b = run_passes(
        g_both, [push_transpose_through_elementwise,
                 push_transpose_up_through_elementwise], max_rounds=30)
    check("E1 双向规则互相 undo，振荡被检测",
          status_b == "oscillation", f"{rounds_b} 轮后判定")

    g_one = make_tr()
    rounds_o, status_o = run_passes(
        g_one, [push_transpose_through_elementwise])
    check("E2 单向规则正常收敛", status_o == "fixpoint", f"{rounds_o} 轮")

    g_one2 = make_tr()
    run_passes(g_one2, [push_transpose_up_through_elementwise])
    check("E3 反向规则单独存在也能收敛（问题只在「同时在场」）",
          g_one2.count_kind("transpose") == 1
          and g_one2.ops[2].kind == "transpose")

    sec("F. 压力对拍：200 组随机图（数值/单调/不动点/无振荡）")

    rng6 = np.random.default_rng(680268)
    n = 200
    n_eq = n_mono = n_fix = 0
    t_all_before = t_all_after = 0
    for case in range(n):
        g = Graph(f"f{case}")
        rank = int(rng6.integers(2, 5))
        shape = tuple(int(rng6.integers(2, 5)) for _ in range(rank))
        cur = g.const((rng6.standard_normal(shape) * 3).astype(np.float32)) \
            if rng6.random() < 0.3 else g.arg(shape)
        for _ in range(int(rng6.integers(3, 9))):
            u = rng6.random()
            if u < 0.4:
                cur = g.transpose(cur, tuple(rng6.permutation(rank)))
            elif u < 0.7:
                cur = g.relu(cur)
            else:
                cur = g.neg(cur)
        g.returns = [cur]
        g_ref = g.copy()
        tb = traffic_report(g)
        _, status = run_passes(
            g, [push_transpose_through_elementwise,
                merge_adjacent_transposes,
                fold_transpose_into_constant])
        ta = traffic_report(g)
        ok, _ = graphs_equal_num(g_ref, g, seeds=(case % 5,))
        n_eq += int(ok)
        n_mono += int(ta["transposes"] <= tb["transposes"])
        r2, s2 = run_passes(g, [push_transpose_through_elementwise,
                                merge_adjacent_transposes,
                                fold_transpose_into_constant])
        n_fix += int(r2 == 0 and s2 == "fixpoint")
        assert status == "fixpoint"
        t_all_before += tb["transposes"]
        t_all_after += ta["transposes"]
    check("F1 数值等价 200/200", n_eq == n, f"{n_eq}/{n}")
    check("F2 转置数不增 200/200", n_mono == n, f"{n_mono}/{n}")
    check("F3 二次运行不动点 200/200", n_fix == n, f"{n_fix}/{n}")
    check("F4 转置总数显著下降",
          t_all_after < t_all_before,
          f"{t_all_before} -> {t_all_after}")

    sec("G. 白名单本身的语义（防呆）")

    check("G1 白名单只含逐元素一元算子",
          set(ELEMENTWISE_WHITELIST) == {"relu", "neg"})
    check("G2 add 不在白名单（受限 Pattern 的边界，选做挑战再扩展）",
          "add" not in ELEMENTWISE_WHITELIST)

    print(f"\n测试汇总：PASS {PASS} / FAIL {FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
