#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_negative_acceptance.py —— 第 55 天负例验收测试。

把教程 §5 的验收判据钉成断言（全部基于 mini_fuse_accept.py 的语料）：

  T1  正例双遍历同形态：bottom-up / top-down 的最终 IR 必须完全一致；
  T2  负例恒等拒绝：拒绝后 IR 逐字不变、代价账本不变（无副作用）；
  T3  数值对账：融合前后按 return 位置对齐的输出全部 allclose；
  T4  假负例不被误伤：输出多使用 / 操作数共享不妨碍融合；
  T5  半融合不动点：%s 共用时两种遍历都停在 fused_matmul_bias + relu；
  T6  类型边界：f64 与混合 dtype 在 Pattern 层被拦下；拆掉闸门后失控；
  T7  Verifier 层负例：Shape/类型错误在 Pattern 之前被拦下；
  T8  第二道防线：绕过 Verifier 后 Pattern 仍拦下（防线冗余）。

运行:  python3 test_negative_acceptance.py
"""

import unittest

import numpy as np

import mini_fuse_accept as mfa


def run_case(case, order="bottom-up", type_guard=True):
    """构造新图 -> Verifier -> 按指定方向跑管道，返回 (图, 判前 IR, 判后 IR)。"""
    _, _, _, build, _, _ = case
    g = build()
    pre_ir = g.print_ir()
    mfa.run_pipeline(g, order=order, type_guard=type_guard)
    return g, pre_ir, g.print_ir()


def case_by_id(cid):
    return next(c for c in mfa.CASES if c[0] == cid)


class T1PositiveSameFixpoint(unittest.TestCase):
    """正例：两种遍历方向必须殊途同归（Day 54 的教训写成断言）。"""

    def test_all_positive_cases_converge_both_orders(self):
        for cid in ("C01", "C02", "C03", "C04", "C05", "C06", "C08"):
            case = case_by_id(cid)
            g1, _, ir1 = run_case(case, "bottom-up")
            g2, _, ir2 = run_case(case, "top-down")
            self.assertEqual(ir1, ir2, f"{cid} 双遍历形态不一致")
            self.assertEqual(sorted(g1.op_names()), sorted(case[5]),
                             f"{cid} 最终算子名单与期望不符")


class T2IdentityRejection(unittest.TestCase):
    """负例：拒绝必须是恒等变换——IR 逐字不变、代价账本不变。"""

    def test_identity_cases_are_exact_identity(self):
        for cid in ("C07", "C09", "C10", "C11"):
            case = case_by_id(cid)
            for order in ("bottom-up", "top-down"):
                g, pre_ir, post_ir = run_case(case, order)
                self.assertEqual(pre_ir, post_ir,
                                 f"{cid}({order}) 拒绝时修改了 IR")
                # 代价账本：构造新图对照
                g0 = case[3]()
                self.assertEqual(mfa.count_cost(g), mfa.count_cost(g0),
                                 f"{cid}({order}) 拒绝时代价账本变了")

    def test_identity_rejection_has_no_side_effects(self):
        """拒绝后 use 计数必须原样（第 52 天：失败无副作用）。"""
        case = case_by_id("C07")
        g0, g1 = case[3](), case[3]()
        mfa.run_pipeline(g1, order="bottom-up")
        for op in g0.body_ops():
            twin = next(o for o in g1.body_ops() if o.result.name ==
                        op.result.name)
            self.assertEqual(op.result.n_uses(), twin.result.n_uses(),
                             f"{op.result.name} 的 use 计数在拒绝后变了")


class T3NumericEquivalence(unittest.TestCase):
    """数值对账：所有可求值用例融合前后输出一致。"""

    def test_all_runnable_cases_preserve_values(self):
        for case in mfa.CASES:
            if case[4] == "verifier_reject":
                continue
            g0 = case[3]()
            ref = mfa.evaluate(g0, mfa.FEED)
            for order in ("bottom-up", "top-down"):
                g, _, _ = run_case(case, order)
                out = mfa.evaluate(g, mfa.FEED)
                self.assertEqual(len(ref), len(out))
                for i, (a, b) in enumerate(zip(ref, out)):
                    self.assertTrue(np.allclose(a, b),
                                    f"{case[0]}({order}) 输出 #{i} 数值变了")

    def test_mainline_values_match_hand_computation(self):
        """主线数字：%m=[[12,-13],[-27,28]] %s=[[22,-23],[-7,8]] %r=[[22,0],[0,8]]。"""
        g, _, _ = run_case(case_by_id("C01"), "bottom-up")
        out = mfa.evaluate(g, mfa.FEED)
        self.assertTrue(np.allclose(out[0], [[22.0, 0.0], [0.0, 8.0]]))
        g0 = case_by_id("C01")[3]()
        ref = mfa.evaluate(g0, mfa.FEED)
        self.assertTrue(np.allclose(ref[0], [[22.0, 0.0], [0.0, 8.0]]))


class T4FakeNegativesStillFuse(unittest.TestCase):
    """假负例：输出多使用 / 操作数共享从来不是融合的障碍。"""

    def test_relu_result_multi_use_still_fuses(self):
        # C05：%r 被 return 和第二个 add 使用——被擦除的是 relu，
        # replaceAllUses 会把两个使用者都迁到融合结果上
        g, _, _ = run_case(case_by_id("C05"), "bottom-up")
        self.assertEqual(g.op_names(), ["mini.fused_matmul_bias_relu",
                                        "mini.add"])
        # 第二个 add 的操作数必须是融合结果
        add2 = g.body_ops()[1]
        self.assertIs(add2.inputs[0].def_op, g.body_ops()[0])

    def test_shared_bias_operand_still_fuses_both_chains(self):
        # C06：bias 是操作数不是被删生产者——两条链都应融合
        g, _, _ = run_case(case_by_id("C06"), "bottom-up")
        self.assertEqual(g.op_names(), ["mini.fused_matmul_bias",
                                        "mini.fused_matmul_bias"])
        # 两个融合算子共享同一个 bias 值
        f1, f2 = g.body_ops()
        self.assertIs(f1.inputs[2], f2.inputs[2])


class T5HalfFusionFixpoint(unittest.TestCase):
    """半融合不动点：%s 共用时两种遍历都停在 fused_matmul_bias + relu。"""

    def test_shared_result_settles_at_half_fusion(self):
        case = case_by_id("C08")
        for order in ("bottom-up", "top-down"):
            g, pre_ir, post_ir = run_case(case, order)
            self.assertNotEqual(pre_ir, post_ir)  # 不是恒等（有部分融合）
            self.assertEqual(sorted(g.op_names()),
                             ["mini.fused_matmul_bias", "mini.relu"])
            # %s'（融合结果）必须仍有两个使用者：relu + return
            fused = g.body_ops()[0]
            self.assertEqual(fused.result.n_uses(), 2)


class T6TypeBoundary(unittest.TestCase):
    """类型边界：f64 / 混合 dtype 在 Pattern 层被拦下。"""

    def test_f64_add_relu_refused(self):
        g, pre_ir, post_ir = run_case(case_by_id("C09"), "bottom-up")
        self.assertEqual(pre_ir, post_ir)

    def test_mixed_dtype_refused(self):
        g, pre_ir, post_ir = run_case(case_by_id("C11"), "bottom-up")
        self.assertEqual(pre_ir, post_ir)

    def test_removing_type_guard_lets_them_through(self):
        """对照实验：拆掉类型闸门后 C09/C11 失守——验收器必须报警。"""
        for cid in ("C09", "C11"):
            case = case_by_id(cid)
            g, pre_ir, post_ir = run_case(case, "bottom-up",
                                          type_guard=False)
            self.assertNotEqual(pre_ir, post_ir,
                                f"{cid} 拆闸门后居然仍被拦下？")
            # 数值碰巧仍一致（numpy 对 f64/提升都良定义）——所以这道
            # 闸门必须静态把守，等不到数值对账来报警
            ref = mfa.evaluate(case[3](), mfa.FEED)
            out = mfa.evaluate(g, mfa.FEED)
            self.assertTrue(all(np.allclose(a, b)
                                for a, b in zip(ref, out)))

    def test_type_guard_does_not_block_f32(self):
        """闸门不能太宽：f32 的 Add+Relu 照常融合（回归守护）。"""
        g, _, _ = run_case(case_by_id("C03"), "bottom-up")
        self.assertEqual(g.op_names(), ["mini.fused_add_relu"])


class T7VerifierGate(unittest.TestCase):
    """Verifier 层负例：Shape/类型错误在 Pattern 之前被拦下。"""

    def test_shape_and_type_cases_fail_verification(self):
        for cid in ("C12", "C13", "C14"):
            case = case_by_id(cid)
            g = case[3]()
            errors = mfa.verify_graph(g)
            self.assertTrue(errors, f"{cid} 应当过不了 Verifier")
            self.assertEqual(case[4], "verifier_reject")

    def test_error_messages_match_expected_keywords(self):
        # 报错文案里的关键词与 MLIR 版 Verifier 对齐
        self.assertIn("shape 不匹配",
                      " ".join(mfa.verify_graph(case_by_id("C12")[3]())))
        self.assertIn("广播",
                      " ".join(mfa.verify_graph(case_by_id("C13")[3]())))
        self.assertIn("f32",
                      " ".join(mfa.verify_graph(case_by_id("C14")[3]())))


class T8SecondLineOfDefense(unittest.TestCase):
    """第二道防线：绕过 Verifier 后 Pattern 仍拦下（防线冗余）。"""

    def test_bypass_verifier_pattern_still_refuses(self):
        for cid in ("C12", "C13", "C14"):
            case = case_by_id(cid)
            g0 = case[3]()
            pre_ir = g0.print_ir()
            # 不看 verify_graph 的结果，直接把图喂给管道
            mfa.run_pipeline(g0, order="bottom-up")
            self.assertEqual(g0.print_ir(), pre_ir,
                             f"{cid} 绕过 Verifier 后 Pattern 没拦住")


class T9CostLedger(unittest.TestCase):
    """代价账本：正例的遍数必须下降，负例必须不变（优化前后对照）。"""

    def test_passes_table(self):
        expect = {  # (编号, 遍数前 -> 遍数后)
            "C01": (8, 4), "C02": (6, 4), "C03": (5, 3), "C04": (8, 4),
            "C05": (11, 7), "C06": (12, 8), "C07": (10, 10), "C08": (8, 6),
            "C09": (5, 5), "C10": (9, 9), "C11": (8, 8),
        }
        for cid, (pre, post) in expect.items():
            case = case_by_id(cid)
            g0 = case[3]()
            self.assertEqual(mfa.count_cost(g0), pre, f"{cid} 融合前遍数")
            g, _, _ = run_case(case, "bottom-up")
            self.assertEqual(mfa.count_cost(g), post, f"{cid} 融合后遍数")


if __name__ == "__main__":
    unittest.main(verbosity=2)
