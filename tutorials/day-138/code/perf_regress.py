#!/usr/bin/env python3
"""第 138 天核心模块：perf_regress.py——性能回归测试。

计划条目："固定一组基准 Shape，保存中位数和波动范围，建立合理回归报警；
产出：性能基准文件和自动比较脚本。"

三个实验：
  P1 基准采集    固定 4 个基准 shape×多轮计时→中位数+P90+波动范围→baseline.json
  P2 回归比较    新测量 vs baseline→偏差判定（超过阈值报警）
  P3 报警演练    注入"退化版"（模拟性能回归）→报警应触发；正常版→不触发
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
LLVM = "/opt/homebrew/opt/llvm/bin"

BENCH_SHAPES = [(4, 6, 3), (8, 8, 8), (16, 16, 16), (32, 32, 32)]
ROUNDS = 7            # 每轮内部 20000 次调用取均值（D125 口径）
THRESHOLD = 1.5       # 报警阈值：中位数超基线 1.5× 才报（防噪声误报）


def time_kernel_us(M: int, K: int, N: int, fake_slowdown: float = 1.0) -> float:
    """计时一个 shape 的 kernel（教学仿真：基础 µs × slowdown）。

    真实版应调 D125 的 kernel_timing；教学版用确定性仿真保证
    实验的可重复讲解（性能回归的判定逻辑才是今天的主角）。
    """
    base_us = 0.02 * (M * K * N) / 72.0      # 粗略按 MAC 数缩放
    import random
    rng = random.Random(f"{M}-{K}-{N}")
    return base_us * fake_slowdown * rng.uniform(0.92, 1.08)   # ±8% 波动


def collect_baseline() -> dict:
    """P1：基准采集——每 shape 多轮取中位数＋P90＋范围。"""
    baseline = {}
    for (M, K, N) in BENCH_SHAPES:
        samples = [time_kernel_us(M, K, N) for _ in range(ROUNDS)]
        samples.sort()
        med = statistics.median(samples)
        p90 = samples[int(len(samples) * 0.9) - 1]
        baseline[f"{M}x{K}x{N}"] = {
            "median_us": round(med, 4),
            "p90_us": round(p90, 4),
            "min_us": round(samples[0], 4),
            "max_us": round(samples[-1], 4),
            "spread_pct": round((samples[-1] - samples[0]) / med * 100, 1),
        }
    return baseline


def compare(new_run: dict, baseline: dict, threshold: float = THRESHOLD) -> dict:
    """P2：回归比较——每 shape 的中位数偏差＋判定。"""
    report = {"regressions": [], "improvements": [], "stable": []}
    for shape, base in baseline.items():
        new_med = new_run[shape]["median_us"]
        ratio = new_med / base["median_us"]
        entry = {"shape": shape, "baseline_us": base["median_us"],
                 "new_us": round(new_med, 4), "ratio": round(ratio, 3)}
        if ratio > threshold:
            report["regressions"].append({**entry, "verdict": "REGRESSION"})
        elif ratio < 1 / threshold:
            report["improvements"].append({**entry, "verdict": "IMPROVEMENT"})
        else:
            report["stable"].append({**entry, "verdict": "STABLE"})
    return report


def main():
    os.makedirs(OUT, exist_ok=True)

    print("== P1 基准采集：4 shape × 7 轮 ==")
    baseline = collect_baseline()
    json.dump(baseline, open(os.path.join(OUT, "baseline.json"), "w"), indent=2)
    for shape, m in baseline.items():
        print(f"  {shape}: 中位 {m['median_us']:.4f}µs｜P90 {m['p90_us']:.4f}｜"
              f"波动 ±{m['spread_pct']/2:.0f}%")
    print(f"  基准落盘 baseline.json（阈值 {THRESHOLD}×——超 1.5× 才报）\n")

    print("== P2 正常回归比较（无退化——应全 STABLE）==")
    normal_run = collect_baseline()          # 同分布再采一组
    r1 = compare(normal_run, baseline)
    n_stable = len(r1["stable"])
    print(f"  {n_stable}/{len(BENCH_SHAPES)} STABLE｜"
          f"{len(r1['regressions'])} REGRESSION｜{len(r1['improvements'])} IMPROVEMENT")
    print(f"  → 波动 ±8% 在阈值 1.5× 之内——不误报\n")

    print("== P3 报警演练（注入 2× 退化——应触发）==")
    degraded = {}
    for (M, K, N) in BENCH_SHAPES:
        samples = [time_kernel_us(M, K, N, fake_slowdown=2.0) for _ in range(ROUNDS)]
        degraded[f"{M}x{K}x{N}"] = {"median_us": statistics.median(samples)}
    r2 = compare(degraded, baseline)
    print(f"  {len(r2['regressions'])}/{len(BENCH_SHAPES)} REGRESSION 触发：")
    for reg in r2["regressions"]:
        print(f"    {reg['shape']}: {reg['baseline_us']}→{reg['new_us']}µs"
              f"（{reg['ratio']}×）——报警！")
    ok = n_stable == len(BENCH_SHAPES) and len(r2["regressions"]) == len(BENCH_SHAPES)
    print(f"\n结论：{'PASS' if ok else 'FAIL'}——正常波动不误报、真实退化必报警")
    print("口径：中位数（非均值——抗离群）；阈值 1.5×（波动 8%×2 倍安全边际）")
    print("     阈值太紧→误报疲劳（狼来了）；太松→漏报真退化——1.5× 是教学权衡")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
