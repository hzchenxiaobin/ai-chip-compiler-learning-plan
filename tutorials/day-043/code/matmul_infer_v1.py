#!/usr/bin/env python3
"""Day 43 TDD 第 1 步：直觉版——两条"想当然"被测试当场抓住。

这个版本保留了 K 匹配检查（T13 绿），但带着两条直觉 bug：

  bug A  batch 维一律抄 lhs，不看看 rhs 是不是已知
        → T11 红：?x2x3 · 2x3x2 推出 ?x2x2，而 rhs 明明告诉了 batch=2。
  bug B  不查前提（unranked / rank<2 / 秩相等）直接算
        → T14 红：2x3 · 2x3x2 内维"恰好"都是 3，居然推出 2x2 成功；
        → T15 崩：3 · 3 取 rhs[-2] 直接 IndexError。

预期：12/15，红 T11、T14、T15。
重放（在 code/ 目录下）：
  mkdir -p /tmp/day043/v1
  cp test_matmul_infer.py matmul_infer_v1.py /tmp/day043/v1/
  mv /tmp/day043/v1/matmul_infer_v1.py /tmp/day043/v1/matmul_infer.py
  cd /tmp/day043/v1 && python3 test_matmul_infer.py
"""

DYN = None  # 动态维 "?"


def infer_matmul_result(lhs_shape, rhs_shape):
    # 直觉版唯一的防御：K 双侧静态且不等才算非法。
    if lhs_shape[-1] is not DYN and rhs_shape[-2] is not DYN \
            and lhs_shape[-1] != rhs_shape[-2]:
        return None, "K mismatch"

    out = [d for d in lhs_shape[:-2]]      # bug A：batch 一律抄 lhs
    out.append(lhs_shape[-2])              # M 只看 lhs（这条直觉是对的）
    out.append(rhs_shape[-1])              # N 只看 rhs（这条也是对的）
    return tuple(out), None                # bug B：上面若越界/错秩，就让它崩
