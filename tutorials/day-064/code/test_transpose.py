#!/usr/bin/env python3
"""test_transpose.py —— 第 64 天验收测试：mini.transpose Operation + Verifier。

分节：
  A  Operation 与 IR 文本往返（打印 → 解析 → 等价）
  B  Verifier 正例
  C  Verifier 反例与报错质量
  D  推导对拍：mini vs numpy（固定 12 组 + 随机 300 组）
  E  视图语义（strides 重排 / 零拷贝 / 写穿联动 / 连续性被破坏）
  F  搬家语义（连续化 / 值相等 / 内存独立）
  G  排列性质（逆排列 / 阶 / 对合与非对合）
  H  MLIR 对照（linalg.transpose 真实裁决，mlir-opt 不可用则整节跳过）

用法：python3 test_transpose.py   （在 code/ 目录下）
"""

from __future__ import annotations

import random
import sys

import numpy as np

from transpose_lab import (
    MiniTransposeOp, parse_mini_transpose, perm_order, permute_strides,
    infer_transposed_shape, inverse_perm, verify_transpose,
    find_mlir_opt, linalg_transpose_ir, mlir_verdict, estrides,
    linear_read_offsets, ref_transpose,
)

PASS = 0
FAIL = 0
SKIP = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))
    return cond


rng = random.Random(64)

print("== A. Operation 与 IR 文本往返 ==")
ops = [
    MiniTransposeOp("%t", "%in", (2, 3), "f32", (1, 0)),
    MiniTransposeOp("%t", "%in", (2, 3, 4), "f32", (1, 2, 0)),
    MiniTransposeOp("%t", "%in", (5,), "f32", (0,)),
    MiniTransposeOp("%t", "%in", (2, 3), "f32", (0, 1)),
    MiniTransposeOp("%t", "%in", (3, 2), "f16", (1, 0)),
]
round_ok = True
for op in ops:
    rt = parse_mini_transpose(op.print_ir())
    round_ok &= (rt == op)
check("A1 打印→解析往返一致（2D/3D/1D/恒等/f16 共 5 例）", round_ok)
check("A2 默认结果形状由推导补全",
      MiniTransposeOp("%t", "%in", (2, 3), "f32", (1, 0)).result_shape == (3, 2))
check("A3 推导失败的 op 结果形状保持 None",
      MiniTransposeOp("%t", "%in", (2, 3), "f32", (1, 1)).result_shape is None)
try:
    parse_mini_transpose("%t = mini.add %in : (2x3xf32) -> (2x3xf32)")
    bad = False
except ValueError:
    bad = True
check("A4 非 transpose 行解析报 ValueError", bad)
check("A5 IR 文本含 permutation 属性与类型签名",
      "permutation = [1, 0]" in ops[0].print_ir()
      and ": (2x3xf32) -> (3x2xf32)" in ops[0].print_ir())

print("\n== B. Verifier 正例 ==")
positives = [
    ("B1 2D 交换", (2, 3), (1, 0), (3, 2)),
    ("B2 3D 循环 (1,2,0)", (2, 3, 4), (1, 2, 0), (3, 4, 2)),
    ("B3 3D 循环 (2,0,1)", (2, 3, 4), (2, 0, 1), (4, 2, 3)),
    ("B4 恒等（no-op，合法）", (2, 3), (0, 1), (2, 3)),
    ("B5 1D 恒等", (5,), (0,), (5,)),
    ("B6 size-1 维参与", (1, 3), (1, 0), (3, 1)),
    ("B7 高秩 5D", (2, 3, 4, 5, 6), (4, 2, 0, 3, 1), (6, 4, 2, 5, 3)),
]
for name, sh, pm, rs in positives:
    check(name, verify_transpose(sh, pm, rs) == [])

print("\n== C. Verifier 反例与报错质量 ==")
negatives = [
    ("C1 E1 排列过长", (2, 3), (0, 1, 2), (3, 2, 1), "[E1]"),
    ("C2 E1 排列过短", (2, 3, 4), (0, 1), (3, 4), "[E1]"),
    ("C3 E2 值越上界", (2, 3), (2, 0), (3, 2), "[E2]"),
    ("C4 E2 值为负", (2, 3), (-1, 0), (3, 2), "[E2]"),
    ("C5 E3 重复维", (2, 3), (1, 1), (3, 3), "[E3]"),
    ("C6 E3 高秩重复", (2, 3, 4), (0, 1, 1), (2, 3, 3), "[E3]"),
    ("C7 E4 形状写错", (2, 3), (1, 0), (2, 3), "[E4]"),
    ("C8 E4 3D 维序错", (2, 3, 4), (1, 2, 0), (4, 3, 2), "[E4]"),
    ("C9 E4 结果秩不符", (2, 3), (1, 0), (3, 2, 1), "[E4]"),
]
for name, sh, pm, rs, tag in negatives:
    errs = verify_transpose(sh, pm, rs)
    check(name, bool(errs) and all(e.startswith(tag) for e in errs))

e2 = verify_transpose((2, 3), (2, 0), (3, 2))[0]
check("C10 E2 报错写明位置(第 0 项)、非法值(2)与合法范围(0..1)",
      "第 0 项" in e2 and "2" in e2 and "0..1" in e2)
e4 = verify_transpose((2, 3), (1, 0), (2, 3))[0]
check("C11 E4 报错写明期望(3=输入第 1 维)与实际(2)及约定",
      "应为 3" in e4 and "输入第 1 维" in e4 and "实际写的 2" in e4)
check("C12 检查顺序：E1 错误时不产生 E2/E3/E4 报错（长度不对无从查起）",
      verify_transpose((2, 3), (7,), (3,)) == [
          verify_transpose((2, 3), (7,), (3,))[0]])
check("C13 越界值不会被拿去索引 shape（E2 先于 E4 触发）",
      verify_transpose((2, 3), (5, 0), (3, 2))[0].startswith("[E2]"))

print("\n== D. 推导对拍：mini vs numpy ==")
A = np.arange(1, 7, dtype=np.float32).reshape(2, 3)
B = np.arange(24, dtype=np.float32).reshape(2, 3, 4)
cases = [
    ("D1 2D 交换", A, (1, 0)), ("D2 2D 恒等", A, (0, 1)),
    ("D3 3D (1,2,0)", B, (1, 2, 0)), ("D4 3D (2,0,1)", B, (2, 0, 1)),
    ("D5 3D (2,1,0)", B, (2, 1, 0)), ("D6 3D 换后两维", B, (0, 2, 1)),
    ("D7 1D", np.arange(5, dtype=np.float32), (0,)),
    ("D8 size-1", np.ones((1, 3), dtype=np.float32), (1, 0)),
    ("D9 切片源", np.arange(12, dtype=np.float32).reshape(3, 4)[:, :2], (1, 0)),
    ("D10 转置链", np.transpose(B, (1, 2, 0)), (2, 0, 1)),
    ("D11 4D", np.arange(60, dtype=np.float32).reshape(3, 4, 5, 1), (3, 1, 0, 2)),
    ("D12 广播视图源", np.broadcast_to(
        np.arange(3, dtype=np.float32), (2, 3)), (1, 0)),
]
for name, src, pm in cases:
    actual = np.transpose(src, pm)
    check(name,
          infer_transposed_shape(src.shape, pm) == actual.shape
          and permute_strides(estrides(src), pm) == estrides(actual)
          and np.array_equal(actual, ref_transpose(src, pm)))

rand_ok = 0
for _ in range(300):
    rank = rng.randint(1, 5)
    shape = tuple(rng.randint(1, 5) for _ in range(rank))
    pm = list(range(rank))
    rng.shuffle(pm)
    x = np.arange(int(np.prod(shape)), dtype=np.float32).reshape(shape)
    y = np.transpose(x, tuple(pm))
    if (infer_transposed_shape(shape, tuple(pm)) == y.shape
            and permute_strides(estrides(x), tuple(pm)) == estrides(y)
            and np.shares_memory(x, y)
            and np.array_equal(y, ref_transpose(x, tuple(pm)))):
        rand_ok += 1
check("D13 随机 300 组：shape/strides/值/零拷贝四方一致", rand_ok == 300,
      f"{rand_ok}/300")

print("\n== E. 视图语义 ==")
V = A.T
check("E1 视图配方：A(2,3)/(3,1) --perm(1,0)--> (3,2)/(1,3)",
      V.shape == (3, 2) and estrides(V) == (1, 3))
check("E2 零拷贝：视图与源共享存储", np.shares_memory(V, A))
V[0, 1] = 99.0
check("E3 写穿联动：V[0,1]=99 使 A[1,0]=99", A[1, 0] == 99.0)
V[0, 1] = 4.0
check("E4 连续性被破坏：连续源转置后不再 C-连续（rank>1 且非恒等）",
      A.flags["C_CONTIGUOUS"] and not V.flags["C_CONTIGUOUS"]
      and linear_read_offsets(V) == [0, 3, 1, 4, 2, 5])
view_ok = sum(
    1 for _ in range(100)
    if (lambda s: np.shares_memory(
        np.transpose(s, pm := tuple(rng.sample(range(s.ndim), s.ndim))), s))(
        np.arange(int(np.prod(shape := tuple(
            rng.randint(1, 4) for _ in range(rng.randint(2, 5))))),
            dtype=np.float32).reshape(shape)))
check("E5 100 组随机转置全部零拷贝（转置永远可视图化）", view_ok == 100)
check("E6 size-1 维转置 strides 仍正确：(1,3)/(3,1)→(3,1)/(1,3)",
      estrides(np.transpose(np.ones((1, 3), dtype=np.float32), (1, 0)))
      == (1, 3))

print("\n== F. 搬家语义 ==")
C = np.ascontiguousarray(A.T)
check("F1 搬家后 C-连续且 strides 规整为 (2,1)",
      C.flags["C_CONTIGUOUS"] and estrides(C) == (2, 1))
check("F2 值与视图版一致（语义不变）", np.array_equal(C, A.T))
check("F3 内存独立（真重排，非视图）", not np.shares_memory(C, A))
check("F4 读序偏移被规整为 0..5",
      linear_read_offsets(C) == [0, 1, 2, 3, 4, 5]
      and list(map(int, C.ravel())) == [1, 4, 2, 5, 3, 6])

print("\n== G. 排列性质 ==")
check("G1 inverse_perm 定义 inv[perm[i]]=i（5 组随机）",
      all(all(inv[pm[i]] == i for i in range(len(pm)))
          for pm in [(1, 0), (1, 2, 0), (2, 0, 1), (0, 1), (1, 2, 3, 0)]
          for inv in [inverse_perm(pm)]))
check("G2 阶：恒等 1 / 对合 2 / 3-循环 3 / 4-循环 4",
      perm_order((0, 1)) == 1 and perm_order((1, 0)) == 2
      and perm_order((1, 2, 0)) == 3 and perm_order((1, 2, 3, 0)) == 4)
y1 = np.transpose(np.transpose(B, (1, 2, 0)), (1, 2, 0))
y2 = np.transpose(np.transpose(B, (1, 2, 0)), inverse_perm((1, 2, 0)))
check("G3 非对合陷阱：同款转置两次≠原样，排列+逆排列=原样",
      not np.array_equal(y1, B) and np.array_equal(y2, B))
check("G4 2D 交换是唯一非平凡对合（转两次必回原样）",
      np.array_equal(np.transpose(np.transpose(A, (1, 0)), (1, 0)), A)
      and inverse_perm((1, 0)) == (1, 0))
check("G5 逆排列的形状推导满足『回程』约束：3x4x2 经 (2,0,1) 回 2x3x4",
      infer_transposed_shape((3, 4, 2), (2, 0, 1)) == (2, 3, 4))

print("\n== H. MLIR 对照（linalg.transpose 真实裁决） ==")
if find_mlir_opt() is None:
    print("[SKIP] H 整节：mlir-opt 不可用")
    SKIP += 1
else:
    mlir_cases = [
        ("H1 合法 2D", "memref<2x3xf32>", "memref<3x2xf32>", "[1, 0]", 0),
        ("H2 约定A 4x2x3", "memref<2x3x4xf32>", "memref<4x2x3xf32>",
         "[2, 0, 1]", 0),
        ("H3 约定B 3x4x2", "memref<2x3x4xf32>", "memref<3x4x2xf32>",
         "[2, 0, 1]", 1),
        ("H4 E1 长度", "memref<2x3xf32>", "memref<3x2xf32>", "[0, 1, 2]", 1),
        ("H5 E3 双射", "memref<2x3xf32>", "memref<3x3xf32>", "[1, 1]", 1),
        ("H6 E2 值域", "memref<2x3xf32>", "memref<3x2xf32>", "[2, 0]", 1),
        ("H7 E4 形状", "memref<2x3xf32>", "memref<2x3xf32>", "[1, 0]", 1),
        ("H8 恒等合法", "memref<2x3xf32>", "memref<2x3xf32>", "[0, 1]", 0),
    ]
    for name, in_t, out_t, pm, expect in mlir_cases:
        code, _ = mlir_verdict(linalg_transpose_ir(in_t, out_t, pm))
        check(name, code == expect, f"exit={code}")
    _, m3 = mlir_verdict(linalg_transpose_ir(
        "memref<2x3x4xf32>", "memref<3x4x2xf32>", "[2, 0, 1]"))
    check("H9 M3 报错原文把约定写在错误里（dim(input, permutation[0])）",
          "dim(input, permutation[0])" in m3 and "= 4" in m3)
    _, m6a = mlir_verdict(linalg_transpose_ir(
        "memref<2x3xf32>", "memref<3x2xf32>", "[2, 0]"))
    _, m6b = mlir_verdict(linalg_transpose_ir(
        "memref<2x3xf32>", "memref<3x2xf32>", "[2, 0]"))
    check("H10 越界排列两次报错的乱码值不同（值域检查缺失的现场）",
          m6a != m6b)

print()
print(f"test_transpose: PASS {PASS} / FAIL {FAIL}"
      + (f" / SKIP {SKIP}" if SKIP else ""))
sys.exit(0 if FAIL == 0 else 1)
