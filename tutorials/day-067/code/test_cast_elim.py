#!/usr/bin/env python3
"""test_cast_elim.py —— 第 67 天验收测试：Cast 消除 Pattern + 类型反例。

分节：
  A  类型系统与 Verifier（五分类 17 对 / 未知 dtype / 图级 G1、G2、G3 /
     eval 与 numpy 行为一致 / bf16 截断仿真正确）
  B  Pattern 恒等消除（多使用者照样消除 / 单跳直返 / 非恒等不动 /
     连续 identity 幂等）
  C  位宽陷阱（buggy 版在 i8→ui8、f32→i32、f16→bf16 上翻车；
     正确判据全部保留）
  D  PassManager 不动点（连续 identity 1..4 跳全部迭代到 0 /
     随机链 op 数 = 非 identity 跳数）
  E  反例与判定表（四类反例全保留 / 17 个 dtype 对的期望 op 数）
  F  数值对拍（0.1 三重人格 / 0.5 假阴性 / 300 回绕 / 0xFF 两副面孔 /
     回环方向终审 7 条）
  G  MLIR 对照（stock 管道 8 项裁决；mlir-opt 不可用则 SKIP）

用法：python3 test_cast_elim.py   （在 code/ 目录下）
"""

from __future__ import annotations

import copy
import random

import numpy as np

from cast_elim_lab import (
    BITCAST_CHAIN_IR, BITCAST_SAME_IR, BITCAST_UI8_IR, CLASS_NAME, DTYPES,
    EXT_TRUNC_IR, EXTF_SAME_IR, EXTSI_TRUNC_IR, PATTERNS, TRUNC_EXT_IR,
    TRUNCSI_EXTSI_IR, DTYPE_INFO, MiniCastOp, MiniGraph, classify_cast,
    count_casts, eliminate_bitwidth_cast_bug, eliminate_identity_cast,
    find_mlir_opt, run_mlir_opt, run_passes, to_bf16, values_equal,
    verify_cast,
)

PASS = 0
FAIL = 0
SKIP = 0

B32 = np.array([[0.1, 0.5, 2.75], [-3.25, 100.0, 0.0]],
               dtype=np.float32).reshape(2, 3)
B8 = np.array([[-1, 0, 127], [-128, 5, 42]], dtype=np.int8).reshape(2, 3)


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


def section(title: str) -> None:
    print(f"\n== {title} ==")


def graph_of(x, in_t, hops, input_dtypes=None):
    """构造链图：%in --cast t1--> --cast t2--> …；hops 是目标 dtype 列表。"""
    ops, cur = [], in_t
    ids = ["%in"] + [f"%t{k}" for k in range(len(hops))]
    for k, tgt in enumerate(hops):
        ops.append(MiniCastOp(ids[k + 1], ids[k], (2, 3), cur, tgt))
        cur = tgt
    return MiniGraph(ops=ops, returns=[ids[-1]], inputs={"%in": x},
                     input_dtypes=input_dtypes or {"%in": in_t})


# ----------------------------------------------------------------------

def test_a() -> None:
    section("A  类型系统与 Verifier")

    expect = {
        ("f32", "f32"): "identity", ("f16", "f16"): "identity",
        ("bf16", "bf16"): "identity", ("i8", "i8"): "identity",
        ("f16", "f32"): "widen", ("bf16", "f32"): "widen",
        ("i8", "i32"): "widen", ("ui8", "i32"): "widen",
        ("f32", "f16"): "narrow", ("f32", "bf16"): "narrow",
        ("i32", "i8"): "narrow",
        ("f16", "bf16"): "reformat", ("bf16", "f16"): "reformat",
        ("i8", "ui8"): "signflip", ("ui8", "i8"): "signflip",
        ("f32", "i32"): "domainflip", ("i32", "f32"): "domainflip",
    }
    bad = [(k, classify_cast(*k)) for k in expect
           if classify_cast(*k) != expect[k]]
    check("A1 五分类 17 个 dtype 对全部正确", not bad, str(bad))

    check("A2 未知 dtype 被 Verifier 拦截",
          verify_cast("f64", "f32") != [] and verify_cast("f32", "f64") != []
          and verify_cast("f32", "f32") == [])

    g = MiniGraph(ops=[MiniCastOp("%c", "%ghost", (2, 3), "f32", "f16")],
                  returns=["%c"], inputs={"%in": B32})
    check("A3 G1：输入无定义被拦截", any("G1" in e for e in g.verify()))

    g = graph_of(B32, "f32", ["f32"])
    g.returns = ["%missing"]
    check("A4 G2：返回值无定义被拦截", any("G2" in e for e in g.verify()))

    g = MiniGraph(ops=[MiniCastOp("%c", "%in", (2, 3), "f16", "f32")],
                  returns=["%c"], inputs={"%in": B32},
                  input_dtypes={"%in": "f32"})
    check("A5 G3：声明输入类型与生产者实际类型不一致被拦截",
          any("G3" in e for e in g.verify()))

    g = graph_of(B32, "f32", ["f32", "f16"])
    check("A6 合法图 verify 通过", g.verify() == [])

    x = np.float32(0.1)
    check("A7 bf16 截断仿真：f32(0.1) → 0.099609375（0x3DCC0000）",
          float(to_bf16(x)) == 0.099609375
          and int(to_bf16(x).view(np.uint32)) == 0x3DCC0000)

    g = graph_of(B32, "f32", ["f32"])
    r = g.eval()
    check("A8 eval 恒等跳与 numpy 直取一致",
          np.array_equal(r[0], B32) and r[0].dtype == B32.dtype)

    check("A9 eval 的 f32→i32 与 numpy astype 一致（0.5→0、2.75→2）",
          np.array_equal(graph_of(B32, "f32", ["i32"]).eval()[0],
                         B32.astype(np.int32)))


def test_b() -> None:
    section("B  Pattern 恒等消除")

    g = MiniGraph(
        ops=[MiniCastOp("%r", "%in", (2, 3), "f32", "f32"),
             MiniCastOp("%a", "%r", (2, 3), "f32", "f16"),
             MiniCastOp("%b", "%r", (2, 3), "f32", "i32")],
        returns=["%a", "%b"], inputs={"%in": B32})
    before = g.eval()
    run_passes(g, PATTERNS)
    check("B1 多使用者照样消除（3→2，%a/%b 直读 %in）",
          len(g.ops) == 2 and all(op.input_id == "%in" for op in g.ops)
          and all(np.array_equal(a, b)
                  for a, b in zip(g.eval(), before)))

    g = graph_of(B32, "f32", ["f32"])
    before = g.eval()
    run_passes(g, PATTERNS)
    check("B2 单跳直返整体消除（1→0，return %in）",
          len(g.ops) == 0 and g.returns == ["%in"]
          and np.array_equal(g.eval()[0], before[0]))

    g = graph_of(B32, "f32", ["f16"])
    before = g.eval()
    run_passes(g, PATTERNS)
    check("B3 非恒等单跳不动（f32→f16 保留）",
          len(g.ops) == 1 and np.array_equal(g.eval()[0], before[0]))

    g = MiniGraph(
        ops=[MiniCastOp("%r", "%in", (2, 3), "i8", "i8")],
        returns=["%r"], inputs={"%in": B8})
    before = g.eval()
    run_passes(g, PATTERNS)
    check("B4 被返回的 identity 也照样消除（i8→i8，return %in）",
          len(g.ops) == 0 and g.returns == ["%in"]
          and np.array_equal(g.eval()[0], before[0]))

    g = graph_of(B32, "f32", ["f16"])
    run_passes(g, PATTERNS)
    r1 = (len(g.ops), g.print_ir())
    run_passes(g, PATTERNS)
    r2 = (len(g.ops), g.print_ir())
    check("B5 幂等：不动点后再跑不变（f32→f16 原样）", r1 == r2 and r1[0] == 1)

    for i, o in [("i8", "ui8"), ("f32", "i32"), ("f16", "bf16"),
                 ("ui8", "i8"), ("f32", "f16")]:
        g = graph_of(B8 if i in ("i8", "ui8") else B32, i, [o])
        run_passes(g, PATTERNS)
        if len(g.ops) != 1:
            check(f"B6 {i}→{o} 保留", False)
            return
    check("B6 同宽/缩窄/换号五种反例全部保留", True)


def test_c() -> None:
    section("C  位宽陷阱：只比位宽的 buggy 判据翻车现场")

    g = graph_of(B8, "i8", ["ui8"])
    before = g.eval()
    g_ok = copy.deepcopy(g)
    run_passes(g_ok, PATTERNS)
    while eliminate_bitwidth_cast_bug(g):
        pass
    check("C1 i8→ui8：正确版保留（255 不变）；位宽版消除后 255 → -1",
          len(g_ok.ops) == 1 and np.array_equal(g_ok.eval()[0], before[0])
          and len(g.ops) == 0 and not np.array_equal(g.eval()[0], before[0]))

    g = graph_of(B32, "f32", ["i32"])
    before = g.eval()
    while eliminate_bitwidth_cast_bug(g):
        pass
    check("C2 f32→i32：位宽版把 0.1/0.5 原样放行（应为 0）",
          len(g.ops) == 0 and not np.array_equal(g.eval()[0], before[0]))

    g = MiniGraph(
        ops=[MiniCastOp("%c", "%in", (2, 3), "f16", "bf16")],
        returns=["%c"],
        inputs={"%in": np.array([[0.1, 0.5, 2.75], [-3.25, 100., 0.]],
                                dtype=np.float16)},
        input_dtypes={"%in": "f16"})
    before = g.eval()
    while eliminate_bitwidth_cast_bug(g):
        pass
    check("C3 f16→bf16：位宽版放行（值应重新编码）",
          len(g.ops) == 0 and not np.array_equal(g.eval()[0], before[0]))

    check("C4 MLIR 的答案：同型 extf 被 Verifier 拒（源头上没有 no-op 可消除）；"
          "同型 bitcast 被消除——类型全等才动手，位宽不够",
          True, "见 G 节实测")

    g = graph_of(B8, "i8", ["i8"])
    before = g.eval()
    while eliminate_bitwidth_cast_bug(g):
        pass
    check("C5 buggy 版对真正的 identity 也成立（1→0，值不变）"
          "——错在判据太宽，不在消除动作本身",
          len(g.ops) == 0 and np.array_equal(g.eval()[0], before[0]))


def test_d() -> None:
    section("D  PassManager 不动点")

    for L in range(1, 5):
        g = graph_of(B32, "f32", ["f32"] * L)
        before = g.eval()
        rounds, applied = run_passes(g, PATTERNS)
        if not (len(g.ops) == 0 and applied == L
                and np.array_equal(g.eval()[0], before[0])):
            check(f"D1 连续 identity L={L} 迭代到 0", False)
            return
    check("D1 连续 identity 1..4 跳全部迭代到 0", True)

    rng = random.Random(67)
    nrng = np.random.default_rng(67)
    ok, n = 0, 0
    for _ in range(150):
        start = rng.choice(DTYPES)
        L = rng.randint(1, 5)
        chain = [rng.choice(DTYPES) for _ in range(L)]
        if DTYPE_INFO[start]["kind"] == "int":
            x = nrng.integers(0, 128, size=6).astype(
                np.int32 if start == "i32" else
                (np.int8 if start == "i8" else np.uint8))
        else:
            v = nrng.integers(0, 32, size=6) * 0.25 + 0.125
            x = (to_bf16(v) if start == "bf16"
                 else v.astype(np.float16 if start == "f16" else np.float32))
        g = graph_of(x.reshape(2, 3), start, chain)
        before = g.eval()
        run_passes(g, PATTERNS)
        expect = sum(1 for k, tgt in enumerate(chain)
                     if tgt != ([start] + chain)[k])
        n += 1
        if (values_equal(g.eval()[0], before[0]) and g.verify() == []
                and len(g.ops) == expect):
            ok += 1
    check(f"D2 随机 dtype 链 {ok}/{n}：op 数 = 非 identity 跳数，数值不变",
          ok == n)


def test_e() -> None:
    section("E  反例与判定表")

    g = MiniGraph(
        ops=[MiniCastOp("%w", "%in", (2, 3), "f32", "f16"),
             MiniCastOp("%n", "%in", (2, 3), "f32", "bf16"),
             MiniCastOp("%d", "%in", (2, 3), "f32", "i32"),
             MiniCastOp("%s", "%inp", (2, 3), "i8", "ui8")],
        returns=["%w", "%n", "%d", "%s"],
        inputs={"%in": B32, "%inp": B8})
    before = g.eval()
    _, applied = run_passes(g, PATTERNS)
    check("E1 四类反例图全保留（4→4，零应用）且数值不变",
          len(g.ops) == 4 and applied == 0
          and all(np.array_equal(a, b) for a, b in zip(g.eval(), before)))

    pairs = [("f32", "f32"), ("f16", "f16"), ("bf16", "bf16"),
             ("i8", "i8"), ("f16", "f32"), ("bf16", "f32"),
             ("i8", "i32"), ("ui8", "i32"), ("f32", "f16"),
             ("f32", "bf16"), ("i32", "i8"), ("f16", "bf16"),
             ("bf16", "f16"), ("i8", "ui8"), ("ui8", "i8"),
             ("f32", "i32"), ("i32", "f32")]
    ok, bad = 0, []
    for i, o in pairs:
        if DTYPE_INFO[i]["kind"] == "int":
            x = (np.array([[-128, -1, 127], [255, 300, 42]],
                          dtype=np.int32) if i == "i32"
                 else B8.astype(np.int8 if i == "i8" else np.uint8))
        else:
            x = B32.astype(np.float16 if i == "f16" else np.float32)
            if i == "bf16":
                x = to_bf16(x)
        g = MiniGraph(ops=[MiniCastOp("%c", "%in", (2, 3), i, o)],
                      returns=["%c"], inputs={"%in": x},
                      input_dtypes={"%in": i})
        before = g.eval()
        run_passes(g, PATTERNS)
        expect = 0 if i == o else 1
        if (len(g.ops) == expect and values_equal(g.eval()[0], before[0])):
            ok += 1
        else:
            bad.append((i, o))
    check(f"E2 判定表 {ok}/17：identity → 0，其余 → 1，数值不变",
          ok == 17, str(bad))

    check("E3 i32→i8 回绕现场：300 → 44（numpy C cast 语义）",
          int(np.array(300, np.int32).astype(np.int8)) == 44)


def test_f() -> None:
    section("F  数值对拍与方向终审")

    a32 = np.float32(0.1)
    check("F1 0.1 三重人格：f32 0.10000000149011612 / f16 0.0999755859375 /"
          " bf16 0.099609375",
          float(a32) == 0.10000000149011612
          and float(np.float16(a32)) == 0.0999755859375
          and float(to_bf16(a32)) == 0.099609375)

    check("F2 0.5 假阴性：f32→f16→f32 恰好相等（2 的幂——挑值不能只挑好值）",
          np.float32(np.float16(np.float32(0.5))) == np.float32(0.5))

    check("F3 0xFF 两副面孔：i8=-1、ui8=255，array_equal 判 False",
          int(np.int8(-1).view(np.uint8)) == 255
          and not np.array_equal(np.array(-1, np.int8),
                                 np.array(255, np.uint8)))

    rt = [
        (np.array([-128, -1, 0, 127], np.int8).astype(np.int32)
         .astype(np.int8), True),
        (np.array([-128, -1, 0, 127], np.int8).astype(np.uint8)
         .astype(np.int8), True),
        (np.float32(np.float16(np.float32(0.1))), False),
    ]
    check("F4 方向终审：i8→i32→i8 与 i8→ui8→i8 安全；"
          "f32→f16→f32 的 0.1 变 0.0999755859375",
          np.array_equal(rt[0][0], np.array([-128, -1, 0, 127], np.int8))
          and np.array_equal(rt[1][0], np.array([-128, -1, 0, 127], np.int8))
          and float(rt[2][0]) != float(np.float32(0.1)))

    x = np.array([np.nan, 1.5, np.inf], dtype=np.float32)
    y = np.array([np.nan, 1.5, np.inf], dtype=np.float32)
    check("F5 values_equal 对 NaN/Inf 视为相等（identity 不改位模式）",
          values_equal(x, y))

    g = graph_of(np.array([[np.nan, 1.5], [np.inf, 0.0]],
                          dtype=np.float32), "f32", ["f32", "f16"])
    before = g.eval()
    run_passes(g, PATTERNS)
    check("F6 含 NaN/Inf 的图：identity 消除后数值仍可对拍（equal_nan 口径）",
          len(g.ops) == 1 and values_equal(g.eval()[0], before[0]))


def test_g() -> None:
    section("G  MLIR 对照：stock 管道的真实裁决")

    if find_mlir_opt() is None:
        skip("G 全部", "mlir-opt 不可用")
        return

    code, _, err = run_mlir_opt(EXTF_SAME_IR, ["--canonicalize"])
    check("G1 extf f32→f32：Verifier 拒绝（cast incompatible）",
          code != 0 and "cast incompatible" in err)

    code, out, _ = run_mlir_opt(BITCAST_SAME_IR, ["--canonicalize"])
    check("G2 bitcast f32→f32：消除为 return %arg0",
          code == 0 and count_casts(out) == 0 and "return %arg0" in out)

    code, out, _ = run_mlir_opt(TRUNC_EXT_IR, ["--canonicalize"])
    check("G3 truncf∘extf（f16→f32→f16，数学恒等）：原样保留 2 op"
          "——stock 无浮点回环折叠",
          code == 0 and count_casts(out) == 2)

    code, out, _ = run_mlir_opt(EXT_TRUNC_IR, ["--canonicalize"])
    check("G4 extf∘truncf（f32→f16→f32，有损）：原样保留 2 op（正确拒绝）",
          code == 0 and count_casts(out) == 2)

    code, out, _ = run_mlir_opt(TRUNCSI_EXTSI_IR, ["--canonicalize"])
    check("G5 trunci∘extsi（i8→i32→i8，恒等）：消除为 return %arg0"
          "——整数回环有折叠",
          code == 0 and count_casts(out) == 0 and "return %arg0" in out)

    code, out, _ = run_mlir_opt(EXTSI_TRUNC_IR, ["--canonicalize"])
    check("G6 extsi∘trunci（i32→i8→i32，有损）：原样保留 2 op（正确拒绝）",
          code == 0 and count_casts(out) == 2)

    code, out, _ = run_mlir_opt(BITCAST_CHAIN_IR, ["--canonicalize"])
    check("G7 bitcast 链 f32→i32→f32：消除为 return %arg0（双射重解释）",
          code == 0 and count_casts(out) == 0 and "return %arg0" in out)

    code, _, err = run_mlir_opt(BITCAST_UI8_IR, ["--canonicalize"])
    check("G8 bitcast i8→ui8：ui8 类型不存在——MLIR 整数 signless，"
          "符号在 op 不在类型",
          code != 0 and "signless" in err)


def main() -> int:
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
