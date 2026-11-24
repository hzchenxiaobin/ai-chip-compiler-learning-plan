#!/usr/bin/env python3
"""layout_lab.py —— 第 57 天：用同一底层存储构造连续 Tensor、转置视图和带偏移切片。

核心问题：Shape、Stride、Storage Offset、Contiguous 分别描述了什么？
           为什么「逻辑形状相同」不代表「内存布局相同」？

约定：元素值 == 它在底层存储中的物理位置（0..5），
      这样打印出的「值 @ 偏移」肉眼即可核对，不用信任何公式。

用法：python3 layout_lab.py
"""

from __future__ import annotations

import numpy as np

CHECKS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(cond), detail))


def elem_strides(view: np.ndarray) -> tuple[int, ...]:
    """把字节 stride 换算成「元素 stride」，与 MLIR strided<[...]> 同口径。"""
    return tuple(s // view.itemsize for s in view.strides)


def storage_offset(view: np.ndarray, store: np.ndarray) -> int:
    """视图首元素相对底层存储首元素的偏移（单位：元素）。

    对应 MLIR memref 类型里的 offset: N。
    """
    return (view.ctypes.data - store.ctypes.data) // view.itemsize


def phys_offset(view: np.ndarray, store: np.ndarray, idx: tuple[int, ...]) -> int:
    """逻辑下标 idx 的元素在底层存储中的物理偏移（单位：元素）。"""
    addr = view.ctypes.data
    for i, s in zip(idx, view.strides):
        addr += i * s
    return (addr - store.ctypes.data) // view.itemsize


def dump_view(tag: str, view: np.ndarray, store: np.ndarray) -> None:
    es = elem_strides(view)
    print(f"{tag}: shape={view.shape}  strides={es} 元素"
          f"（{view.strides} 字节）  storage_offset={storage_offset(view, store)}")
    print(f"  C-contiguous={view.flags['C_CONTIGUOUS']}  "
          f"F-contiguous={view.flags['F_CONTIGUOUS']}  "
          f"与 store 共享内存={np.shares_memory(view, store)}")
    for i in range(view.shape[0]):
        cells = []
        for j in range(view.shape[1]):
            off = phys_offset(view, store, (i, j))
            cells.append(f"{tag}[{i},{j}]={view[i, j]:.0f} @ 偏移{off}")
        print("  " + "   ".join(cells))
    print()


def main() -> None:
    # ---------- 1. 底层存储：6 个 f32 连续排布 ----------
    store = np.arange(6, dtype=np.float32)
    print("=== 1. 底层存储 store ===")
    print(f"store: shape={store.shape}  itemsize={store.itemsize} 字节  "
          f"strides={store.strides} 字节")
    print(f"值：{store.tolist()}（元素值 ＝ 它的物理位置，方便核对）\n")

    # ---------- 2. 视图 A：连续 Tensor（2×3，行主序） ----------
    A = store.reshape(2, 3)
    print("=== 2. 视图 A = store.reshape(2, 3)：连续 Tensor ===")
    dump_view("A", A, store)

    # ---------- 3. 视图 T：转置视图（3×2，只改元信息） ----------
    T = A.T
    print("=== 3. 视图 T = A.T：转置视图（同一存储，零拷贝） ===")
    dump_view("T", T, store)

    # ---------- 4. 视图 B：带 storage offset 的切片 ----------
    # 注意：B 的窗口内部仍是 (2,1) 连续的——偏移与连续性是两个独立属性
    B = store[1:5].reshape(2, 2)
    print("=== 4. 视图 B = store[1:5].reshape(2, 2)：storage_offset = 1 ===")
    dump_view("B", B, store)

    # ---------- 5. 对照实验：reshape 连续 vs 非连续 ----------
    print("=== 5. 对照实验：同一句 reshape，两种代价 ===")
    a_flat = A.reshape(6)
    t_flat = T.reshape(6)
    print(f"A.reshape(6) 与 store 共享内存: {np.shares_memory(a_flat, store)}"
          "  → 元信息操作，零拷贝")
    print(f"T.reshape(6) 与 store 共享内存: {np.shares_memory(t_flat, store)}"
          "  → 必须拷贝出新的连续数组")
    print(f"T.reshape(6) 值: {t_flat.tolist()}")
    T2 = np.ascontiguousarray(T)
    print(f"显式拷贝 ascontiguousarray(T): strides={T2.strides} 字节，"
          f"C-contiguous={T2.flags['C_CONTIGUOUS']}，"
          f"与 store 共享内存={np.shares_memory(T2, store)}")
    print(f"写回验证：T2 内容 == T 内容 → {np.array_equal(T2, T)}\n")

    # ---------- 6. 断言：偏移公式逐项核对 ----------
    # 物理偏移 = storage_offset + i * stride0 + j * stride1（单位：元素）
    for name, view, off_expect, s0, s1 in [
        ("A", A, 0, 3, 1),
        ("T", T, 0, 1, 3),
        ("B", B, 1, 2, 1),
    ]:
        check(f"{name} 的 storage_offset == {off_expect}",
              storage_offset(view, store) == off_expect)
        check(f"{name} 的元素 strides == ({s0}, {s1})",
              elem_strides(view) == (s0, s1))
        ok = all(
            phys_offset(view, store, (i, j)) == off_expect + i * s0 + j * s1
            for i in range(view.shape[0]) for j in range(view.shape[1]))
        check(f"{name} 每个元素满足 偏移 = off + i*{s0} + j*{s1}", ok)
        ok2 = all(
            view[i, j] == store[phys_offset(view, store, (i, j))]
            for i in range(view.shape[0]) for j in range(view.shape[1]))
        check(f"{name} 的值 == store 中该偏移处的值", ok2)

    check("A 是 C-contiguous", A.flags["C_CONTIGUOUS"])
    check("T 不是 C-contiguous 但 F-contiguous",
          not T.flags["C_CONTIGUOUS"] and T.flags["F_CONTIGUOUS"])
    check("B 虽有偏移 1 但仍 C-contiguous（偏移与连续性无关）",
          B.flags["C_CONTIGUOUS"] and storage_offset(B, store) == 1)
    check("T[i,j] == A[j,i]", np.array_equal(T, A.T))
    check("A.reshape(6) 是视图（共享内存）", np.shares_memory(a_flat, store))
    check("T.reshape(6) 是拷贝（不共享内存）", not np.shares_memory(t_flat, store))
    check("T.reshape(6) 值顺序 == 按列读 A", t_flat.tolist() == [0, 3, 1, 4, 2, 5])

    passed = sum(1 for _, ok, _ in CHECKS if ok)
    print("=== 6. 断言结果 ===")
    for name, ok, _ in CHECKS:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}")
    total = len(CHECKS)
    print(f"\nlayout_lab: {passed}/{total} checks passed")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
