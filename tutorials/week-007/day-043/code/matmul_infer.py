#!/usr/bin/env python3
"""Day 43 交付物：mini.matmul 输出 shape 推导规则表（可执行版，v2 最终版）。

规则表（R0~R4，与教程 5.2 节一致；明天 Day 44 原样翻译成 C++）：

  R0  前提：输入是 ranked、rank>=2、秩相等的 shape。
      这条正常管线里由 ODS（Mini_F32Tensor2DPlus）和 Verifier（规则 1）
      先行保证；本函数被直接调用时做防御性检查，返回 failure 而不是崩溃。
  R1  batch 维（前 rank-2 维）取“已知一侧”：lhs 静态取 lhs，
      否则取 rhs；两侧都 ? 才输出 ?。两侧都静态时 Verifier 规则 2
      已保证相等，取谁都一样。
  R2  输出 M = lhs 倒数第 2 维。M 只有 lhs 一个来源，? 原样传播。
  R3  输出 N = rhs 倒数第 1 维。N 只有 rhs 一个来源，? 原样传播。
  R4  K 被消费、不进输出：2x? · ?x2 照样推出 2x2。
      两侧都静态且不等属于结构性非法 → 防御性失败（Verifier 规则 3 的活）。

失败语义（三分类）：
  success + 全静态    推导成功；
  success + 带 ?      推导成功——“不知道”不是错误，绝不发明数字；
  failure             结构性非法（unranked / rank<2 / 秩不等 / K 不等）。
                      正常管线里 Verifier 先拦，这里只是兜底。

CLI 用法（5.5 节对照实验）：
  python3 matmul_infer.py 2x? ?x2     # -> tensor<2x2xf32>
"""

import sys

DYN = None  # 动态维，对应 IR 里的 "?"（MLIR C++ 里是 kDynamicSize 哨兵）


def infer_matmul_result(lhs_shape, rhs_shape):
    """按 R0~R4 推导 mini.matmul 的输出 shape。

    返回 (shape, None) 表示 success（shape 里可以带 DYN）；
    返回 (None, reason) 表示防御性失败。
    """
    # R0：防御性前提。正常管线里 Verifier 先跑，这里只是被直接调用时的兜底。
    if lhs_shape is None or rhs_shape is None:
        return None, "unranked: ODS 已挡在门外"
    if len(lhs_shape) < 2 or len(rhs_shape) < 2:
        return None, "rank<2: ODS 已挡在门外"
    if len(lhs_shape) != len(rhs_shape):
        return None, "rank mismatch: Verifier 规则 1 已拦"

    rank = len(lhs_shape)

    # R4：K 只在“两侧都静态且不等”时才算结构性非法（Verifier 规则 3 的活）。
    k_lhs, k_rhs = lhs_shape[-1], rhs_shape[-2]
    if k_lhs is not DYN and k_rhs is not DYN and k_lhs != k_rhs:
        return None, "K mismatch: Verifier 规则 3 已拦"

    out = []
    for i in range(rank - 2):  # R1：batch 维取已知一侧
        if lhs_shape[i] is not DYN:
            out.append(lhs_shape[i])
        else:
            out.append(rhs_shape[i])
    out.append(lhs_shape[-2])  # R2：M 只看 lhs
    out.append(rhs_shape[-1])  # R3：N 只看 rhs
    return tuple(out), None


def shape_to_string(shape):
    """(2, None, 3) -> 'tensor<2x?x3xf32>'，与 MLIR 文本同形。"""
    if shape is None:
        return "tensor<*xf32>"
    dims = "x".join("?" if d is DYN else str(d) for d in shape)
    return "tensor<" + dims + "xf32>"


def parse_shape(text):
    """'2x?' -> (2, None)；'*' -> None（unranked 的示意输入）。"""
    if text == "*":
        return None
    return tuple(None if p == "?" else int(p) for p in text.split("x"))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("用法: python3 matmul_infer.py <lhs> <rhs>    例如 2x? ?x2")
    lhs, rhs = parse_shape(sys.argv[1]), parse_shape(sys.argv[2])
    shape, err = infer_matmul_result(lhs, rhs)
    if err is not None:
        print("FAIL (" + err + ")")
        raise SystemExit(1)
    print(shape_to_string(shape))
