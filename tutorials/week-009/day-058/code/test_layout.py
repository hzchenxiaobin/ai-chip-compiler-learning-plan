#!/usr/bin/env python3
"""test_layout.py —— 第 58 天验收测试：布局元信息、访存序列与视图/重排语义。

与 layout_lab.py 共用同一份数据构造方式，但测试点独立设计：
  A. Strides 公式的一般化（含 N=2 的批维，lab 里只有 N=1）；
  B. 偏移公式逐元素交叉验证（地址反查 vs stride 公式）；
  C. 访存序列用手算期望值对拍（不依赖 lab 的实现）；
  D. 视图 vs 重排的语义判定（shares_memory / contiguous）；
  E. 可选：mlir-opt Verifier 是否拒绝「谎报的转置布局」。

用法：python3 test_layout.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

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


def elem_strides(a: np.ndarray) -> tuple[int, ...]:
    return tuple(s // a.itemsize for s in a.strides)


def build(n: int, c: int, h: int, w: int):
    """同一逻辑张量 v(n,c,h,w) = c*(h*w) + h*w + w 的两种物理摆放。"""
    nchw = np.arange(n * c * h * w, dtype=np.float32).reshape(n, c, h, w)
    nhwc = np.ascontiguousarray(nchw.transpose(0, 2, 3, 1))
    return nchw, nhwc


def phys_offsets(a: np.ndarray, idxs) -> list[int]:
    """地址反查：逻辑下标落在 a 自身缓冲的第几格（元素）。"""
    base = a.ctypes.data
    out = []
    for idx in idxs:
        addr = base
        for i, s in zip(idx, a.strides):
            addr += i * s
        out.append((addr - base) // a.itemsize)
    return out


def formula_offsets(a: np.ndarray, idxs) -> list[int]:
    """stride 公式计算：offset = Σ idx_k × stride_k（独立于地址反查的第二条路）。"""
    es = elem_strides(a)
    return [sum(i * s for i, s in zip(idx, es)) for idx in idxs]


def main() -> int:
    global SKIP
    nchw, nhwc = build(1, 4, 2, 4)
    nhwc_view = nchw.transpose(0, 2, 3, 1)

    # ---- A. Strides 公式 ----
    check("NCHW strides == (C·H·W, H·W, W, 1) = (32, 8, 4, 1)",
          elem_strides(nchw) == (4 * 2 * 4, 2 * 4, 4, 1))
    check("NHWC strides == (H·W·C, W·C, C, 1) = (32, 16, 4, 1)",
          elem_strides(nhwc) == (2 * 4 * 4, 4 * 4, 4, 1))
    nchw2, nhwc2 = build(2, 4, 2, 4)
    check("N=2 一般化：NCHW strides == (32, 8, 4, 1)（批维不改变其余维步长）",
          elem_strides(nchw2) == (32, 8, 4, 1))
    check("N=2 一般化：NHWC strides == (32, 16, 4, 1)",
          elem_strides(nhwc2) == (32, 16, 4, 1))

    # ---- B. 偏移公式逐元素交叉验证（N=2 版本，含批维） ----
    ok = True
    for a in (nchw2, nhwc2):
        idxs = list(np.ndindex(*a.shape))
        if phys_offsets(a, idxs) != formula_offsets(a, idxs):
            ok = False
    check("地址反查 == stride 公式（两种布局 × 64 元素逐个对拍）", ok)

    # ---- C. 访存序列（手算期望，独立于 lab 实现） ----
    p1_n = formula_offsets(nchw, [(0, 0, 0, w) for w in range(4)])
    p1_h = formula_offsets(nhwc, [(0, 0, w, 0) for w in range(4)])
    check("P1 读一行像素：NCHW 偏移 == [0,1,2,3]（沿 W 连续）",
          p1_n == [0, 1, 2, 3])
    check("P1 读一行像素：NHWC 偏移 == [0,4,8,12]（w 步长 = C = 4）",
          p1_h == [0, 4, 8, 12])
    p2_n = formula_offsets(nchw, [(0, c, 0, 0) for c in range(4)])
    p2_h = formula_offsets(nhwc, [(0, 0, 0, c) for c in range(4)])
    check("P2 取像素全部通道：NCHW 偏移 == [0,8,16,24]（c 步长 = H·W = 8）",
          p2_n == [0, 8, 16, 24])
    check("P2 取像素全部通道：NHWC 偏移 == [0,1,2,3]（沿 C 连续）",
          p2_h == [0, 1, 2, 3])
    p3_n = formula_offsets(nchw, [(0, 1, h, w) for h in range(2) for w in range(4)])
    p3_h = formula_offsets(nhwc, [(0, h, w, 1) for h in range(2) for w in range(4)])
    check("P3 逐通道空间平面：NCHW 偏移 == [8..15]（连续 8 格）",
          p3_n == list(range(8, 16)))
    check("P3 逐通道空间平面：NHWC 偏移 == [1,5,9,13,17,21,25,29]（步长 C=4）",
          p3_h == [1, 5, 9, 13, 17, 21, 25, 29])

    def max_run(seq):
        best = cur = 1
        for x, y in zip(seq, seq[1:]):
            cur = cur + 1 if y == x + 1 else 1
            best = max(best, cur)
        return best

    check("向量化判定：沿 W（P1）NCHW 最长连续段 = 4 ≥ 128 位向量",
          max_run(p1_n) >= 4)
    check("向量化判定：沿 C（P2）NHWC 最长连续段 = 4，NCHW 只有 1",
          max_run(p2_h) >= 4 and max_run(p2_n) == 1)
    lines_n = len({(v * 4) // 64 for v in p3_n})
    lines_h = len({(v * 4) // 64 for v in p3_h})
    check("缓存行：P3 触碰 64B 行数 NCHW=1 < NHWC=2", lines_n == 1 and lines_h == 2)

    # ---- D. 视图 vs 重排语义 ----
    check("逻辑相等：nhwc[n,h,w,c] == nchw[n,c,h,w]（逐逻辑下标，N=2）",
          all(nchw2[n, c, h, w] == nhwc2[n, h, w, c]
              for n in range(2) for c in range(4)
              for h in range(2) for w in range(4)))
    check("视图：transpose(0,2,3,1) 与原存储共享内存 且 非 C-contiguous",
          np.shares_memory(nhwc_view, nchw)
          and not nhwc_view.flags["C_CONTIGUOUS"])
    check("重排：ascontiguousarray 不共享内存 且 C-contiguous",
          not np.shares_memory(nhwc, nchw) and nhwc.flags["C_CONTIGUOUS"])
    check("视图零收益：P2 经 nhwc_view 的偏移 == 经 nchw 的偏移",
          formula_offsets(nhwc_view, [(0, 0, 0, c) for c in range(4)]) == p2_n)
    check("NHWC 平铺顺序 == 逻辑读序搬家：nhwc.ravel() 前 8 项 == [0,8,16,24,1,9,17,25]",
          list(nhwc.ravel()[:8]) == [0.0, 8.0, 16.0, 24.0, 1.0, 9.0, 17.0, 25.0])

    # ---- E. 可选：mlir-opt Verifier 拒绝谎报布局 ----
    mlir = shutil.which("mlir-opt") or "/usr/lib/llvm-18/bin/mlir-opt"
    bad = Path(__file__).parent / "bad_layout.mlir"
    if shutil.which(mlir) or Path(mlir).exists():
        r = subprocess.run([mlir, str(bad)], capture_output=True, text=True)
        check("MLIR Verifier 拒绝把重排布局谎报成转置视图（exit != 0 且报 strided 错误）",
              r.returncode != 0 and "strided" in r.stderr)
    else:
        SKIP += 1
        print("[SKIP] 未找到 mlir-opt，跳过 Verifier 测试")

    print(f"test_layout: {PASS}/{PASS + FAIL} checks passed"
          + (f"（{SKIP} skipped）" if SKIP else ""))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
