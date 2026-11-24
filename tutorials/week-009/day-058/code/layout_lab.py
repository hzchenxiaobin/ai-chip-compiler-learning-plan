#!/usr/bin/env python3
"""layout_lab.py —— 第 58 天主实验：NCHW 与 NHWC，同一逻辑张量的两种物理摆放。

贯穿全文的例子（与 MLIR 侧 layout_orders.mlir 同一份数据）：
  N=1, C=4, H=2, W=4，共 32 个 f32
  逻辑内容 v(n,c,h,w) = c*8 + h*4 + w    （恰好等于它在 NCHW 连续数组里的物理位置）

三个对象：
  nchw      = arange(32).reshape(1,4,2,4)      # 物理 NCHW（框架图最常见的默认摆放）
  nhwc_view = nchw.transpose(0,2,3,1)          # NHWC 逻辑顺序，但物理没动（零拷贝视图）
  nhwc      = ascontiguousarray(nhwc_view)     # 物理 NHWC（真重排，新内存）

实验内容：
  1. 数据准备与逻辑相等性
  2. Layout 对照表（元信息：shape / strides / 连续性 / 存储归属）
  3. 访存序列：四种典型访问模式下两种布局的物理偏移序列
  4. 视图零成本但也零收益：经视图的访存序列与原布局完全相同
  5. 重排有成本才有收益：1x3x224x224 真实计时
  6. torch 对照：channels_last 就是官方版 NHWC 重排
  7. 断言收尾

用法：python3 layout_lab.py
"""

from __future__ import annotations

import platform
import time

import numpy as np

N, C, H, W = 1, 4, 2, 4
ITEMSIZE = 4  # f32

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


def elem_strides(a: np.ndarray) -> tuple[int, ...]:
    """numpy 字节 stride → 元素 stride，与 MLIR strided<[...]> 同口径。"""
    return tuple(s // a.itemsize for s in a.strides)


def phys_offsets(a: np.ndarray, idxs) -> list[int]:
    """地址反查：每个逻辑下标落在 a 自身底层缓冲的第几格（元素）。

    不用 stride 公式自证公式——直接从视图首地址按字节累加再归一化，
    与第 57 天 layout_lab.py 的 phys_offset 同一思路。
    """
    base = a.ctypes.data
    out = []
    for idx in idxs:
        addr = base
        for i, s in zip(idx, a.strides):
            addr += i * s
        out.append((addr - base) // a.itemsize)
    return out


def runs(seq: list[int]) -> list[tuple[int, int]]:
    """把偏移序列切成「连续段」：返回 [(起点, 长度), ...]。"""
    out = []
    for v in seq:
        if out and v == out[-1][0] + out[-1][1]:
            out[-1] = (out[-1][0], out[-1][1] + 1)
        else:
            out.append((v, 1))
    return out


def fmt_runs(seq: list[int]) -> str:
    return " ".join(f"[{s}..{s + l - 1}]×{l}" if l > 1 else f"[{s}]"
                    for s, l in runs(seq))


def cache_lines(seq: list[int]) -> int:
    """序列触碰的 64 字节缓存行数（f32：每行 16 个元素）。"""
    return len({(v * ITEMSIZE) // 64 for v in seq})


def vec4_possible(seq: list[int]) -> bool:
    """是否存在 ≥4 的连续段——128 位向量一次装 4×f32 的必要条件。"""
    return any(l >= 4 for _, l in runs(seq))


def main() -> int:
    print("=== 0. 环境 ===")
    print(f"python {platform.python_version()} · numpy {np.__version__} · "
          f"{platform.machine()} · {platform.system()}")
    print()

    # ----------------------------------------------------------
    print("=== 1. 数据准备：同一个逻辑张量，两种物理摆放 ===")
    print(f"形状 N={N}, C={C}, H={H}, W={W}，共 {N*C*H*W} 个 f32")
    print(f"逻辑内容 v(n,c,h,w) = c*{H*W} + h*{W} + w   （即每个元素的 NCHW 编号）")
    nchw = np.arange(N * C * H * W, dtype=np.float32).reshape(N, C, H, W)
    nhwc_view = nchw.transpose(0, 2, 3, 1)          # (n,c,h,w) -> (n,h,w,c)，零拷贝
    nhwc = np.ascontiguousarray(nhwc_view)          # 真重排：新内存、按 NHWC 连续摆放
    print(f"nchw      = arange(32).reshape(1,4,2,4)")
    print(f"nhwc_view = nchw.transpose(0,2,3,1)      # NHWC 逻辑顺序，物理没动")
    print(f"nhwc      = ascontiguousarray(nhwc_view) # NHWC 物理摆放（重排）")
    print(f"三者是同一个逻辑张量：np.array_equal(nhwc, nhwc_view) = "
          f"{np.array_equal(nhwc, nhwc_view)}")
    print()

    # ----------------------------------------------------------
    print("=== 2. Layout 对照表（元信息） ===")
    print(f"{'对象':<11}{'逻辑形状':<13}{'元素strides':<18}{'最内维':<12}"
          f"{'C连续':<7}{'与nchw同存储':<12}")
    rows = [
        ("nchw", nchw, "W (stride 1)"),
        ("nhwc_view", nhwc_view, "c (stride 8)"),
        ("nhwc", nhwc, "C (stride 1)"),
    ]
    for name, a, inner in rows:
        print(f"{name:<10}{str(a.shape):<12}{str(elem_strides(a)):<18}{inner:<8}"
              f"{str(a.flags['C_CONTIGUOUS']):<7}"
              f"{str(np.shares_memory(a, nchw)):<12}")
    print("注：strides 单位是元素；numpy 的 a.strides 是字节（各 ×4）。")
    print()

    # ----------------------------------------------------------
    print("=== 3. 访存序列：同一访问模式，两种布局的物理偏移 ===")
    patterns = [
        ("P1 读一行像素：固定 c=0,h=0，w=0..3（空间方向扫描）",
         [(0, 0, 0, w) for w in range(W)],        # NCHW 下标 (n,c,h,w)
         [(0, 0, w, 0) for w in range(W)]),       # NHWC 下标 (n,h,w,c)
        ("P2 取一个像素的全部通道：固定 h=0,w=0，c=0..3（通道归约）",
         [(0, c, 0, 0) for c in range(C)],
         [(0, 0, 0, c) for c in range(C)]),
        ("P3 取 c=1 的整幅空间平面：(h,w) 行优先（逐通道 pooling）",
         [(0, 1, h, w) for h in range(H) for w in range(W)],
         [(0, h, w, 1) for h in range(H) for w in range(W)]),
    ]
    for name, idx_nchw, idx_nhwc in patterns:
        print(f"--- {name} ---")
        for lay_name, arr, idxs in (("NCHW", nchw, idx_nchw),
                                    ("NHWC", nhwc, idx_nhwc)):
            seq = phys_offsets(arr, idxs)
            vec = "可以" if vec4_possible(seq) else "不行"
            print(f"  {lay_name}: 偏移 {seq}")
            print(f"        连续段 {fmt_runs(seq)} · 触碰缓存行 {cache_lines(seq)} 个"
                  f" · 128位向量(4×f32)一次装载: {vec}")
        print()

    print("--- P4 整体搬运（memcpy 一口气）：两种布局各自整体连续 ---")
    for lay_name, a in (("NCHW", nchw), ("NHWC", nhwc)):
        flat = phys_offsets(a, list(np.ndindex(*a.shape)))
        print(f"  {lay_name}: 全量偏移 0..{len(flat)-1} 连续 = "
              f"{flat == list(range(len(flat)))}")
    print()

    # ----------------------------------------------------------
    print("=== 4. 视图零成本，但也零收益 ===")
    print("同一个 P2（取像素 (h=0,w=0) 的全部通道），三种走法：")
    p2_c = [(0, c, 0, 0) for c in range(C)]       # 经 nchw 直接索引 (n,c,h,w)
    p2_v = [(0, 0, 0, c) for c in range(C)]       # 经 nhwc_view 索引 (n,h,w,c)
    p2_r = [(0, 0, 0, c) for c in range(C)]       # 经重排后的 nhwc 索引
    print(f"  经 nchw       （下标 (n,c,h,w)）: {phys_offsets(nchw, p2_c)}")
    print(f"  经 nhwc_view  （下标 (n,h,w,c)）: {phys_offsets(nhwc_view, p2_v)}")
    print(f"  经 nhwc 重排  （下标 (n,h,w,c)）: {phys_offsets(nhwc, p2_r)}")
    print("→ 转置视图只换「索引习惯」，物理访存一格没变；只有重排才改变访存序列")
    print()

    # ----------------------------------------------------------
    print("=== 5. 重排有成本，才有收益（真实计时） ===")
    big = np.arange(1 * 3 * 224 * 224, dtype=np.float32).reshape(1, 3, 224, 224)
    nbytes = big.nbytes
    print(f"输入: 1x3x224x224 f32 = {nbytes} 字节（约 {nbytes/1024:.0f} KiB）")

    t_view = min(time_per(lambda: big.transpose(0, 2, 3, 1)) for _ in range(1))
    t_repack = min(time_per(lambda: np.ascontiguousarray(big.transpose(0, 2, 3, 1)))
                   for _ in range(1))
    print(f"创建零拷贝视图 transpose(0,2,3,1)   : {t_view*1e6:8.1f} µs/次（最优）")
    print(f"真实重排 ascontiguousarray(同一句)  : {t_repack*1e3:8.3f} ms/次（最优）")
    print(f"差距约 {t_repack/t_view:.0f} 倍——「换登记表」与「搬家」的代价从来不在一个量级")
    print()

    # ----------------------------------------------------------
    print("=== 6. torch 对照：channels_last 就是官方版 NHWC 重排 ===")
    try:
        import torch
        tx = torch.arange(32, dtype=torch.float32).reshape(1, 4, 2, 4)
        ty = tx.to(memory_format=torch.channels_last)
        print(f"torch {torch.__version__}（本机 CPU 版，真实运行）")
        print(f"tx.stride() = {tuple(tx.stride())}            # NCHW：(H*W*C, H*W, W, 1)")
        print(f"ty.stride() = {tuple(ty.stride())}     # channels_last：(H*W*C, 1, W*C, C)")
        print("注意：torch 的逻辑维仍是 (N,C,H,W)，只是 strides 变了——")
        print("  同一块 NHWC 物理摆放，逻辑标签可以是 (N,H,W,C)（我们的 nhwc）")
        print("  也可以是 (N,C,H,W)+channels_last（torch 的 ty）——物理布局才是本质")
        print(f"numpy 侧等价视图 nhwc.transpose(0,3,1,2) 的元素 strides = "
              f"{elem_strides(nhwc.transpose(0, 3, 1, 2))}  # 与 ty.stride() 一致")
        print(f"torch.equal(tx, ty) = {torch.equal(tx, ty)}"
              f" · ty 与 tx 不同内存 = {ty.data_ptr() != tx.data_ptr()}")
        print(f"ty.is_contiguous(memory_format=channels_last) = "
              f"{ty.is_contiguous(memory_format=torch.channels_last)}")
        print("（说明：torch_npu 已安装但本机无 NPU 硬件，此实验在 CPU 上完成；")
        print("  在昇腾/GPU 上，channels_last 正是卷积类算子偏好的摆放。）")
    except ImportError:
        print("torch 不可用，跳过（本节为可选对照）")
    print()

    # ----------------------------------------------------------
    print("=== 7. 断言收尾 ===")
    v = lambda c, h, w: c * (H * W) + h * W + w
    check("nchw 的值 == 逻辑编号 v(c,h,w)（逐元素）",
          all(nchw[0, c, h, w] == v(c, h, w)
              for c in range(C) for h in range(H) for w in range(W)))
    check("nhwc 与 nhwc_view 逻辑相等（同一逻辑张量）",
          np.array_equal(nhwc, nhwc_view))
    check("nchw 元素 strides == (32, 8, 4, 1)",
          elem_strides(nchw) == (C*H*W, H*W, W, 1))
    check("nhwc_view 元素 strides == (32, 4, 1, 8)",
          elem_strides(nhwc_view) == (C*H*W, W, 1, H*W))
    check("nhwc 元素 strides == (32, 16, 4, 1)",
          elem_strides(nhwc) == (H*W*C, W*C, C, 1))
    check("nchw 是 C-contiguous", nchw.flags["C_CONTIGUOUS"])
    check("nhwc_view 不是 C-contiguous（只是个视图）",
          not nhwc_view.flags["C_CONTIGUOUS"])
    check("nhwc 是 C-contiguous（重排后恢复连续）",
          nhwc.flags["C_CONTIGUOUS"])
    check("nhwc_view 与 nchw 共享内存（零拷贝）",
          np.shares_memory(nhwc_view, nchw))
    check("nhwc 与 nchw 不共享内存（重排=搬家）",
          not np.shares_memory(nhwc, nchw))
    p1_n, p1_h = phys_offsets(nchw, patterns[0][1]), phys_offsets(nhwc, patterns[0][2])
    p2_n, p2_h = phys_offsets(nchw, patterns[1][1]), phys_offsets(nhwc, patterns[1][2])
    p3_n, p3_h = phys_offsets(nchw, patterns[2][1]), phys_offsets(nhwc, patterns[2][2])
    check(f"P1 NCHW 序列 == [0,1,2,3]（空间行连续）", p1_n == [0, 1, 2, 3])
    check(f"P1 NHWC 序列 == [0,4,8,12]（隔 4 跳格）", p1_h == [0, 4, 8, 12])
    check(f"P2 NCHW 序列 == [0,8,16,24]（通道隔 8 跳格）", p2_n == [0, 8, 16, 24])
    check(f"P2 NHWC 序列 == [0,1,2,3]（通道连续→1 次向量装载）", p2_h == [0, 1, 2, 3])
    check(f"P3 NCHW 序列 == [8..15]（通道平面连续）", p3_n == list(range(8, 16)))
    check(f"P3 NHWC 序列 == [1,5,9,13,17,21,25,29]（隔 4 跳格）",
          p3_h == [1, 5, 9, 13, 17, 21, 25, 29])
    check("视图零收益：经 nhwc_view 的 P2 序列 == 经 nchw 的 P2 序列",
          phys_offsets(nhwc_view, p2_v) == p2_n)
    check("两种布局各自整体连续（memcpy 一口气可搬）",
          phys_offsets(nchw, list(np.ndindex(*nchw.shape))) == list(range(32))
          and phys_offsets(nhwc, list(np.ndindex(*nhwc.shape))) == list(range(32)))
    try:
        import torch
        # torch 的 channels_last：逻辑维仍是 (N,C,H,W)，但 strides 是 (HWC,1,WC,C)
        # numpy 里等价物 = nhwc(逻辑 N,H,W,C) 转回 (N,C,H,W) 的零拷贝视图
        back_view = nhwc.transpose(0, 3, 1, 2)          # (n,h,w,c) -> (n,c,h,w)
        check("torch channels_last strides == numpy 同物理布局视图的 strides",
              tuple(torch.arange(32, dtype=torch.float32)
                    .reshape(1, 4, 2, 4)
                    .to(memory_format=torch.channels_last).stride())
              == elem_strides(back_view))
        ty = torch.arange(32, dtype=torch.float32).reshape(1, 4, 2, 4) \
            .to(memory_format=torch.channels_last)
        check("torch channels_last 的物理平铺顺序 == numpy 重排 nhwc 的平铺顺序",
              np.array_equal(ty.permute(0, 2, 3, 1).flatten().numpy(),
                             nhwc.reshape(-1)))
    except ImportError:
        print("[SKIP] torch 不可用，跳过该断言")
    print(f"layout_lab: {PASS}/{PASS + FAIL} checks passed")
    return 0 if FAIL == 0 else 1


def time_per(fn, repeat: int = 30) -> float:
    """多次取最优，降低调度噪声（与工程里 best-of-N 同口径）。"""
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


if __name__ == "__main__":
    raise SystemExit(main())
