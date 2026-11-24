#!/usr/bin/env python3
"""test_reshape_merge.py —— 第 66 天验收测试：Reshape 合并 Pattern + 边界。

分节：
  A  语义与三关 Verifier（numel / E1 / E2 / E3 / 图级 G1、G3 / eval 与 numpy 一致）
  B  Pattern 1 恒等消除（多使用者照样消除 / order=F 恒等 / 非恒等不动）
  C  Pattern 2 链合并（朴素 / 绕回 / 中间形状任意性 / 轮数 / 混 order 拒绝）
  D  PassManager 不动点（链长 1..6 的链尾判定 / 幂等性）
  E  反例（多使用者 / 被 return / 分叉独立判定 / numel 违规构造）
  F  数值对拍（非连续输入 / 随机链对拍 numpy / 混 order 终审）
  G  激进版与 MLIR 对照（改写合法删除有条件 / stock 管道裁决；mlir-opt
     不可用则跳过 MLIR 项）

用法：python3 test_reshape_merge.py   （在 code/ 目录下）
"""

from __future__ import annotations

import copy
import random

import numpy as np

from reshape_merge_lab import (
    TENSOR_RESHAPE_CHAIN_IR, TWO_PATTERNS, MiniGraph, MiniReshapeOp,
    eliminate_identity_reshape, find_mlir_opt, merge_aggressive_reshape,
    merge_consecutive_reshape, numel, run_mlir_opt, run_passes,
    verify_reshape,
)

PASS = 0
FAIL = 0
SKIP = 0

B = np.arange(24, dtype=np.float32).reshape(2, 3, 4)


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))
    return cond


def skip(name: str, why: str = "") -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name}（{why}）")


def build_chain(x_shape, shapes, order="C"):
    """构造链图：x --reshape s1--> --reshape s2--> …（全部同 order）。"""
    ops, cur = [], tuple(x_shape)
    ids = ["%in"] + [f"%t{i}" for i in range(len(shapes))]
    for i, s in enumerate(shapes):
        ops.append(MiniReshapeOp(ids[i + 1], ids[i], cur, "f32", tuple(s),
                                 order))
        cur = tuple(s)
    return ops, ids


def graph_of(x, shapes, order="C"):
    ops, ids = build_chain(x.shape, shapes, order)
    return MiniGraph(ops=ops, returns=[ids[-1]], inputs={"%in": x})


def section(title: str) -> None:
    print(f"\n== {title} ==")


# ----------------------------------------------------------------------

def test_a() -> None:
    section("A  语义与三关 Verifier")
    check("A1 numel：形状连乘（3 例）",
          numel((2, 3, 4)) == 24 and numel((24,)) == 24 and numel((1, 24)) == 24)
    check("A2 E1 拦截非法维度（0 维 / 负维 / 空形状）",
          verify_reshape((2, 3, 4), (0, 6))[0].startswith("[E1]")
          and verify_reshape((2, 3, 4), (24, -1))[0].startswith("[E1]")
          and verify_reshape((2, 3, 4), ())[0].startswith("[E1]"))
    check("A3 E2 拦截元素数量不守恒（24 ≠ 35）",
          verify_reshape((2, 3, 4), (5, 7))[0].startswith("[E2]"))
    check("A4 E3 拦截未知 order",
          verify_reshape((2, 3, 4), (24,), "A")[0].startswith("[E3]"))
    g_bad = MiniGraph(
        ops=[MiniReshapeOp("%t", "%ghost", (2, 3, 4), "f32", (6, 4))],
        returns=["%t"], inputs={"%in": B})
    check("A5 图级 G1：输入无定义被拦截",
          any(e.startswith("[G1]") for e in g_bad.verify()))
    g_shape = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (3, 8), "f32", (6, 4))],
        returns=["%t"], inputs={"%in": B})
    check("A5b 图级 G3：声明输入形状与生产者实际形状不一致被拦截",
          any(e.startswith("[G3]") for e in g_shape.verify()))
    g = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4))],
        returns=["%t"], inputs={"%in": B})
    check("A6 eval 与 numpy 语义一致（含 F 序）",
          np.array_equal(g.eval()[0], np.reshape(B, (6, 4)))
          and np.array_equal(
              MiniGraph(ops=[MiniReshapeOp("%f", "%in", (2, 3, 4), "f32",
                                           (24,), "F")],
                        returns=["%f"], inputs={"%in": B}).eval()[0],
              np.reshape(B, (24,), order="F")))


def test_b() -> None:
    section("B  Pattern 1：恒等消除（不需要唯一使用者检查）")
    g = MiniGraph(ops=[MiniReshapeOp("%r", "%in", (2, 3, 4), "f32",
                                     (2, 3, 4))],
                  returns=["%r"], inputs={"%in": B})
    before = g.eval()
    rounds, applied = run_passes(g, TWO_PATTERNS)
    check("B1 恒等单跳消除（op 数 1→0，值不变）",
          len(g.ops) == 0 and np.array_equal(g.eval()[0], before[0]))

    g2 = MiniGraph(
        ops=[MiniReshapeOp("%r", "%in", (2, 3, 4), "f32", (2, 3, 4)),
             MiniReshapeOp("%a", "%r", (2, 3, 4), "f32", (24,)),
             MiniReshapeOp("%b", "%r", (2, 3, 4), "f32", (4, 6))],
        returns=["%a", "%b", "%r"], inputs={"%in": B})
    before2 = g2.eval()
    run_passes(g2, TWO_PATTERNS)
    check("B2 结果被 2 个 op + 1 个 return 共 3 处使用 → 照样消除，全部改道",
          len(g2.ops) == 2 and g2.ops[0].input_id == "%in"
          and g2.ops[1].input_id == "%in"
          and g2.returns == ["%a", "%b", "%in"]
          and all(np.array_equal(a, b)
                  for a, b in zip(g2.eval(), before2)))

    g3 = MiniGraph(ops=[MiniReshapeOp("%r", "%in", (2, 3, 4), "f32",
                                      (2, 3, 4), "F")],
                   returns=["%r"], inputs={"%in": B})
    before3 = g3.eval()
    run_passes(g3, TWO_PATTERNS)
    check("B3 order='F' 的恒等同样消除（同形状 reshape 与 order 无关）",
          len(g3.ops) == 0 and np.array_equal(g3.eval()[0], before3[0]))

    g4 = graph_of(B, [(24,)])
    run_passes(g4, TWO_PATTERNS)
    check("B4 非恒等单跳不触发 P1（op 数仍 1）",
          len(g4.ops) == 1 and g4.ops[0].out_shape == (24,))


def test_c() -> None:
    section("C  Pattern 2：链合并（中间形状从判据消失）")
    g = graph_of(B, [(6, 4), (24,)])
    before = g.eval()
    rounds, applied = run_passes(g, TWO_PATTERNS)
    check("C1 朴素链合并（2→1，直读 %in，shape=[24]，2 轮 1 次）",
          len(g.ops) == 1 and g.ops[0].input_id == "%in"
          and g.ops[0].out_shape == (24,) and rounds == 2 and applied == 1
          and np.array_equal(g.eval()[0], before[0]))

    g2 = graph_of(B, [(6, 4), (2, 3, 4)])
    before2 = g2.eval()
    run_passes(g2, TWO_PATTERNS)
    check("C2 绕回链整体消除（2→0，链尾 == 输入形状）",
          len(g2.ops) == 0 and np.array_equal(g2.eval()[0], before2[0]))

    finals = []
    for s1 in [(6, 4), (24,), (4, 6), (2, 12), (1, 24)]:
        gx = graph_of(B, [s1, (24,)])
        before_x = gx.eval()
        run_passes(gx, TWO_PATTERNS)
        finals.append(gx.eval()[0])
        if len(gx.ops) != 1 or gx.ops[0].out_shape != (24,):
            check(f"C3 中间形状 {s1} 合并失败", False)
            return
    check("C3 中间形状任意性：5 种 s1 全部合并成同一个 Reshape(x,(24,))，值相等",
          all(np.array_equal(f, finals[0]) for f in finals)
          and np.array_equal(finals[0], np.reshape(B, (24,))))

    g4 = graph_of(B, [(6, 4), (24,), (2, 12), (24, 1), (12, 2)])
    before4 = g4.eval()
    rounds4, applied4 = run_passes(g4, TWO_PATTERNS)
    check("C4 五连链每轮合并一对（applied=4），终点直读 %in",
          applied4 == 4 and len(g4.ops) == 1 and g4.ops[0].input_id == "%in"
          and np.array_equal(g4.eval()[0], before4[0]))

    g5 = graph_of(B, [(6, 4), (24,)], order="C")
    g5.ops[1].order = "F"       # 内层 C、外层 F
    before5 = g5.eval()
    run_passes(g5, TWO_PATTERNS)
    g6 = graph_of(B, [(6, 4)], order="F")
    g6.ops[0].order = "F"
    g6.ops.append(MiniReshapeOp("%t1", "%t0", (6, 4), "f32", (24,), "C"))
    g6.returns = ["%t1"]
    before6 = g6.eval()
    run_passes(g6, TWO_PATTERNS)
    check("C5 混 order 两个方向都拒绝（C→F 与 F→C 均原样保留，值不变）",
          len(g5.ops) == 2 and len(g6.ops) == 2
          and np.array_equal(g5.eval()[0], before5[0])
          and np.array_equal(g6.eval()[0], before6[0]))


def test_d() -> None:
    section("D  PassManager 不动点：链尾形状一刀判定")
    shapes_pool = [(6, 4), (24,), (4, 6), (2, 12), (24, 1), (12, 2)]
    ok_all, rounds_ok = True, True
    for L in range(1, 7):
        for tail, want in [((24,), 1), ((2, 3, 4), 0)]:
            shapes = shapes_pool[:L - 1] + [tail]
            g = graph_of(B, shapes)
            before = g.eval()
            run_passes(g, TWO_PATTERNS)
            if not (len(g.ops) == want
                    and np.array_equal(g.eval()[0], before[0])
                    and g.verify() == []):
                ok_all = False
    check("D1 链长 1..6 × 链尾两种命运：最终 op 数 = 0（链尾==输入）或 1",
          ok_all)

    g = graph_of(B, [(6, 4), (24,), (4, 6)])
    run_passes(g, TWO_PATTERNS)
    ir_once = g.print_ir()
    rounds2, applied2 = run_passes(g, TWO_PATTERNS)
    check("D2 幂等性：不动点再跑一遍零应用、IR 不变",
          applied2 == 0 and g.print_ir() == ir_once)


def test_e() -> None:
    section("E  反例：多使用者与必要中间结果")
    g = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,)),
             MiniReshapeOp("%u", "%t", (6, 4), "f32", (4, 6))],
        returns=["%c", "%u"], inputs={"%in": B})
    before = g.eval()
    rounds, applied = run_passes(g, TWO_PATTERNS)
    check("E1 多使用者反例：保守 P2 零应用，3 个 op 原样、数值不变",
          applied == 0 and len(g.ops) == 3
          and all(np.array_equal(a, b) for a, b in zip(g.eval(), before)))

    g2 = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,))],
        returns=["%c", "%t"], inputs={"%in": B})
    before2 = g2.eval()
    run_passes(g2, TWO_PATTERNS)
    check("E2 被 return 的中间值拒绝（use_count 含 return，2 个 op 原样）",
          len(g2.ops) == 2
          and all(np.array_equal(a, b) for a, b in zip(g2.eval(), before2)))

    g3 = MiniGraph(
        ops=[MiniReshapeOp("%t1", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%t2", "%t1", (6, 4), "f32", (24,)),
             MiniReshapeOp("%u", "%t1", (6, 4), "f32", (4, 6)),
             MiniReshapeOp("%v", "%u", (4, 6), "f32", (2, 12))],
        returns=["%t2", "%v"], inputs={"%in": B})
    before3 = g3.eval()
    run_passes(g3, TWO_PATTERNS)
    check("E3 分叉链各段独立判定：(%t1,%t2) 阻塞、(%u,%v) 合并（4→3，%v 直读 %t1）",
          len(g3.ops) == 3 and g3.ops[2].input_id == "%t1"
          and all(np.array_equal(a, b) for a, b in zip(g3.eval(), before3)))

    g4 = MiniGraph(ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (5, 7))],
                   returns=["%t"], inputs={"%in": B})
    check("E4 numel 违规构造被图级 verify 拦截（[E2] 元素数量不守恒）",
          any(e.startswith("[E2]") for e in g4.verify()))


def test_f() -> None:
    section("F  数值对拍")
    xT = B.T          # 非连续输入（stride 乱序）
    g = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", xT.shape, "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,))],
        returns=["%c"], inputs={"%in": xT})
    before = g.eval()
    run_passes(g, TWO_PATTERNS)
    check("F1 非连续输入的链照常合并且值不变（np.reshape 语义对拍）",
          len(g.ops) == 1
          and np.array_equal(g.eval()[0], before[0])
          and np.array_equal(g.eval()[0], np.reshape(xT, (24,))))

    rng = random.Random(466)
    ok, n = True, 0

    def rand_factorization(n_):
        rank = rng.randint(1, 4)
        dims, rem = [], n_
        for _ in range(rank - 1):
            divs = [d for d in range(1, rem + 1) if rem % d == 0]
            d = rng.choice(divs)
            dims.append(d)
            rem //= d
        dims.append(rem)
        return tuple(dims)

    for _ in range(50):
        rank = rng.randint(1, 4)
        shape = tuple(rng.randint(1, 5) for _ in range(rank))
        total = numel(shape)
        L = rng.randint(1, 5)
        shapes = [rand_factorization(total) for _ in range(L)]
        x = np.arange(total, dtype=np.float32).reshape(shape)
        g = graph_of(x, shapes)
        before = g.eval()
        run_passes(g, TWO_PATTERNS)
        want = np.reshape(x, shapes[-1])
        if not (np.array_equal(g.eval()[0], before[0])
                and np.array_equal(g.eval()[0], want) and g.verify() == []):
            ok = False
        n += 1
    check(f"F2 随机 {n} 组链对拍 numpy：合并后值 == 直接 reshape 到链尾", ok)

    a = np.reshape(B, (6, 4), order="C")
    b = np.reshape(a, (24,), order="F")
    check("F3 混 order 终审：C∘F 不等于任何单个 reshape（C 或 F）",
          not np.array_equal(b, np.reshape(B, (24,)))
          and not np.array_equal(b, np.reshape(B, (24,), order="F")))


def test_g() -> None:
    section("G  激进版与 MLIR 对照")
    g = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,)),
             MiniReshapeOp("%u", "%t", (6, 4), "f32", (4, 6))],
        returns=["%c", "%u"], inputs={"%in": B})
    before = g.eval()
    while merge_aggressive_reshape(g):
        pass
    check("G1 激进版多使用者图：两路直连 %in 后删除无人的 %t（3→2，值不变）",
          len(g.ops) == 2 and g.ops[0].input_id == "%in"
          and g.ops[1].input_id == "%in"
          and all(np.array_equal(a, b) for a, b in zip(g.eval(), before)))

    g2 = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,))],
        returns=["%c", "%t"], inputs={"%in": B})
    before2 = g2.eval()
    while merge_aggressive_reshape(g2):
        pass
    check("G2 激进版遇到图输出：%t 保留、%c 改直读 %in（2 op，值不变）",
          len(g2.ops) == 2 and g2.ops[1].input_id == "%in"
          and all(np.array_equal(a, b) for a, b in zip(g2.eval(), before2)))

    g3 = graph_of(B, [(6, 4), (24,)])
    g4 = copy.deepcopy(g3)
    before3 = g3.eval()
    run_passes(g3, TWO_PATTERNS)
    while merge_aggressive_reshape(g4):
        pass
    check("G3 唯一使用者时激进版与保守版殊途同归（IR 相同）",
          g3.print_ir() == g4.print_ir()
          and np.array_equal(g3.eval()[0], before3[0]))

    if find_mlir_opt() is None:
        skip("G4/G5 MLIR 对照", "mlir-opt 不可用")
        return
    code, canon = run_mlir_opt(TENSOR_RESHAPE_CHAIN_IR, ["--canonicalize"])
    check("G4 MLIR：tensor.reshape 链 --canonicalize 原样保留（2 个）",
          code == 0 and canon.count("tensor.reshape") == 2)
    from reshape_merge_lab import COLLAPSE_CHAIN_IR
    _, c2 = run_mlir_opt(COLLAPSE_CHAIN_IR, ["--canonicalize"])
    check("G5 MLIR：collapse 连链折叠成单 op [[0, 1, 2]]（结构化对照）",
          c2.count("tensor.collapse_shape") == 1 and "[[0, 1, 2]]" in c2)


def main() -> int:
    print("=" * 66)
    print("第 66 天验收测试：Reshape 合并 Pattern、边界与数值对拍")
    print("=" * 66)
    test_a()
    test_b()
    test_c()
    test_d()
    test_e()
    test_f()
    test_g()
    print()
    print("=" * 66)
    print(f"汇总：PASS {PASS} / FAIL {FAIL} / SKIP {SKIP}")
    print("=" * 66)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
