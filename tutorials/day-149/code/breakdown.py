#!/usr/bin/env python3
"""第 149 天核心模块：breakdown.py——拆解编译与运行开销。

计划条目："分别测量各阶段时间，确认主要开销所在；
产出：时间分解图和初步瓶颈判断。"

把 D148 基线（160³ 朴素 kernel 20.9ms）的端到端拆成五段：
  T_compile   编译时间（管道七 pass＋translate＋llc＋clang）
  T_search    搜索时间（教学版无搜索——记 0 并说明）
  T_launch    launch/调用开销（ctypes 调用＋描述符构造）
  T_alloc     内存分配（kernel 内 malloc）
  T_exec      kernel 执行（20.9ms 的主体）
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
LLVM = "/opt/homebrew/opt/llvm/bin"
M, K, N = 160, 160, 160


def time_compile() -> float:
    """T_compile：全管道编译（七 pass＋translate＋llc＋clang）。"""
    from baseline import build_naive
    t0 = time.perf_counter()
    lib, _ = build_naive(M, K, N)
    dt = (time.perf_counter() - t0) * 1000
    assert lib is not None
    return dt


def time_launch_and_exec() -> dict:
    """T_launch / T_alloc / T_exec 的分解测量。"""
    from baseline import build_naive, md2, md1, Desc2, Desc1
    lib, _ = build_naive(M, K, N)
    rng = np.random.default_rng(149)
    A = rng.standard_normal((M, K)).astype(np.float32)
    B = rng.standard_normal((K, N)).astype(np.float32)
    bias = rng.standard_normal(N).astype(np.float32)

    # 描述符构造（launch 准备的一部分）
    t0 = time.perf_counter()
    for _ in range(100):
        da, db, dbias = md2(A), md2(B), md1(bias)
    t_desc = (time.perf_counter() - t0) / 100 * 1000  # µs 级

    # 纯 ctypes 调用开销（用空 kernel 对照——教学近似：
    # 用最小 shape 的同结构 kernel 测"调用+分配"部分）
    lib_small, _ = build_naive(2, 2, 2)
    As, Bs, bs = (np.ones((2, 2), np.float32), np.ones((2, 2), np.float32),
                  np.ones(2, np.float32))
    das, dbs, dbs_ = md2(As), md2(Bs), md1(bs)
    # 预热
    for _ in range(3):
        dc = Desc2()
        lib_small._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(das),
                                           ctypes.byref(dbs), ctypes.byref(dbs_))
    t0 = time.perf_counter()
    n = 200
    for _ in range(n):
        dc = Desc2()
        lib_small._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(das),
                                           ctypes.byref(dbs), ctypes.byref(dbs_))
    t_overhead = (time.perf_counter() - t0) / n * 1000
    # 小 kernel 的执行近似 0 → t_overhead ≈ launch+alloc+调用

    # 大 kernel 的总时间（D148 口径）
    da, db, dbias = md2(A), md2(B), md1(bias)
    for _ in range(2):
        dc = Desc2()
        lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                     ctypes.byref(db), ctypes.byref(dbias))
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(3):
            dc = Desc2()
            lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                         ctypes.byref(db), ctypes.byref(dbias))
        times.append((time.perf_counter() - t0) / 3 * 1000)
    times.sort()
    t_total = times[len(times)//2]
    t_exec = t_total - t_overhead   # 扣除调用开销的净执行

    return {
        "t_desc_us": t_desc * 1000,
        "t_overhead_ms": t_overhead,
        "t_total_ms": t_total,
        "t_exec_ms": t_exec,
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    print("== T_compile 编译时间 ==")
    t_compile = time_compile()
    print(f"  全管道（七 pass＋translate＋llc＋clang）：{t_compile:.0f} ms")

    print("\n== T_search 搜索时间 ==")
    print("  教学版无自动搜索（tile 是手选参数）——记 0")
    print("  （真实系统：AutoTVM 搜索可能占小时级——minic 的对照）")

    print("\n== T_launch / T_alloc / T_exec ==")
    r = time_launch_and_exec()
    print(f"  描述符构造：{r['t_desc_us']:.1f} µs（可忽略）")
    print(f"  调用+分配开销（小 kernel 对照）：{r['t_overhead_ms']:.3f} ms")
    print(f"  总时间（160³ 中位）：{r['t_total_ms']:.2f} ms")
    print(f"  净执行（总-开销）：{r['t_exec_ms']:.2f} ms")

    # 分解图（文本版）
    total_e2e = t_compile + r["t_total_ms"]
    segs = [
        ("编译（一次性）", t_compile),
        ("搜索（教学 0）", 0),
        ("描述符构造", r["t_desc_us"] / 1000),
        ("调用+分配", r["t_overhead_ms"]),
        ("kernel 执行", r["t_exec_ms"]),
    ]
    print("\n== 时间分解图（首次调用的端到端）==")
    for name, ms in segs:
        pct = ms / total_e2e * 100
        bar = "█" * max(1, int(pct / 2))
        print(f"  {name:16s} {ms:8.2f} ms  {pct:5.1f}%  {bar}")

    print("\n== 稳态视角（编译摊销后——每次调用）==")
    steady = r["t_total_ms"]
    for name, ms in [("描述符", r["t_desc_us"]/1000), ("调用+分配", r["t_overhead_ms"]),
                     ("执行", r["t_exec_ms"])]:
        pct = ms / steady * 100
        print(f"  {name:10s} {ms:7.3f} ms  {pct:5.1f}%")

    # 初步瓶颈判断
    exec_pct = r["t_exec_ms"] / r["t_total_ms"] * 100
    print(f"\n== 初步瓶颈判断 ==")
    print(f"  稳态下执行占 {exec_pct:.0f}%——瓶颈在 kernel 执行本身（不是调用/分配）")
    print(f"  → D150 的 Roofline 分析对象：这 {r['t_exec_ms']:.1f}ms 里是计算受限还是访存受限")

    json.dump({"t_compile_ms": round(t_compile, 1),
               "t_exec_ms": round(r["t_exec_ms"], 2),
               "t_overhead_ms": round(r["t_overhead_ms"], 3),
               "exec_pct": round(exec_pct, 1)},
              open(os.path.join(OUT, "breakdown.json"), "w"), indent=2)
    ok = exec_pct > 90
    print(f"\n判定：{'PASS——瓶颈定位在执行段' if ok else '开销占比异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
