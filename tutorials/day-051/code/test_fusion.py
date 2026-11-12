"""test_fusion.py —— 第 51 天基础测试：融合 Pattern 的正例、反例与完整性。

运行: python3 test_fusion.py
依赖: numpy
"""

import numpy as np

from mini_fuse import Graph, Rewriter, evaluate, run_fusion


def build_basic():
    g = Graph("basic")
    a = g.add_input("%a", "tensor<2x2xf32>")
    b = g.add_input("%b", "tensor<2x2xf32>")
    g.create_op("mini.add", [a, b], "%t")
    g.create_op("mini.relu", [g.ops[-1].result], "%r")
    g.set_outputs([g.ops[-1].result])
    return g


def build_shared_relu_result():
    # %r 有两个使用者：图输出和第二个 mini.add —— 融合后两者都必须接上 %r'
    g = Graph("shared")
    a = g.add_input("%a", "tensor<2x2xf32>")
    b = g.add_input("%b", "tensor<2x2xf32>")
    c = g.add_input("%c", "tensor<2x2xf32>")
    g.create_op("mini.add", [a, b], "%t")
    r = g.create_op("mini.relu", [g.ops[-1].result], "%r")
    g.create_op("mini.add", [r.result, c], "%s")
    g.set_outputs([r.result, g.ops[-1].result])
    return g


def build_multi_user_add():
    # %t 有两个使用者：图输出和 mini.relu —— 必须拒绝融合
    g = Graph("multi")
    a = g.add_input("%a", "tensor<2x2xf32>")
    b = g.add_input("%b", "tensor<2x2xf32>")
    t = g.create_op("mini.add", [a, b], "%t")
    r = g.create_op("mini.relu", [t.result], "%r")
    g.set_outputs([t.result, r.result])
    return g


FEED = {
    "%a": np.array([[1.0, -2.0], [3.0, -4.0]]),
    "%b": np.array([[0.5, 0.5], [-1.0, 2.0]]),
    "%c": np.array([[10.0, 10.0], [10.0, 10.0]]),
}


def test_basic_fusion():
    g = build_basic()
    before = evaluate(g, FEED)["%r"]
    assert run_fusion(g)
    names = [op.name for op in g.ops]
    assert names == ["mini.fused_add_relu"], names
    after = evaluate(g, FEED)["%r'"]
    assert np.allclose(before, after)
    print("test_basic_fusion        通过：2 个算子融合成 1 个，数值一致")


def test_shared_relu_result_still_fuses():
    g = build_shared_relu_result()
    before = evaluate(g, FEED)
    assert run_fusion(g)
    fused = g.ops[0]
    assert fused.name == "mini.fused_add_relu"
    # %r' 同时出现在图输出和第二个 mini.add 的输入里
    assert g.outputs[0] is fused.result
    assert g.ops[1].inputs[0] is fused.result
    after = evaluate(g, FEED)
    assert np.allclose(before["%r"], after["%r'"])
    assert np.allclose(before["%s"], after["%s"])
    print("test_shared_relu_result  通过：%r 的两个使用者都被正确改接")


def test_multi_user_add_is_rejected():
    g = build_multi_user_add()
    before = evaluate(g, FEED)
    assert not run_fusion(g)
    assert [op.name for op in g.ops] == ["mini.add", "mini.relu"]
    after = evaluate(g, FEED)
    assert np.allclose(before["%r"], after["%r"])
    print("test_multi_user_add      通过：中间结果多使用者，Pattern 拒绝融合")


def test_wrong_erase_order_is_caught():
    g = build_basic()
    rw = Rewriter(g)
    relu = g.ops[1]
    add = g.ops[0]
    rw.create("mini.fused_add_relu", add.inputs, insert_before=relu)
    try:
        rw.erase(add)  # 错误顺序：还没改接使用者就擦生产者
    except RuntimeError as e:
        assert "仍有 1 处使用者" in str(e), str(e)
        print("test_wrong_erase_order   通过：错误擦除顺序被 Rewriter 拒绝，"
              "异常信息 =", e)
    else:
        raise AssertionError("错误顺序应当抛出 RuntimeError")


def test_illegal_chain_is_not_matched():
    g = Graph("not_a_chain")
    a = g.add_input("%a", "tensor<2x2xf32>")
    g.create_op("mini.relu", [a], "%r1")
    g.create_op("mini.relu", [g.ops[-1].result], "%r2")  # Relu(Relu(x))，不是 Add 链
    g.set_outputs([g.ops[-1].result])
    assert not run_fusion(g)
    assert [op.name for op in g.ops] == ["mini.relu", "mini.relu"]
    print("test_illegal_chain       通过：Relu(Relu(x)) 不匹配，图保持原样")


if __name__ == "__main__":
    test_basic_fusion()
    test_shared_relu_result_still_fuses()
    test_multi_user_add_is_rejected()
    test_wrong_erase_order_is_caught()
    test_illegal_chain_is_not_matched()
    print("\n全部 5 个测试通过。")
