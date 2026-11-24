"""test_matmul_bias.py —— 第 53 天的类型与 Shape 测试（共 10 个）。

覆盖：
  融合正例（带/不带 Relu）、bias 左右位置、输出类型来源、
  乘积多使用者（reject / keep）、%s 共用时 Relu 不吸收、
  [N] 向量与错形 bias 的三分类拒绝、双侧都是 matmul 的拒绝、
  以及「拒绝必须无副作用」（恒等变换）。

运行: python3 test_matmul_bias.py
"""

import numpy as np

from mini_fuse_bias import (
    FEED, Graph, Rewriter, classify_bias_shape, count_cost, evaluate,
    run_fusion, tt,
    build_bias_relu_graph, build_bias_only_graph, build_bias_on_left_graph,
    build_multi_user_product_graph, build_shared_result_graph,
    build_bad_bias_graph, _matmul,
)

PRODUCT = FEED["%a"] @ FEED["%b"]
BIASED = PRODUCT + FEED["%bias"]
RELU = np.maximum(BIASED, 0.0)


def fused_ops(g):
    return [op for op in g.ops if op.name.startswith("mini.fused_")]


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    return True


# ---------- 1. 主线图：MatMul + Add + Relu -> fused_matmul_bias_relu ----------

def test_bias_relu_absorbed():
    g = build_bias_relu_graph()
    run_fusion(g)
    names = g.op_names()
    check(names == ["mini.fused_matmul_bias_relu"], f"应只剩融合算子，实际 {names}")
    out = evaluate(g, FEED)
    check(np.allclose(out[g.outputs[0].name], RELU), "融合后数值应等于 relu(A·B+bias)")
    print("通过：三算子直接吸收成 fused_matmul_bias_relu，数值一致")


# ---------- 2. 输出类型听 matmul 的，不听 inputs[0] 的 ----------

def test_output_type_follows_matmul():
    g = build_bias_relu_graph()
    run_fusion(g)
    res_type = fused_ops(g)[0].result.type
    check(res_type == tt(2, 2), f"融合结果类型应为 tensor<2x2xf32>，实际 {res_type}")
    check(res_type != tt(2, 3), "若照抄 inputs[0] 的类型会得到 2x3——这正是常见错误 1")
    print("通过：融合结果类型 = matmul 的输出类型 [M,N]，不是 lhs 的 [M,K]")


# ---------- 3. 无 Relu：两算子融合成 fused_matmul_bias ----------

def test_bias_only_fuses_two_ops():
    g = build_bias_only_graph()
    run_fusion(g)
    names = g.op_names()
    check(names == ["mini.fused_matmul_bias"], f"应只剩 fused_matmul_bias，实际 {names}")
    out = evaluate(g, FEED)
    check(np.allclose(out[g.outputs[0].name], BIASED), "数值应等于 A·B+bias")
    print("通过：MatMul+Add 融合成 fused_matmul_bias，数值一致")


# ---------- 4. bias 在左边也要认 ----------

def test_bias_on_left():
    g = build_bias_on_left_graph()
    run_fusion(g)
    names = g.op_names()
    check(names == ["mini.fused_matmul_bias"], f"bias 在左也应融合，实际 {names}")
    ins = [v.name for v in fused_ops(g)[0].inputs]
    check(ins == ["%a", "%b", "%bias"], f"融合算子操作数应归一为 (a, b, bias)，实际 {ins}")
    out = evaluate(g, FEED)
    check(np.allclose(out[g.outputs[0].name], BIASED), "bias 在左时数值仍应一致")
    print("通过：add(%bias, %m) 也正确融合，操作数归一成 (lhs=a, rhs=b, bias)")


# ---------- 5. 乘积多使用者：默认拒绝且必须是恒等变换 ----------

def test_multi_user_product_reject_is_identity():
    g = build_multi_user_product_graph()
    before = g.op_names()
    mm, ad, fl, ps = count_cost(g)
    run_fusion(g)                     # 默认 reject
    check(g.op_names() == before, "拒绝必须无副作用：算子列表应原样")
    mm2, ad2, fl2, ps2 = count_cost(g)
    check((mm, ad, fl, ps) == (mm2, ad2, fl2, ps2), "拒绝必须无副作用：代价账本应原样")
    out = evaluate(g, FEED)
    check(np.allclose(out["%r"], RELU), "%r 数值一致")
    check(np.allclose(out["%t"], np.maximum(PRODUCT, 0.0)), "%t 数值一致")
    print("通过：乘积 %m 有 2 个使用者时默认拒绝，IR、代价、数值全部原样")


# ---------- 6. 乘积多使用者 + keep：matmul 重算、语义不变 ----------

def test_multi_user_product_keep_recomputes_matmul():
    g = build_multi_user_product_graph()
    run_fusion(g, policy="keep")
    names = g.op_names()
    check("mini.matmul" in names, "keep 应保留 mini.matmul 给 %t 使用")
    check("mini.fused_matmul_bias_relu" in names, "keep 应融合 Relu 分支")
    mm, ad, fl, ps = count_cost(g)
    check(mm == 2, f"keep 后 matmul 应执行 2 次（原 1 次 + 融合算子里 1 次），实际 {mm}")
    out = evaluate(g, FEED)
    check(np.allclose(out[g.outputs[0].name], RELU), "keep 后 %r' 数值一致")
    check(np.allclose(out["%t"], np.maximum(PRODUCT, 0.0)), "keep 后 %t 数值一致")
    print(f"通过：keep 语义不变，但 matmul 执行 1→2 次、FLOPs {fl}（第 52 天只亏一次加法）")


# ---------- 7. %s 被 relu 和 return 共用：只做两算子融合 ----------

def test_shared_result_does_not_absorb_relu():
    g = build_shared_result_graph()
    run_fusion(g)
    names = g.op_names()
    check(names == ["mini.fused_matmul_bias", "mini.relu"],
          f"%s 多使用者时应保留 relu，实际 {names}")
    out = evaluate(g, FEED)
    check(np.allclose(out["%r"], RELU), "%r 数值一致")
    check(np.allclose(out["%s'"], BIASED), "return 拿到的应是 A·B+bias（不是 relu 后的值）")
    print("通过：%s 共用时只做两算子融合；return 拿到的仍是 A·B+bias")


# ---------- 8. [N] 向量 bias：BroadcastOnly，Pattern 拒绝 ----------

def test_rank1_bias_rejected():
    check(classify_bias_shape(tt(2), tt(2, 2)) == "BroadcastOnly",
          "bias [2] 对输出 [2,2] 应分类为 BroadcastOnly")
    g = build_bad_bias_graph("broadcast")
    before = g.op_names()
    run_fusion(g)
    check(g.op_names() == before, "BroadcastOnly 应拒绝且无副作用")
    print("通过：bias tensor<2xf32> 分类为 BroadcastOnly，Pattern 今天不碰（第 60 天放行）")


# ---------- 9. 错形 bias：Mismatch，Pattern 拒绝 ----------

def test_mismatch_bias_rejected():
    check(classify_bias_shape(tt(1, 2), tt(2, 2)) == "Mismatch",
          "bias [1,2] 对输出 [2,2] 应分类为 Mismatch")
    g = build_bad_bias_graph("mismatch")
    before = g.op_names()
    run_fusion(g)
    check(g.op_names() == before, "Mismatch 应拒绝且无副作用")
    print("通过：bias tensor<1x2xf32> 分类为 Mismatch，拒绝融合")


# ---------- 10. 双侧都是 matmul：分不清谁是 bias，拒绝 ----------

def test_both_matmul_rejected():
    g = Graph("both_matmul")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vc = g.add_input("%c", tt(2, 4))
    vd = g.add_input("%d", tt(4, 2))
    m1 = _matmul(g, va, vb, "%m1")
    m2 = g.create_op("mini.matmul", [vc, vd], "%m2", result_type=tt(2, 2))
    g.create_op("mini.add", [m1.result, m2.result], "%s", result_type=tt(2, 2))
    g.set_outputs([g.ops[-1].result])
    before = g.op_names()
    run_fusion(g)
    check(g.op_names() == before, "双侧都是 matmul 应拒绝且无副作用")
    print("通过：add(%m1, %m2) 两侧都是乘积——没有 bias 可言，拒绝融合")


if __name__ == "__main__":
    tests = [
        test_bias_relu_absorbed,
        test_output_type_follows_matmul,
        test_bias_only_fuses_two_ops,
        test_bias_on_left,
        test_multi_user_product_reject_is_identity,
        test_multi_user_product_keep_recomputes_matmul,
        test_shared_result_does_not_absorb_relu,
        test_rank1_bias_rejected,
        test_mismatch_bias_rejected,
        test_both_matmul_rejected,
    ]
    for t in tests:
        print(f"[{t.__name__}]")
        t()
        print()
    print(f"全部 {len(tests)} 个测试通过。")
