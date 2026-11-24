"""test_multi_user.py —— 第 52 天测试：多使用者反例与各策略的性质。

运行: python3 test_multi_user.py
依赖: numpy
"""

import numpy as np

from mini_fuse_multi import (
    FEED, Graph, build_multi_user_graph, build_single_user_graph,
    count_cost, evaluate, run_fusion,
)


def reference():
    """不经过任何改写的参考结果：直接按算子语义计算。"""
    t = FEED["%a"] + FEED["%b"]
    return np.maximum(t, 0.0), t + FEED["%c"]


def test_multi_user_rejected_by_default():
    g = build_multi_user_graph()
    before = evaluate(g, FEED)
    assert not run_fusion(g, policy="reject")          # 默认策略：不命中
    assert [op.name for op in g.ops] == ["mini.add", "mini.relu", "mini.add"]
    after = evaluate(g, FEED)
    assert np.allclose(after["%r"], before["%r"])
    assert np.allclose(after["%s"], before["%s"])
    assert count_cost(g) == (2, 8)                     # 代价也没变
    print("test_multi_user_rejected_by_default 通过：默认拒绝，IR、语义、代价都不变")


def test_keep_strategy_preserves_semantics():
    g = build_multi_user_graph()
    ref_r, ref_s = reference()
    assert run_fusion(g, policy="keep")
    assert [op.name for op in g.ops] == ["mini.add", "mini.fused_add_relu", "mini.add"]
    # 关键性质：保留的 mini.add 仍喂给第二个 mini.add —— %t 没有被改接
    assert g.ops[2].inputs[0] is g.ops[0].result
    assert g.ops[2].inputs[0].name == "%t"
    out = evaluate(g, FEED)
    assert np.allclose(out["%r'"], ref_r)
    assert np.allclose(out["%s"], ref_s)
    add_calls, passes = count_cost(g)
    assert add_calls == 3 and passes == 9               # 加法 2 -> 3 次
    print("test_keep_strategy_preserves_semantics 通过：语义不变，"
          "但加法 2→3 次、张量遍数 8→9（合法 ≠ 有收益）")


def test_rewire_t_changes_semantics():
    g = build_multi_user_graph()
    ref_r, ref_s = reference()
    assert run_fusion(g, policy="rewire-t")
    assert [op.name for op in g.ops] == ["mini.fused_add_relu", "mini.add"]
    assert g.ops[1].inputs[0] is g.ops[0].result        # %s 被改接到融合结果！
    out = evaluate(g, FEED)
    assert np.allclose(out["%r'"], ref_r)               # %r' 本身是对的
    assert not np.allclose(out["%s"], ref_s)            # %s 错了
    # 出错的恰好是 a+b<0 的位置：期望 8.5/8.0，实际 10.0（relu 后加 c）
    assert np.allclose(out["%s"], np.array([[11.5, 10.0], [12.0, 10.0]]))
    print(f"test_rewire_t_changes_semantics    通过：%s 被改接，"
          f"{out['%s'].tolist()} != 期望 {ref_s.tolist()}")


def test_erase_anyway_is_caught():
    g = build_multi_user_graph()
    try:
        run_fusion(g, policy="erase-anyway")
    except RuntimeError as e:
        assert "仍有" in str(e) and "使用者" in str(e)
        print(f"test_erase_anyway_is_caught       通过：Rewriter 拦截，异常信息 = {e}")
    else:
        raise AssertionError("erase-anyway 本应抛出 RuntimeError")


def test_single_user_fuses_under_all_policies():
    for policy in ("reject", "keep", "rewire-t"):
        g = build_single_user_graph()
        before = evaluate(g, FEED)
        assert run_fusion(g, policy=policy)
        assert [op.name for op in g.ops] == ["mini.fused_add_relu"], (policy, [o.name for o in g.ops])
        out = evaluate(g, FEED)
        assert np.allclose(before["%r"], out["%r'"]), policy
    print("test_single_user_fuses_under_all_policies 通过：单使用者图三种策略结果一致")


def build_t_and_return_graph():
    """%t 的两个使用者：mini.relu 和图输出（return）。"""
    g = Graph("t_return")
    va = g.add_input("%a", "tensor<2x2xf32>")
    vb = g.add_input("%b", "tensor<2x2xf32>")
    t = g.create_op("mini.add", [va, vb], "%t")
    g.create_op("mini.relu", [t.result], "%r")
    g.set_outputs([t.result, g.ops[-1].result])        # return %t, %r
    return g


def test_multi_user_with_return_consumer():
    g = build_t_and_return_graph()
    t_val = FEED["%a"] + FEED["%b"]
    assert not run_fusion(g, policy="reject")           # return 也是使用者：拒绝
    assert [op.name for op in g.ops] == ["mini.add", "mini.relu"]
    out = evaluate(g, FEED)
    assert np.allclose(out["%t"], t_val)
    # keep 策略：Relu 分支融合，%t 继续作为图输出
    assert run_fusion(g, policy="keep")
    assert [op.name for op in g.ops] == ["mini.add", "mini.fused_add_relu"]
    assert g.outputs[0] is g.ops[0].result and g.outputs[0].name == "%t"
    out = evaluate(g, FEED)
    assert np.allclose(out["%t"], t_val)
    assert np.allclose(out["%r'"], np.maximum(t_val, 0.0))
    print("test_multi_user_with_return_consumer 通过：return 也是使用者，keep 保留 %t 作输出")


if __name__ == "__main__":
    test_multi_user_rejected_by_default()
    test_keep_strategy_preserves_semantics()
    test_rewire_t_changes_semantics()
    test_erase_anyway_is_caught()
    test_single_user_fuses_under_all_policies()
    test_multi_user_with_return_consumer()
    print("\n全部 6 个测试通过。")
