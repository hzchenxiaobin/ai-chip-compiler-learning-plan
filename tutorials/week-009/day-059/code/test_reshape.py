#!/usr/bin/env python3
"""test_reshape.py —— 第 59 天验收测试：Reshape Verifier 的合法与非法用例。

与 reshape_lab.py 共用同一份 Verifier 实现（import），但测试点独立设计：
  A. infer_shape：-1 推断与元素数量违规（手算期望值）；
  B. try_view：零拷贝判定的手算对拍（视图给 strides，不可表达给 None）；
  C. 随机对拍：200 组随机「视图手术 + 随机目标形状」，
     mini.reshape 判定必须与 numpy 裁判（reshape 实际行为）完全一致；
  D. 语义：view / copy 两种结局下逻辑内容都逐元素不变；
  E. 偏移序列：手算的线性读序偏移；
  F. 可选：mlir-opt 的 Verifier 是否拒绝非法 collapse/reshape。

用法：python3 test_reshape.py
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from reshape_lab import estrides, infer_shape, mini_reshape, try_view

PASS = 0
FAIL = 0
SKIP = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def raises_value_error(fn, *args) -> bool:
    try:
        fn(*args)
        return False
    except ValueError:
        return True


def random_factorization(rng, n: int, max_dims: int = 4):
    """把 n 随机分解成 1~max_dims 个因子。"""
    dims = []
    while n > 1 and len(dims) < max_dims - 1:
        divs = [d for d in range(2, n + 1) if n % d == 0]
        d = rng.choice(divs)
        dims.append(d)
        n //= d
    dims.append(n)
    return dims


def make_random_source(rng, numel: int):
    """从连续基座出发做随机「视图手术」：转置 / 跨步切片 / 插 size-1 维。"""
    a = np.arange(numel).reshape(random_factorization(rng, numel))
    for _ in range(rng.integers(0, 3)):
        r = rng.random()
        if r < 0.4 and a.ndim >= 2:
            a = a.transpose(rng.permutation(a.ndim))
        elif r < 0.7:
            slicer = tuple(
                slice(None, None, int(rng.choice([1, 1, 2])))
                for _ in range(a.ndim))
            a = a[slicer]
        else:
            pos = rng.integers(0, a.ndim + 1)
            a = a.reshape(a.shape[:pos] + (1,) + a.shape[pos:])
        if a.size == 0:
            return None
    return a


def random_target(rng, numel: int):
    """随机目标形状：正确 numel 的随机划分，偶尔换成 -1 或错误的 numel。"""
    r = rng.random()
    if r < 0.08:                      # 错误的元素数
        return tuple(random_factorization(rng, numel + rng.choice([1, 2])))
    dims = random_factorization(rng, numel)
    if r < 0.25 and len(dims) >= 2:   # 把一个因子换成 -1
        dims[int(rng.integers(0, len(dims)))] = -1
    return tuple(dims)


def numpy_verdict(src, new_shape):
    try:
        r = src.reshape(new_shape)
    except ValueError:
        return "error", None
    if np.shares_memory(src, r):
        return "view", estrides(r)
    return "copy", None


def main() -> int:
    rng = np.random.default_rng(59)

    x = np.arange(12).reshape(3, 4)
    xT = x.T
    col = x[:, :2]
    z = np.arange(24).reshape(2, 12)[:, ::2]
    y = np.arange(24).reshape(2, 3, 4)          # 连续 3 维基座

    # ---- A. infer_shape ----
    print("== A. infer_shape：-1 推断与元素数量 ==")
    check("A1 (2,3,4) + (-1,6) -> (4,6)",
          infer_shape((-1, 6), 24) == (4, 6))
    check("A2 (2,3,4) + (12,-1) -> (12,2)",
          infer_shape((12, -1), 24) == (12, 2))
    check("A3 (2,3,4) + (-1,4,3) -> (2,4,3)",
          infer_shape((-1, 4, 3), 24) == (2, 4, 3))
    check("A4 numel 24 != 25 报错", raises_value_error(infer_shape, (5, 5), 24))
    check("A5 24 不能被 5 整除报错", raises_value_error(infer_shape, (-1, 5), 24))
    check("A6 两个 -1 报错", raises_value_error(infer_shape, (-1, -1), 24))

    # ---- B. try_view 手算对拍 ----
    print("== B. try_view：零拷贝判定（手算期望）==")
    check("B1 连续 (2,3,4)/(12,4,1) -> (6,4) 给 (4,1)",
          try_view((2, 3, 4), (12, 4, 1), (6, 4)) == (4, 1))
    check("B2 连续 (2,3,4)/(12,4,1) -> (24,) 给 (1,)",
          try_view((2, 3, 4), (12, 4, 1), (24,)) == (1,))
    check("B3 连续 (2,3,4)/(12,4,1) -> (2,12) 给 (12,1)",
          try_view((2, 3, 4), (12, 4, 1), (2, 12)) == (12, 1))
    check("B4 连续 (2,3,4)/(12,4,1) -> (2,3,2,2) 给 (12,4,2,1)",
          try_view((2, 3, 4), (12, 4, 1), (2, 3, 2, 2)) == (12, 4, 2, 1))
    check("B5 转置 (4,3)/(1,4) -> (12,) 不可表达",
          try_view((4, 3), (1, 4), (12,)) is None)
    check("B6 转置 (4,3)/(1,4) -> (2,6) 不可表达",
          try_view((4, 3), (1, 4), (2, 6)) is None)
    check("B7 列切片 (3,2)/(4,1) -> (6,) 不可表达",
          try_view((3, 2), (4, 1), (6,)) is None)
    check("B8 跨步 (2,6)/(12,2) -> (3,4) 给 (8,2)",
          try_view((2, 6), (12, 2), (3, 4)) == (8, 2))
    check("B9 元素数不同直接不可表达",
          try_view((2, 3, 4), (12, 4, 1), (5, 5)) is None)

    # ---- C. 随机对拍 ----
    print("== C. 随机对拍：mini.reshape vs numpy（200 组）==")
    mismatches = []
    seen_view = seen_copy = seen_error = 0
    trials = 0
    while trials < 200:
        numel = int(rng.choice([12, 24, 36, 60, 120]))
        src = make_random_source(rng, numel)
        if src is None or src.size == 0:
            continue
        tgt = random_target(rng, src.size)
        trials += 1
        v_mini, info_mini = mini_reshape(src, tgt)
        v_np, st_np = numpy_verdict(src, tgt)
        v_mini_np = "copy" if v_mini == "reject" else v_mini
        if v_mini_np == "view":
            seen_view += 1
        elif v_mini_np == "copy":
            seen_copy += 1
        else:
            seen_error += 1
        ok = v_mini_np == v_np
        if ok and v_np == "view":
            full = infer_shape(tgt, src.size)
            ok = all(p == a for p, a, d in
                     zip(info_mini, st_np, full) if d != 1)
        if not ok:
            mismatches.append((src.shape, estrides(src), tgt,
                               v_mini, info_mini, v_np, st_np))
    check(f"C1 200 组随机用例判定全部一致（view/copy/error 各归其位）",
          not mismatches)
    if mismatches:
        for m in mismatches[:5]:
            print(f"     不一致: {m}")
    check(f"C2 三种结局都出现过（view={seen_view} copy={seen_copy} "
          f"error={seen_error}）",
          seen_view > 0 and seen_copy > 0 and seen_error > 0)

    # ---- D. 语义不变 ----
    print("== D. 语义：两种结局的逻辑内容 ==")
    r_view = x.reshape(2, 6)
    r_copy = xT.reshape(12)
    check("D1 视图结果逐元素等于源展开",
          np.array_equal(r_view.ravel(), x.ravel()))
    check("D2 拷贝结果也逐元素等于源展开",
          np.array_equal(r_copy, xT.ravel()))
    check("D3 视图共享底层存储，拷贝不共享",
          np.shares_memory(x, r_view) and not np.shares_memory(xT, r_copy))

    # ---- E. 偏移序列（手算） ----
    print("== E. 偏移序列（手算期望值）==")

    def linear_offsets(a):
        base = a.ctypes.data
        out = []
        for idx in np.ndindex(*a.shape):
            addr = base + sum(i * s for i, s in zip(idx, a.strides))
            out.append((addr - base) // a.itemsize)
        return out

    check("E1 xT 的线性读序偏移 == [0,4,8,1,5,9,2,6,10,3,7,11]",
          linear_offsets(xT) == [0, 4, 8, 1, 5, 9, 2, 6, 10, 3, 7, 11])
    check("E2 z 的线性读序偏移 == [0,2,...,22]（步长 2 等差）",
          linear_offsets(z) == list(range(0, 24, 2)))
    check("E3 y.transpose(1,0,2) 的读序前 5 项 == [0,1,2,3,12]"
          "（内维连续，跨 j 时跳到 12）",
          linear_offsets(y.transpose(1, 0, 2))[:5] == [0, 1, 2, 3, 12])
    check("E4 因此 (3,2,4)/(4,12,1) 合并成 (3,8) 不可表达"
          "（12 != 4×1，块合不上）",
          try_view((3, 2, 4), (4, 12, 1), (3, 8)) is None)

    # ---- F. MLIR Verifier（可选） ----
    print("== F. mlir-opt Verifier（环境没有则跳过）==")
    mlir_opt = shutil.which("mlir-opt") or shutil.which("mlir-opt-18")
    for cand in ("/usr/lib/llvm-18/bin/mlir-opt", "/usr/bin/mlir-opt-18"):
        if not mlir_opt and Path(cand).exists():
            mlir_opt = cand
            break
    if mlir_opt is None:
        global SKIP
        SKIP += 2
        print("[SKIP] F1/F2 未找到 mlir-opt，跳过 MLIR 侧检查")
    else:
        here = Path(__file__).resolve().parent

        def run_mlir(fname):
            return subprocess.run(
                [mlir_opt, str(here / fname)],
                capture_output=True, text=True)

        bad = run_mlir("bad_reshape.mlir")
        check("F1 bad_reshape.mlir 被 Verifier 拒绝（exit != 0）",
              bad.returncode != 0
              and "non-contiguous" in bad.stderr)
        good = run_mlir("reshape_views.mlir")
        check("F2 reshape_views.mlir 通过解析与验证（exit == 0）",
              good.returncode == 0)

    print()
    print(f"test_reshape: {PASS}/{PASS + FAIL} passed"
          + (f", {SKIP} skipped" if SKIP else ""))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
