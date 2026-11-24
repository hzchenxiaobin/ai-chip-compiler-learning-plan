#!/usr/bin/env python3
"""第 46 天 IEEE 见证：用 numpy 真算一遍"为什么是 -0.0 不是 +0.0"。

对应教程 3.3 节的 IEEE 对照表。每张表回答一个重写的合法性问题：

  恒等式重写（x + c -> x、x * c -> x）问的是：结果与 x 是否数值一致
  （对零还要求符号位一致，否则 1/x 会从 -inf 变 +inf）；
  Mul(x, 0) -> 0 问的是：结果是否等于"重写后物化的那个 +0.0 常量"。

判定都按"数值相等"口径，NaN 只要求结果仍是 NaN（与 Pattern 的假设
声明一致：不跟踪 payload）。
"""

import numpy as np

f32 = np.float32
np.seterr(all="ignore")  # 除零/无效运算的告警关掉；异常结果本身就是要看的证据


def same_as_x(name, r, x):
    """恒等式重写的判定：结果与 x 数值一致（零含符号位）。"""
    if np.isnan(x):
        ok = bool(np.isnan(r))
        verdict = "是" if ok else "否 <-- 反例"
        print(f"  x = {name:<7} 结果 = {r!s:<7}              与 x 一致？{verdict}")
        return
    ok = bool(r == x and np.signbit(r) == np.signbit(x))
    verdict = "是" if ok else "否 <-- 反例"
    print(f"  x = {name:<7} 结果 = {r!s:<7} signbit = {int(np.signbit(r))}   与 x 一致？{verdict}")


def same_as_zero(name, r):
    """Mul(x, 0) -> 0 的判定：结果是否等于重写后物化的 +0.0。"""
    ok = bool(r == f32(0.0) and np.signbit(r) == 0)
    verdict = "是" if ok else "否 <-- 反例"
    print(f"  x = {name:<7} 结果 = {r!s:<7} signbit = {int(np.signbit(r))}   等于 +0.0？{verdict}")


print("== 表 1：x + (+0.0) —— 计划原文 Add(x, 0) 想要的恒等式 ==")
same_as_x("-0.0", f32(-0.0) + f32(0.0), f32(-0.0))
same_as_x("NaN", f32("nan") + f32(0.0), f32("nan"))
same_as_x("+Inf", f32("inf") + f32(0.0), f32("inf"))

print("== 表 2：x + (-0.0) —— 今天实现的 SimplifyAddNegZero ==")
same_as_x("-0.0", f32(-0.0) + f32(-0.0), f32(-0.0))
same_as_x("NaN", f32("nan") + f32(-0.0), f32("nan"))
same_as_x("+Inf", f32("inf") + f32(-0.0), f32("inf"))

print("== 表 3：x * 1.0 —— 今天实现的 SimplifyMulOne ==")
same_as_x("-0.0", f32(-0.0) * f32(1.0), f32(-0.0))
same_as_x("NaN", f32("nan") * f32(1.0), f32("nan"))
same_as_x("+Inf", f32("inf") * f32(1.0), f32("inf"))

print("== 表 4：x * (+0.0) —— 被否决的 Mul(x, 0) -> 0 ==")
same_as_zero("-0.0", f32(-0.0) * f32(0.0))
same_as_zero("NaN", f32("nan") * f32(0.0))
same_as_zero("+Inf", f32("inf") * f32(0.0))

print("== 符号零为什么可观察：1/x 的两种无穷 ==")
x = f32(-0.0)
print(f"  1/(-0.0)         = {1 / x}")
print(f"  1/((-0.0) + 0.0) = {1 / (x + f32(0.0))}   <-- Add(x, +0.0) 翻了符号")

print("== 整数为什么没有这个烦恼 ==")
print(f"  (-7) + 0 = {np.int32(-7) + np.int32(0)}"
      "  （i32 上 x + 0 恒等于 x；mini 目前只有 f32，才需要这份小心）")
