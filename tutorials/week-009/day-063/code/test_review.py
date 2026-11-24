#!/usr/bin/env python3
"""test_review.py —— 第 63 天（第 9 周复盘）验收测试。

不依赖 review_lab.py 的打印流程，测试点独立设计（与全周 test_* 风格一致）：

  A. 周公式不变量：随机形状 + 转置/切片/广播视图，公式 vs ctypes 实测逐元素对账
  B. 命题一「Shape 相同但内存布局不同」：
     B1 行主序 vs 列主序（2,3）     B2 转置视图 vs 转置副本（3,2）
     B3 reshape 权利（连续/非连续） B4 4D NCHW vs NHWC（1,4,2,4）
     B5 广播 stride-0 与只读        B6 随机 100 组「同 shape 不同布局」对拍
  C. 命题二「动态维度不等于没有约束」（自包含 mini 约束器）：
     C1 rank 固定     C2 静态 K 失配被拒     C3 动态 M + 静态 K 放行
     C4 全动态记运行期账  C5 符号同名对账/绑定冲突  C6 非法维度构造被拒
     C7 mlir-opt 三房间裁决（若可用）
     C8 特化链复验（Day 62 工具，若可用）：exit=3 / exit=4
  D. 语义不变性：同一逻辑张量换身份，元素值恒等

运行：python3 test_review.py
"""

from __future__ import annotations

import random
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

PASS = FAIL = SKIP = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))


def skip(name: str, why: str) -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name}（{why}）")


def elem_strides(a: np.ndarray) -> tuple[int, ...]:
    return tuple(s // a.itemsize for s in a.strides)


def phys_offset(view: np.ndarray, store: np.ndarray, idx: tuple[int, ...]) -> int:
    addr = view.ctypes.data
    for i, s in zip(idx, view.strides):
        addr += i * s
    return (addr - store.ctypes.data) // view.itemsize


def formula_offset(offset0: int, strides: tuple[int, ...],
                   idx: tuple[int, ...]) -> int:
    return offset0 + sum(i * s for i, s in zip(idx, strides))


def base_store(view: np.ndarray) -> np.ndarray:
    """找到视图的底层存储（.base 链的尽头，广播视图的 base 是原数组）。"""
    b = view
    while b.base is not None:
        b = b.base
    return b


def find_mlir_opt() -> str | None:
    exe = shutil.which("mlir-opt")
    if exe:
        return exe
    for c in ("/usr/lib/llvm-18/bin/mlir-opt", "/usr/bin/mlir-opt-18"):
        if Path(c).is_file():
            return c
    return None


# ===========================================================================
print("== A. 周公式不变量（随机视图 fuzz：公式 vs ctypes 实测）==")

rng = random.Random(63)
a_bad = f_bad = 0
n_cases = n_elems = 0
for trial in range(120):
    nd = rng.randint(1, 4)
    shape = tuple(rng.randint(1, 4) for _ in range(nd))
    total = int(np.prod(shape))
    store = np.arange(1, total + 1, dtype=np.float32)
    v = store.reshape(shape)
    # 随机组合三种「身份变换」：转置、隔行切片、广播
    if nd >= 2 and rng.random() < 0.5:
        perm = list(range(nd))
        rng.shuffle(perm)
        v = v.transpose(perm)
    if nd >= 2 and rng.random() < 0.4:
        sl = tuple(slice(None, None, 2) if rng.random() < 0.5 else slice(None)
                   for _ in range(nd))
        try:
            v = v[sl]
        except IndexError:
            pass
    if rng.random() < 0.3 and v.ndim >= 1:
        target = (1,) + v.shape if rng.random() < 0.5 else v.shape + (1,)
        try:
            v = np.broadcast_to(v, target)
        except ValueError:
            pass
    store = base_store(v)
    offset0 = (v.ctypes.data - store.ctypes.data) // v.itemsize
    for idx in np.ndindex(v.shape):
        n_elems += 1
        got = phys_offset(v, store, tuple(int(i) for i in idx))
        want = formula_offset(offset0, elem_strides(v),
                              tuple(int(i) for i in idx))
        if got != want:
            f_bad += 1
    # 读回的值必须等于存储里那个位置的值（公式与数据都对才算对）
        if v[tuple(int(i) for i in idx)] != store[got]:
            a_bad += 1
    n_cases += 1
check("A1 周公式在 120 组随机视图上逐元素成立",
      f_bad == 0 and n_elems > 1000, f"{n_cases} 组视图、{n_elems} 个元素对账")
check("A2 公式指到的物理位置上真的躺着那个值", a_bad == 0)

# ===========================================================================
print("\n== B. 命题一：Shape 相同但内存布局不同 ==")

A = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
S_row = np.arange(1, 7, dtype=np.float32)                # [1,2,3,4,5,6]
id1 = S_row.reshape(2, 3)                                 # 行主序 (3,1)
S_col = np.ascontiguousarray(A.T).ravel().astype(np.float32)  # [1,4,2,5,3,6]
id2 = S_col.reshape(3, 2).T                               # 列主序 (1,2)

check("B1a 行主序/列主序同 shape 同值，但存储与 strides 都不同",
      id1.shape == id2.shape and np.array_equal(id1, id2)
      and elem_strides(id1) == (3, 1) and elem_strides(id2) == (1, 2)
      and not np.shares_memory(id1, id2))
row_seq = [phys_offset(id1, S_row, (i, j)) for i in range(2) for j in range(3)]
col_seq = [phys_offset(id2, S_col, (i, j)) for i in range(2) for j in range(3)]
check("B1b 逻辑读序的物理序列不同（[0,1,2,3,4,5] vs [0,2,4,1,3,5]）",
      row_seq == [0, 1, 2, 3, 4, 5] and col_seq == [0, 2, 4, 1, 3, 5])

id3 = id1.T                                               # 转置视图 (3,2) (1,3)
id4 = np.ascontiguousarray(id1.T)                         # 转置副本 (3,2) (2,1)
S_row[0] = 99.0
check("B2a 视图随原存储联动，副本不动（shape 都是 (3,2)）",
      id3.shape == id4.shape == (3, 2) and id3[0, 0] == 99.0 and id4[0, 0] == 1.0)
S_row[0] = 1.0
check("B2b reshape 权利：非连续视图被迫拷贝、连续副本保持零拷贝",
      not np.shares_memory(np.reshape(id3, (6,)), S_row)
      and np.shares_memory(np.reshape(id4, (6,)), id4))

fam = [(6,), (2, 3), (3, 2), (1, 6), (6, 1), (1, 2, 3)]
check("B3 连续存储的 reshape 家族全是零拷贝视图（元素数量不变 ⇒ 只改元信息）",
      all(np.shares_memory(S_row.reshape(t), S_row) for t in fam))
try:
    S_row.reshape((5,))
    n5 = False
except ValueError:
    n5 = True
check("B3b 元素数量变了的 reshape 直接被拒", n5)

nchw = np.arange(32, dtype=np.float32).reshape(1, 4, 2, 4)
nhwc_phys = np.ascontiguousarray(nchw.transpose(0, 2, 3, 1))
nhwc = nhwc_phys.transpose(0, 3, 1, 2)   # 同逻辑 shape (1,4,2,4)，NHWC strides
check("B4a 同 Shape (1,4,2,4)：NCHW strides (32,8,4,1) vs NHWC (32,1,16,4)",
      nchw.shape == nhwc.shape and np.array_equal(nchw, nhwc)
      and elem_strides(nchw) == (32, 8, 4, 1)
      and elem_strides(nhwc) == (32, 1, 16, 4))
check("B4b 两种布局的物理字节序列不同（NHWC 前 8 字节 [0,8,16,24,1,9,17,25]）",
      nhwc_phys.ravel()[:8].astype(int).tolist() == [0, 8, 16, 24, 1, 9, 17, 25]
      and nchw.ravel()[:8].astype(int).tolist() == list(range(8)))

r = np.array([7.0, 8.0, 9.0])
R = np.broadcast_to(r, (2, 3))
try:
    R[0, 0] = 99.0
    w_ok = False
except ValueError:
    w_ok = True
check("B5 广播视图：stride=(0,1)、共享 r 存储、只读", elem_strides(R) == (0, 1)
      and np.shares_memory(R, r) and w_ok
      and np.array_equal(np.broadcast_to(r, (2, 3)) + 0, np.tile(r, (2, 1))))

rng2 = random.Random(63)
ok_pairs = 0
for trial in range(100):
    nd = rng2.randint(2, 3)
    # 维度全部 ≥2：退化维（大小 1）会让不同布局的 strides 巧合相等，掩盖差异
    shape = tuple(rng2.randint(2, 4) for _ in range(nd))
    total = int(np.prod(shape))
    v = np.arange(total, dtype=np.float32).reshape(shape)
    perm = list(range(nd))
    rng2.shuffle(perm)
    if perm == list(range(nd)):
        perm[0], perm[1] = perm[1], perm[0]
    w = np.ascontiguousarray(v.transpose(perm)).transpose(
        tuple(np.argsort(perm)))
    if (w.shape == v.shape and np.array_equal(w, v)
            and not np.shares_memory(w, v)
            and elem_strides(w) != elem_strides(v)):
        ok_pairs += 1
check("B6 随机 100 组「同 shape、同值、不同布局、不共享内存」全部成立",
      ok_pairs == 100, f"{ok_pairs}/100")

# ===========================================================================
print("\n== C. 命题二：动态维度不等于没有约束（mini 约束器）==")


class ShapeError(Exception):
    pass


def valid_dim(d) -> bool:
    """维度合法值：正整数、符号名、未知 None。"""
    if isinstance(d, bool):
        return False
    if isinstance(d, int):
        return d >= 1
    if isinstance(d, str) and d:
        return True
    return d is None


def matmul_check(a, b):
    """mini MatMul 形状检查（Day 61 的三档知识：int / Sym(str) / None）。

    返回 (out_dims, runtime_checks)；违反约束抛 ShapeError。
    约束分三档对账：
      静态静态 → 编译期裁决（失配即拒）
      静态符号 → 绑定/对账（同名同值）
      涉及未知 → 记到运行期账（放行但欠账）
    """
    if not (isinstance(a, tuple) and isinstance(b, tuple)):
        raise ShapeError("输入必须是维度元组")
    if len(a) != 2 or len(b) != 2:
        raise ShapeError(f"rank 固定：MatMul 要 2 维，得到 {len(a)} 与 {len(b)}")
    for d in (*a, *b):
        if not valid_dim(d):
            raise ShapeError(f"非法维度值：{d!r}")
    runtime: list[tuple[str, object]] = []
    bindings: dict[str, int] = {}
    ka, kb = a[1], b[0]
    # ---- K 对账（三档）----
    if isinstance(ka, int) and isinstance(kb, int):
        if ka != kb:
            raise ShapeError(f"静态 K 失配：A.dim1={ka} vs B.dim0={kb}")
    elif isinstance(ka, int) and isinstance(kb, str):
        if kb in bindings and bindings[kb] != ka:
            raise ShapeError(f"符号 {kb} 已绑 {bindings[kb]}，又撞上 {ka}")
        bindings[kb] = ka
    elif isinstance(ka, str) and isinstance(kb, int):
        if ka in bindings and bindings[ka] != kb:
            raise ShapeError(f"符号 {ka} 已绑 {bindings[ka]}，又撞上 {kb}")
        bindings[ka] = kb
    elif isinstance(ka, str) and isinstance(kb, str):
        if ka != kb:
            raise ShapeError(f"两个符号维度必须同名（{ka} vs {kb}），"
                             "否则编译期无法对账")
    else:
        runtime.append(("K", (ka, kb)))          # 至少一边未知 → 运行期查
    out = (a[0], b[1])
    for i, d in enumerate(out):
        if isinstance(d, int) and d < 1:
            raise ShapeError(f"输出维必须 ≥1：dim{i}={d}")
    if any(d is None for d in out):
        runtime.append(("out", out))
    return out, runtime, bindings


try:
    matmul_check((2, 3, 1), (3, 2))
    r1 = False
except ShapeError:
    r1 = True
check("C1(实测) rank 固定：3 维输入被拒", r1)
try:
    matmul_check((2, 3), (3, 2, 1))
    r2 = False
except ShapeError:
    r2 = True
check("C1b B 侧 rank 也要 2", r2)

try:
    matmul_check((2, 4), (3, 2))
    r3 = False
except ShapeError as e:
    r3 = "静态 K 失配" in str(e)
check("C2 静态 K 失配（4 vs 3）被拒", r3)

out, rt, bd = matmul_check((None, 3), (3, 2))
check("C3 动态 M + 静态 K=3 放行：输出 (None,2)，K 静态对账、不欠运行期账",
      out == (None, 2) and all(tag != "K" for tag, _ in rt)
      and any(tag == "out" for tag, _ in rt))
out, rt, bd = matmul_check((None, None), (None, 2))
check("C4 全动态放行但欠账：K 记入运行期检查",
      out == (None, 2) and ("K", (None, None)) in rt)

out, rt, bd = matmul_check((2, "k"), ("k", 2))
check("C5a 符号同名对账放行（k==k）", out == (2, 2) and not rt)
try:
    matmul_check((2, "k"), ("j", 2))
    r5 = False
except ShapeError:
    r5 = True
check("C5b 异名符号被拒（编译期无法对账）", r5)
out, rt, bd = matmul_check((2, "k"), ("k", 2))
check("C5c 符号与静态可共存", bd == {})
try:
    matmul_check((2, -3), (3, 2))
    r6 = False
except ShapeError:
    r6 = True
check("C6 非法维度（负数）在构造期被拒", r6)
try:
    matmul_check((2, True), (3, 2))
    r6b = False
except ShapeError:
    r6b = True
check("C6b 布尔值冒充维度被拒", r6b)

mlir_opt = find_mlir_opt()
if mlir_opt:
    rooms = [
        ("房间 1 合法动态 ?x3·3x2", 0,
         "memref<?x3xf32>", "memref<3x2xf32>", "memref<?x2xf32>"),
        ("房间 2 全静态失配 2x4·3x2", 1,
         "memref<2x4xf32>", "memref<3x2xf32>", "memref<2x2xf32>"),
        ("房间 3 失明现场 ?x4·3x2", 0,
         "memref<?x4xf32>", "memref<3x2xf32>", "memref<?x2xf32>"),
    ]
    for tag, want, ta, tb, to in rooms:
        ir = (f"module {{\n  func.func @matmul(%a: {ta}, %b: {tb}, %o: {to}) {{\n"
              f"    linalg.matmul ins(%a, %b : {ta}, {tb}) outs(%o : {to})\n"
              f"    return\n  }}\n}}\n")
        p = subprocess.run([mlir_opt, "-"], input=ir,
                           capture_output=True, text=True)
        check(f"C7 {tag}: mlir-opt exit={p.returncode}",
              p.returncode == want)
else:
    skip("C7 mlir-opt 三房间", "mlir-opt 不可用")

spec_tool = (HERE.parent.parent / "day-062" / "code" / "specialize.py")
if spec_tool.is_file() and mlir_opt:
    blind_ir = OUT / "blind_k.mlir"
    blind_ir.write_text(
        "// 第 63 天复盘用：藏在 ? 后面的 K 失配（与 Day 62 k_blind 同款）\n"
        "module {\n"
        "  func.func @matmul(%a: memref<?x4xf32>, %b: memref<3x2xf32>,\n"
        "                    %o: memref<?x2xf32>) {\n"
        "    linalg.matmul ins(%a, %b : memref<?x4xf32>, memref<3x2xf32>)\n"
        "                  outs(%o : memref<?x2xf32>)\n"
        "    return\n  }\n}\n", encoding="utf-8")
    p1 = subprocess.run(
        [sys.executable, str(spec_tool), str(blind_ir),
         "--specialize-shape", "a=2x4,b=3x2", "-o", str(OUT / "tmp_c8.mlir")],
        capture_output=True, text=True)
    p2 = subprocess.run(
        [sys.executable, str(spec_tool), str(blind_ir),
         "--specialize-shape", "a=2x4,b=3x2", "--force",
         "-o", str(OUT / "tmp_c8.mlir")],
        capture_output=True, text=True)
    check("C8a 特化重推时 mini 层 K 对账拒绝（exit=3）", p1.returncode == 3)
    check("C8b --force 写出后 mlir-opt 拦下（exit=4）", p2.returncode == 4)
else:
    skip("C8 特化链复验", "缺 Day 62 工具或 mlir-opt")

# ===========================================================================
print("\n== D. 语义不变性：同一逻辑张量换身份，值恒等 ==")

S = np.arange(1, 7, dtype=np.float32)
P = np.concatenate([[99.0], S, [99.0]])                    # 带围栏的存储
A0 = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
S_col = np.ascontiguousarray(A0.T).ravel().astype(np.float32)
ident = [
    ("行主序视图", S.reshape(2, 3)),                         # strides (3,1) offset 0
    ("行主序副本", np.ascontiguousarray(S).reshape(2, 3)),   # 自己的存储
    ("列主序视图", S_col.reshape(3, 2).T),                   # strides (1,2)
    ("带偏移视图", P[1:7].reshape(2, 3)),                    # storage offset = 1
    ("三维中转",   S.reshape(1, 2, 3)[0].reshape(2, 3)),     # 零拷贝 reshape 链
]
check("D1 五种身份（视图/副本/列主序/偏移/三维中转）的逻辑值恒等",
      all(np.array_equal(v, A0) for _, v in ident))
ptrs = {v.ctypes.data for _, v in ident}
offset4 = (P[1:7].reshape(2, 3).ctypes.data - P.ctypes.data) // P.itemsize
check("D2 记账各不相同：≥3 个存储指针、2 套 strides、1 个非零偏移",
      len(ptrs) >= 3 and len({elem_strides(v) for _, v in ident}) == 2
      and offset4 == 1, f"{len(ptrs)} 个指针、偏移={offset4}")

# ===========================================================================
print()
print("=" * 66)
print(f"test_review: PASS {PASS} / FAIL {FAIL}"
      + (f" / SKIP {SKIP}" if SKIP else ""))
print("=" * 66)
sys.exit(0 if FAIL == 0 else 1)
