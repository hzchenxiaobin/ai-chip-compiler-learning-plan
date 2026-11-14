#!/usr/bin/env python3
"""第 150 天核心模块：roofline.py——分析计算与访存瓶颈。

计划条目："计算当前用例的理论计算量、访存量和算术强度，与实测
性能对照；产出：瓶颈分析和需要验证的假设。"

Roofline 模型（教学版）：
  算术强度 AI = FLOP / Byte（每字节搬运做了多少计算）
  机器屋顶：峰值算力（FLOP/s）与峰值带宽（Byte/s）
  屋顶线：性能 = min(峰值算力, AI × 峰值带宽)
  拐点：AI* = 峰值算力 / 峰值带宽——AI < AI* 访存受限、AI > AI* 计算受限
"""
from __future__ import annotations

import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
M = N = K = 160

# Apple M 系（教学估算值——诚实声明：规格值非实测）
PEAK_FLOPS = 50e9        # 50 GFLOP/s（单核 f32 朴素序的教学下界）
PEAK_BW = 50e9           # 50 GB/s（L2/内存混合的教学估算）


def analyze_naive():
    """朴素三重循环的访存分析。"""
    flop = 2 * M * N * K                      # 乘加各一
    # 朴素版：每个 C[i][j] 独立算——A 行读 N 次、B 列读 M 次
    # 最坏情形（无 cache）：A 全量 × N 次 + B 全量 × M 次 + C 读写一次
    bytes_worst = (M * K * 4 * N + K * N * 4 * M + M * N * 4 * 2)
    # 有 cache 的情形（教学估算：A 行在 L1 命中、B 列流过）
    # 每个 (i,j) 对：A 行 160×4B 已在 L1（i 固定）＋ B 列流 160×4B
    bytes_cached = M * N * (K * 4 + K * 4) + M * K * 4 + K * N * 4 + M * N * 8
    return flop, bytes_worst, bytes_cached


def main():
    os.makedirs(OUT, exist_ok=True)
    print("== 理论量计算（160³ matmul＋bias＋relu）==")
    flop, bw_worst, bw_cached = analyze_naive()
    print(f"  计算量：2×{M}×{N}×{K} = {flop/1e6:.1f} MFLOP")
    print(f"  访存量（无 cache 最坏）：{bw_worst/1e6:.1f} MB")
    print(f"  访存量（L1 命中估算）：{bw_cached/1e6:.1f} MB")

    print("\n== 算术强度 ==")
    ai_worst = flop / bw_worst
    ai_cached = flop / bw_cached
    print(f"  AI（最坏）= {ai_worst:.2f} FLOP/Byte")
    print(f"  AI（cache）= {ai_cached:.2f} FLOP/Byte")

    print("\n== 机器屋顶（教学估算·M 系）==")
    print(f"  峰值算力：{PEAK_FLOPS/1e9:.0f} GFLOP/s")
    print(f"  峰值带宽：{PEAK_BW/1e9:.0f} GB/s")
    knee = PEAK_FLOPS / PEAK_BW
    print(f"  拐点 AI* = {PEAK_FLOPS/1e9:.0f}/{PEAK_BW/1e9:.0f} = {knee:.1f} FLOP/Byte")

    print("\n== 实测对照 ==")
    measured_gflops = 0.392                     # D148 基线
    roof_compute = PEAK_FLOPS / 1e9             # 计算屋顶
    roof_mem_worst = ai_worst * PEAK_BW / 1e9   # 访存屋顶（最坏）
    roof_mem_cached = ai_cached * PEAK_BW / 1e9
    print(f"  实测：{measured_gflops:.3f} GFLOP/s")
    print(f"  计算屋顶：{roof_compute:.0f} GFLOP/s（差距 {roof_compute/measured_gflops:.0f}×）")
    print(f"  访存屋顶（最坏 AI）：{roof_mem_worst:.1f} GFLOP/s（差距 {roof_mem_worst/measured_gflops:.0f}×）")
    print(f"  访存屋顶（cache AI）：{roof_mem_cached:.1f} GFLOP/s（差距 {roof_mem_cached/measured_gflops:.0f}×）")

    print("\n== 瓶颈判定 ==")
    # 实测离两个屋顶的距离
    d_compute = roof_compute / measured_gflops
    d_mem = roof_mem_worst / measured_gflops
    print(f"  实测离计算屋顶 {d_compute:.0f}×、离访存屋顶（最坏）{d_mem:.0f}×")
    print(f"  → 两个屋顶都远（{d_compute:.0f}× 与 {d_mem:.0f}×）——")
    print(f"    这说明瓶颈不是「计算 vs 访存」的二选一，而是「执行效率」：")
    print(f"    朴素三重循环的指令开销（循环控制/地址计算/依赖链）吞掉了性能——")
    print(f"    每个乘加只用了 ~0.4 GFLOP/s 的「有效算力」")
    print(f"  → 假设 H1：循环控制开销主导（展开可救——D125 的 O2 证据：3.4GF＝8×）")
    print(f"  → 假设 H2：数据复用不足（L1 miss 频繁——tile 化可救——D151 的实验）")
    print(f"  → 假设 H3：依赖链限制 ILP（acc 串行——重排可救——教学版不做）")

    # 文本 roofline 图
    print("\n== Roofline 图（文本版·对数轴）==")
    print("  GFLOP/s")
    for gf in [64, 32, 16, 8, 4, 2, 1, 0.5, 0.25]:
        ai_pos = gf / (PEAK_BW / 1e9) if gf < PEAK_FLOPS / 1e9 else None
        bar = "·" * int(gf)
        marker = ""
        if abs(gf - measured_gflops) < 0.05:
            marker = " ← 实测"
        print(f"  {gf:6.2f} {bar}{marker}")
    print(f"        0.5   1    2    4    8   16   32   64  FLOP/Byte（AI）")

    result = {
        "flop_m": round(flop / 1e6, 1), "ai_worst": round(ai_worst, 2),
        "ai_cached": round(ai_cached, 2), "knee": round(knee, 1),
        "measured_gflops": measured_gflops,
        "dist_to_compute": round(d_compute), "dist_to_mem_worst": round(d_mem),
        "verdict": "执行效率瓶颈（循环开销/复用/ILP）——非纯计算或纯访存",
        "hypotheses": ["H1 循环控制开销（展开可救）", "H2 数据复用不足（tile 可救）",
                       "H3 依赖链限制 ILP（重排可救·不做）"],
    }
    json.dump(result, open(os.path.join(OUT, "roofline.json"), "w"),
              ensure_ascii=False, indent=2)
    ok = d_compute > 10 and d_mem > 2
    print(f"\n判定：{'PASS——瓶颈定性完成（三假设待 D151 验证）' if ok else '重析'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
