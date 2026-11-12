"""test_three_op_fusion.py —— 第 54 天的稳定性测试（共 12 个）。

今天的问题一句话：同一张输入图，换 Pattern 插入序、换访问顺序，
最终形态必须还是预期的那一个——「不依赖偶然执行顺序」是可以测的。

覆盖：
  两阶段/直接/全家桶的合流（confluence）、benefit 与插入序的作用边界、
  抢跑事故的复现与两种修法（让位规则、Pass 管道顺序）、
  %s 共用的半融合不动点、乘积多使用者的恒等拒绝、
  互相打架 Pattern 的不收敛检测。

运行: python3 test_three_op_fusion.py
"""

import numpy as np

from mini_fuse_pipeline import (
    FEED, GreedyDriver, NonConvergence, classify_bias_shape, count_cost,
    evaluate, tt,
    FuseMatmulBiasTwoStage, AbsorbReluEpilogue, FuseMatmulBiasReluDirect,
    FuseAddRelu, UnfuseMatmulBiasRelu,
    build_bias_relu_graph, build_add_relu_only_graph, build_shared_result_graph,
    build_multi_user_product_graph,
)

PRODUCT = FEED["%a"] @ FEED["%b"]
BIASED = PRODUCT + FEED["%bias"]
RELU = np.maximum(BIASED, 0.0)
ADD_RELU = np.maximum(FEED["%x"] + FEED["%y"], 0.0)

FULL = "mini.fused_matmul_bias_relu"
TWO = "mini.fused_matmul_bias"
SMALL = "mini.fused_add_relu"

VISITS = ("bottom-up", "top-down")


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    return True


def run(g, patterns, visit="bottom-up", max_visits=100):
    return GreedyDriver(g, patterns, visit=visit, max_visits=max_visits).run()


# ---------- 1. 两阶段路线：插入序 × 访问序全组合，同一个不动点 ----------

def test_two_stage_confluent():
    for pats in ([FuseMatmulBiasTwoStage(), AbsorbReluEpilogue()],
                 [AbsorbReluEpilogue(), FuseMatmulBiasTwoStage()]):
        for visit in VISITS:
            g = build_bias_relu_graph()
            n = run(g, pats, visit)
            check(g.op_names() == [FULL],
                  f"两阶段应得到 {FULL}（visit={visit}），实际 {g.op_names()}")
            check(np.allclose(evaluate(g, FEED)[g.outputs[0].name], RELU),
                  "两阶段融合后数值应等于 relu(A·B+bias)")
    print("通过：两阶段 [P1,P2] 在 2 种插入序 × 2 种访问序下都得到 fused_matmul_bias_relu")


# ---------- 2. 直接三算子：一步到位 ----------

def test_direct_one_shot():
    for visit in VISITS:
        g = build_bias_relu_graph()
        n = run(g, [FuseMatmulBiasReluDirect()], visit)
        check(g.op_names() == [FULL], f"直接路线应得到 {FULL}，实际 {g.op_names()}")
        check(n == 1, f"直接路线应 1 次改写到位，实际 {n} 次")
        check(np.allclose(evaluate(g, FEED)[g.outputs[0].name], RELU), "数值一致")
    print("通过：直接三算子在两种访问序下都是 1 次改写、fused_matmul_bias_relu")


# ---------- 3. 全家桶 [P1,P2,P3]：P3 的 benefit=2 让它在同 root 上领先 ----------

def test_all_set_benefit_orders_same_root():
    for pats in ([FuseMatmulBiasTwoStage(), AbsorbReluEpilogue(),
                 FuseMatmulBiasReluDirect()],
                [FuseMatmulBiasReluDirect(), AbsorbReluEpilogue(),
                 FuseMatmulBiasTwoStage()]):
        for visit in VISITS:
            g = build_bias_relu_graph()
            n = run(g, pats, visit)
            check(g.op_names() == [FULL], f"全家桶应得到 {FULL}，实际 {g.op_names()}")
            check(n == 1, f"benefit=2 的 P3 应先出手（1 次改写），实际 {n} 次")
    print("通过：全家桶里 benefit=2 的 P3 在同 root（mini.add）上稳定压过 benefit=1 的 P1")


# ---------- 4. benefit 相同：插入序决定谁出手，但不动点不变 ----------

def test_equal_benefit_insertion_order_only_changes_path():
    first = [FuseMatmulBiasTwoStage(benefit=1), AbsorbReluEpilogue(),
             FuseMatmulBiasReluDirect(benefit=1)]     # P1 插入在前
    second = [FuseMatmulBiasReluDirect(benefit=1), AbsorbReluEpilogue(),
              FuseMatmulBiasTwoStage(benefit=1)]      # P3 插入在前
    counts = set()
    for pats in (first, second):
        g = build_bias_relu_graph()
        n = run(g, pats)
        check(g.op_names() == [FULL], f"同 benefit 下不动点应仍是 {FULL}，实际 {g.op_names()}")
        counts.add(n)
    check(counts == {1, 2},
          f"插入序应只改变改写次数（P3 前=1 次，P1 前=2 次），实际 {counts}")
    print("通过：benefit 相同时由插入序决定路径（改写 1 次 vs 2 次），最终形态不变")


# ---------- 5. 抢跑事故：访问顺序改变最终形态（这就是「偶然执行顺序」） ----------

def test_steal_order_dependent_fixpoint():
    pats = [FuseAddRelu(), FuseMatmulBiasReluDirect()]
    g = build_bias_relu_graph()
    run(g, pats, "bottom-up")
    check(g.op_names() == ["mini.matmul", SMALL],
          f"bottom-up 下 P51 应抢跑（P51 root=relu 先被访问），实际 {g.op_names()}")
    out = evaluate(g, FEED)
    check(np.allclose(out[g.outputs[0].name], RELU), "抢跑后语义仍正确（合法但不理想）")
    mm1, ad1, fl1, ps1 = count_cost(g)
    check((mm1, ad1, fl1) == (1, 1, 32), "抢跑后 FLOPs 账应与目标形态相同（省的是访存）")
    check(ps1 == 6, f"抢跑后张量遍数应为 6（%m 落盘），实际 {ps1}")

    g = build_bias_relu_graph()
    run(g, pats, "top-down")
    check(g.op_names() == [FULL],
          f"top-down 下 P3 先访问 add，应一步到位，实际 {g.op_names()}")
    check(count_cost(g)[3] == 4, "目标形态张量遍数应为 4")
    print("通过：同一 Pattern 集 [P51,P3]，bottom-up 抢跑成 matmul+fused_add_relu（遍数 6），"
          "top-down 得 fused_matmul_bias_relu（遍数 4）——最终形态依赖访问顺序")


# ---------- 6. 修法一：让位规则 P51g，两种访问序都正确 ----------

def test_yield_guard_fixes_order_dependence():
    pats = [FuseAddRelu(guard_matmul=True), FuseMatmulBiasReluDirect()]
    for visit in VISITS:
        g = build_bias_relu_graph()
        run(g, pats, visit)
        check(g.op_names() == [FULL],
              f"让位版在 visit={visit} 下应得到 {FULL}，实际 {g.op_names()}")
        check(np.allclose(evaluate(g, FEED)[g.outputs[0].name], RELU), "数值一致")
    print("通过：P51g 让位规则让 [P51g,P3] 在两种访问序下都得到 fused_matmul_bias_relu")


# ---------- 7. 修法二：Pass 管道顺序（先 P3 后 P51）同样稳定 ----------

def test_pipeline_order_fixes_order_dependence():
    for visit in VISITS:
        g = build_bias_relu_graph()
        n1 = run(g, [FuseMatmulBiasReluDirect()], visit)
        n2 = run(g, [FuseAddRelu()], visit)
        check(g.op_names() == [FULL], f"管道修法后应得到 {FULL}，实际 {g.op_names()}")
        check((n1, n2) == (1, 0), f"第一个 Pass 改写 1 次、第二个 Pass 无可抢，实际 {(n1, n2)}")
        check(np.allclose(evaluate(g, FEED)[g.outputs[0].name], RELU), "数值一致")
    print("通过：管道顺序修法（大融合 Pass 先跑）在两种访问序下都稳定，P51 第二轮无可抢")


# ---------- 8. 管道修法不误伤纯 Add+Relu 图上的小融合 ----------

def test_pipeline_preserves_small_fusion():
    for visit in VISITS:
        g = build_add_relu_only_graph()
        n1 = run(g, [FuseMatmulBiasReluDirect()], visit)
        n2 = run(g, [FuseAddRelu()], visit)
        check(g.op_names() == [SMALL],
              f"纯 Add+Relu 图应保留 fused_add_relu，实际 {g.op_names()}")
        check((n1, n2) == (0, 1), "P3 不匹配（改写 0 次），P51 正常融合 1 次")
        check(np.allclose(evaluate(g, FEED)[g.outputs[0].name], ADD_RELU), "数值一致")
    print("通过：管道修法在纯 Add+Relu 图上仍把小融合留给 P51（改写 0+1 次）")


# ---------- 9. 让位规则不误伤纯 Add+Relu 图 ----------

def test_yield_guard_preserves_small_fusion():
    pats = [FuseAddRelu(guard_matmul=True), FuseMatmulBiasReluDirect()]
    for visit in VISITS:
        g = build_add_relu_only_graph()
        run(g, pats, visit)
        check(g.op_names() == [SMALL], f"应得到 {SMALL}，实际 {g.op_names()}")
    print("通过：P51g 的让位只在 add 真吃乘积时收手，纯 Add+Relu 图照样融合")


# ---------- 10. %s 共用：半融合是所有路线的共同不动点 ----------

def test_shared_result_half_fused_stable():
    for label, pats in [
        ("两阶段", [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue()]),
        ("直接", [FuseMatmulBiasReluDirect()]),
        ("全家桶", [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue(),
                    FuseMatmulBiasReluDirect()]),
    ]:
        for visit in VISITS:
            g = build_shared_result_graph()
            run(g, pats, visit)
            check(g.op_names() == [TWO, "mini.relu"],
                  f"{label}/visit={visit} 应停在半融合 {TWO}+relu，实际 {g.op_names()}")
            out = evaluate(g, FEED)
            check(np.allclose(out["%r"], RELU), "%r 数值一致")
            check(np.allclose(out["%s'"], BIASED), "return 拿到的仍是 A·B+bias")
    print("通过：%s 共用时，6 种组合全部停在半融合（fused_matmul_bias + relu），数值一致")


# ---------- 11. 乘积多使用者：全家桶下拒绝仍是恒等变换 ----------

def test_multi_user_product_identity():
    g = build_multi_user_product_graph()
    before = g.op_names()
    cost = count_cost(g)
    run(g, [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue(),
            FuseMatmulBiasReluDirect()])
    check(g.op_names() == before, "乘积多使用者：整条链应原样保留")
    check(count_cost(g) == cost, "拒绝必须无副作用：代价账本原样")
    out = evaluate(g, FEED)
    check(np.allclose(out["%r"], RELU) and
          np.allclose(out["%t"], np.maximum(PRODUCT, 0.0)), "数值一致")
    print("通过：乘积 %m 多使用者时，新管道（P1+P2+P3）拒绝融合且无副作用")


# ---------- 12. 互相打架的 Pattern：驱动必须能发现不收敛 ----------

def test_oscillation_detected_and_semantics_intact():
    g = build_bias_relu_graph()
    try:
        run(g, [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue(),
                UnfuseMatmulBiasRelu()], max_visits=30)
        raise AssertionError("Unfuse 与 P2 互为逆变换，不应收敛")
    except NonConvergence as e:
        check("30" in str(e), f"异常信息应指明访问上限，实际：{e}")
    check(g.op_names() in ([FULL], [TWO, "mini.relu"]),
          f"停止时 IR 停在某个合法中间态，实际 {g.op_names()}")
    out = evaluate(g, FEED)
    check(np.allclose(out[g.outputs[0].name], RELU),
          "即使没收敛，语义在每次改写下都保持正确（浪费的是编译时间）")
    print("通过：Unfuse/P2 振荡在访问上限处被拦下，中间态 IR 语义仍然正确")


if __name__ == "__main__":
    tests = [
        test_two_stage_confluent,
        test_direct_one_shot,
        test_all_set_benefit_orders_same_root,
        test_equal_benefit_insertion_order_only_changes_path,
        test_steal_order_dependent_fixpoint,
        test_yield_guard_fixes_order_dependence,
        test_pipeline_order_fixes_order_dependence,
        test_pipeline_preserves_small_fusion,
        test_yield_guard_preserves_small_fusion,
        test_shared_result_half_fused_stable,
        test_multi_user_product_identity,
        test_oscillation_detected_and_semantics_intact,
    ]
    for t in tests:
        print(f"[{t.__name__}]")
        t()
        print()
    print(f"全部 {len(tests)} 个测试通过。")
