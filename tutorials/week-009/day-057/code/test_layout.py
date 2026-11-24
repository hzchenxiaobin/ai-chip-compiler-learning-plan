#!/usr/bin/env python3
"""test_layout.py —— 第 57 天验收测试：偏移公式、连续性判定和 reshape 语义。

与 layout_lab.py 共用一套核心函数，但测试点独立设计：
  A. 对任意 (offset, sizes, strides) 组合，逐元素验证 偏移公式；
  B. 连续性判定的边界：stride 含 0、窗口偏移、负 stride 的行为；
  C. reshape 视图 vs 拷贝 的判定必须用 shares_memory，不能看返回值形状。

用法：python3 test_layout.py
"""

from __future__ import annotations

import numpy as np

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def elem_strides(view: np.ndarray) -> tuple[int, ...]:
    return tuple(s // view.itemsize for s in view.strides)


def storage_offset(view: np.ndarray, store: np.ndarray) -> int:
    return (view.ctypes.data - store.ctypes.data) // view.itemsize


def phys_offset(view: np.ndarray, store: np.ndarray, idx) -> int:
    addr = view.ctypes.data
    for i, s in zip(idx, view.strides):
        addr += i * s
    return (addr - store.ctypes.data) // view.itemsize


def formula_holds(view: np.ndarray, store: np.ndarray) -> bool:
    """逐元素核对：物理偏移 == storage_offset + Σ idx_k * stride_k。"""
    off = storage_offset(view, store)
    es = elem_strides(view)
    for idx in np.ndindex(*view.shape):
        expect = off + sum(i * s for i, s in zip(idx, es))
        if phys_offset(view, store, idx) != expect:
            return False
        if view[idx] != store[phys_offset(view, store, idx)]:
            return False
    return True


def main() -> int:
    store = np.arange(12, dtype=np.float32)

    # A. 五种视图逐一验证偏移公式
    views = {
        "连续 3x4": store.reshape(3, 4),
        "转置 4x3": store.reshape(3, 4).T,
        "带偏移 2x3": store[2:8].reshape(2, 3),
        "跨步列切片 3x2": store.reshape(3, 4)[:, ::2],
        "三维 2x2x3": store.reshape(2, 2, 3),
    }
    for name, v in views.items():
        check(f"偏移公式对「{name}」成立（值与位置逐元素核对）",
              formula_holds(v, store))

    # B. 连续性判定的三个边界
    A = store.reshape(3, 4)
    row = A[0:1, :]                      # 形状 (1,4)：大小为 1 的维度上 stride 无关紧要
    col = A[:, 0:1]                      # 形状 (3,1)：行间跳 16 字节，判非连续
    check("形状 (1,4) 的行切片仍判 C-contiguous（大小 1 的维度不约束 stride）",
          row.flags["C_CONTIGUOUS"] and elem_strides(row) == (4, 1))
    check("形状 (3,1) 的列切片不连续（stride0=4 元素跨过整行）",
          not col.flags["C_CONTIGUOUS"])
    check("转置后 strides 顺序对调（元素口径）",
          elem_strides(A.T) == (1, 4))
    rev = store.reshape(3, 4)[:, ::-1]   # 负 stride：numpy 判非连续
    check("负 stride 切片不是 C-contiguous", not rev.flags["C_CONTIGUOUS"])
    check("带偏移的连续窗口仍判 C-contiguous（偏移不破坏连续性）",
          store[2:8].reshape(2, 3).flags["C_CONTIGUOUS"])

    # C. reshape 的视图/拷贝语义必须看内存归属
    A24 = store.reshape(3, 4)
    T43 = A24.T
    check("连续视图 reshape 是零拷贝视图",
          np.shares_memory(A24.reshape(12), store))
    check("非连续视图 reshape 静默拷贝",
          not np.shares_memory(T43.reshape(12), store))
    check("拷贝后数值不变",
          np.array_equal(T43.reshape(12), T43.reshape(12).copy()))
    check("reshape 拷贝值顺序 == 按行读转置（即按列读原数组）",
          T43.reshape(12).tolist() == [0, 4, 8, 1, 5, 9, 2, 6, 10, 3, 7, 11])

    total = PASS + FAIL
    print(f"\ntest_layout: {PASS}/{total} tests passed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
