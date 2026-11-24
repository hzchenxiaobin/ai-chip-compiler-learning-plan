#!/usr/bin/env python3
"""test_broadcast.py —— 第 60 天独立验收测试（不依赖 broadcast_lab 的打印流程）。

  A. 判定表：16 组形状推导 + 4 组错误消息逐字对拍（mini vs np.broadcast_shapes）
  B. stride-0 视图：10 组 strides 对拍 + 共享存储 + 只读语义
  C. 随机对拍：400 组形状推导（种子 60）
  D. 未知维度：10 组 meet 结果 + 2 组 None 守恒性质
  E. 语义与边界：数值正确性、增强赋值报错、0 尺寸、标量恒等

运行: python3 test_broadcast.py
"""

from __future__ import annotations

import random
import sys

import numpy as np

from broadcast_lab import (BroadcastError, _meet, broadcast_shapes,
                           broadcast_shapes_unknown, broadcast_strides,
                           estrides, mini_broadcast)

PASS = FAIL = 0


def test(name, cond):
    global PASS, FAIL
    PASS += bool(cond)
    FAIL += not cond
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")


print("== A. 判定表：形状推导与错误消息 ==")
A_CASES = [
    (((), ()), ()),
    (((2, 3), (2, 3)), (2, 3)),
    (((2, 3), ()), (2, 3)),
    (((2, 3), (3,)), (2, 3)),
    (((2, 3), (2, 1)), (2, 3)),
    (((2, 3), (1, 3)), (2, 3)),
    (((8, 1000, 256), (256,)), (8, 1000, 256)),
    (((8, 1000, 256), (256,), (1, 1)), (8, 1000, 256)),
    (((5, 1), (1, 4)), (5, 4)),
    (((1, 3), (3, 1)), (3, 3)),
    (((0,), (1,)), (0,)),
    (((3, 4), (1,)), (3, 4)),
]
for i, (shapes, want) in enumerate(A_CASES, 1):
    got = broadcast_shapes(*shapes)
    test(f"A{i}  {shapes} → {want}", got == want)

A_ERR = [
    ((2, 3), (4,)),
    ((8, 1000, 256), (256, 1)),
    ((3, 1), (2, 3)),
    ((2, 3), (-1,)),
]
for i, shapes in enumerate(A_ERR, 1):
    try:
        broadcast_shapes(*shapes)
        got = "未报错"
    except BroadcastError as e:
        got = str(e)
    try:
        np.broadcast_shapes(*shapes)
        nmsg = "未报错"
    except ValueError as e:
        nmsg = str(e)
    test(f"A{len(A_CASES)+i}  {shapes} → error（消息与 numpy 逐字一致）",
         got == nmsg and nmsg != "未报错")

print("== B. stride-0 视图 ==")
B_CASES = [
    ((3,), (2, 3), (0, 1)),
    ((3, 1), (2, 3, 4), (0, 1, 0)),
    ((2, 1), (2, 3), (1, 0)),
    ((1, 3), (2, 3), (0, 1)),
    ((2, 3), (2, 3), (3, 1)),
    ((), (2, 3), (0, 0)),
    ((2, 3), (1, 2, 3), (0, 3, 1)),
    ((256,), (8, 1000, 256), (0, 0, 1)),
    ((2, 3), (4, 1, 2, 3), (0, 0, 3, 1)),
    ((3,), (4, 1, 2, 3), (0, 0, 0, 1)),
]
for i, (shape, out_shape, want) in enumerate(B_CASES, 1):
    arr = np.zeros(shape, dtype=np.float32)
    v = np.broadcast_to(arr, out_shape)
    numpy_st = tuple(t // arr.itemsize for t in v.strides)
    mini_st = broadcast_strides(shape, estrides(shape), out_shape)
    test(f"B{i}  {shape} → {out_shape}：mini {mini_st} == numpy {numpy_st}",
         mini_st == want == numpy_st)

arr = np.arange(3, dtype=np.float32)
v = np.broadcast_to(arr, (7, 3))
test("B11 广播视图与源共享存储（不拷贝）", np.shares_memory(v, arr))
writable = True
try:
    v[0, 0] = 99.0
except ValueError:
    writable = False
test("B12 广播视图只读（写它要报错）", not writable)
test("B13 100000x3 大输出仍只有 3 个元素的家",
     np.shares_memory(np.broadcast_to(arr, (100000, 3)), arr))
test("B14 不可广播返回 None：broadcast_strides((4,), (3,))",
     broadcast_strides((4,), (1,), (3,)) is None)

print("== C. 随机对拍（种子 60）==")
rng = random.Random(60)
ok = cnt = 0
for _ in range(400):
    shapes = [tuple(rng.choice([1, 1, 2, 3, 4, 5])
                    for _ in range(rng.randint(0, 4))) for _ in range(2)]
    if rng.random() < 0.15:
        shapes[0] = shapes[0] + (rng.randint(6, 9),)
    m = mini_broadcast(*shapes)
    try:
        n = ("ok", tuple(np.broadcast_shapes(*shapes)))
    except ValueError:
        n = ("error", None)
    cnt += 1
    ok += (m[0] == n[0]) and (m[0] == "error" or m[1] == n[1])
test(f"C1  {cnt} 组随机形状：mini 与 numpy 判定完全一致", ok == cnt)

print("== D. 未知维度（None 的 meet 规则）==")
D_CASES = [
    (((None, 3), (3,)), (None, 3)),
    (((None, 3), (5, 3)), (5, 3)),
    (((None, 3), (1,)), (None, 3)),
    (((None, 1), (5, 3)), (5, 3)),
    (((None,), (3,)), (3,)),
    (((None, 1), (1,)), (None, 1)),
    (((None, None), (None, 4)), (None, 4)),
    (((None,), (5,)), (5,)),
    (((), (None, 3)), (None, 3)),
]
for i, (shapes, want) in enumerate(D_CASES, 1):
    got = broadcast_shapes_unknown(*shapes)
    test(f"D{i}  {shapes} → {want}", got == want)
try:
    broadcast_shapes_unknown((None, 4), (3,))
    d10 = False
except BroadcastError:
    d10 = True
test("D10 (None,4)+(3,) 最右维 4 vs 3 失配报错", d10)
test("D11 meet 幂等：_meet(d, d) 对 1/3/None 都成立",
      _meet(1, 1) == 1 and _meet(3, 3) == 3 and _meet(None, None) is None)
def _meet_pair(a, b):
    try:
        return _meet(a, b)
    except BroadcastError:
        return "ERR"


test("D12 meet 交换律：_meet(a,b) == _meet(b,a) 全枚举（失配两边都失配）",
      all(_meet_pair(a, b) == _meet_pair(b, a)
          for a in (1, 3, None) for b in (1, 5, None)))

print("== E. 语义与边界 ==")
a = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
b = np.array([10.0, 20.0, 30.0])
test("E1  a(2,3)+b(3,) 的数值 = 行行加同一个 b",
     np.array_equal(a + b, [[11, 22, 33], [14, 25, 36]]))
x = np.zeros(3)
try:
    x += np.ones((4, 1))
    e2 = False
except ValueError as e:
    e2 = "non-broadcastable output" in str(e)
test("E2  增强赋值不许隐式升维：x(3,) += y(4,1) 报 non-broadcastable output", e2)
test("E3  广播不改变元素数守恒的邻居语义：reshape 的 -1 与广播的 None 是两套约定",
      (mini_broadcast((2, 3), (-1,))[0] == "error"))
test("E4  标量是万能形状：() 与任何形状广播得原形状",
      broadcast_shapes((7, 8), ()) == (7, 8))
test("E5  0 尺寸维参与规则的方式与普通维相同：((0,), (1,)) → (0,)",
      broadcast_shapes((0,), (1,)) == (0,))

print(f"\ntest_broadcast: {PASS}/{PASS + FAIL} passed")
if FAIL:
    sys.exit(1)
