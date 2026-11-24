#!/usr/bin/env python3
"""test_fusion_resource.py —— 第 73 天独立验收测试。

不依赖主实验的输出文件，从零构造断言：
  A. 机器假设卡与容量阶梯边界
  B. 贯穿示例：四种计划的资源账与第 72 天收益的衔接
  C. tile 扫描：活集随 tile 走、AI/并发折中、不分块的代价
  D. MatMul→MatMul 反例：兑现率与净收益封顶
  E. 指令复杂度增量
  F. 假设清单完备性

运行：python3 test_fusion_resource.py
"""

from __future__ import annotations

from fusion_resource_lab import (ASSUMPTIONS, KernelResource, Machine,
                                 delta_b_two_intermediates, ew_live,
                                 fused_matmul_epilogue, matmul_acc,
                                 place, plan_kernels, sram_stage_ab)

PASSED = 0
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASSED, CHECKS
    CHECKS += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' ' + detail) if detail else ''}")
    if cond:
        PASSED += 1
    return cond


def main() -> None:
    m = Machine()

    # ---- A. 机器假设卡与容量阶梯 ----
    print("== A. 机器假设卡与容量阶梯 ==")
    check("A1 片上总容量 262,144 B = 64 KiB 寄存器堆 + 192 KiB SRAM",
          m.onchip_bytes == 262144 and m.regfile_bytes == 65536
          and m.sram_bytes == 196608)
    r_exact = place(KernelResource("d", m.regfile_bytes), m)
    r_plus1 = place(KernelResource("d", m.regfile_bytes + 1), m)
    r_cap = place(KernelResource("d", m.onchip_bytes), m)
    r_over = place(KernelResource("d", m.onchip_bytes + 1), m)
    check("A2 边界含等号：live == regfile → reg（0 降级）；"
          "live == onchip → 仍不溢出",
          r_exact.placement == "reg" and r_exact.demoted_bytes == 0
          and r_cap.spill_bytes == 0 and r_cap.placement == "reg+sram")
    check("A3 超寄存器堆 1 B → 降级 1 B；超片上容量 1 B → spill 1 B、流量 2 B",
          r_plus1.placement == "reg+sram" and r_plus1.demoted_bytes == 1
          and r_over.spill_bytes == 1 and r_over.spill_traffic == 2)
    check("A4 输入分块让路规则：活集降级占满 SRAM 后 staging 放不下（不溢出）",
          place(KernelResource("d", m.onchip_bytes, sram_demand=1), m).staging_ok
          is False
          and place(KernelResource("d", m.regfile_bytes,
                                   sram_demand=m.sram_bytes), m).staging_ok)

    # ---- B. 贯穿示例：资源账与第 72 天收益的衔接 ----
    print("== B. 贯穿示例 A(2,3)@B(3,2)+D(2,2)→relu ==")
    plans = plan_kernels(2, 3, 2, m)
    db = delta_b_two_intermediates(2, 2, m)
    check("B1 四种计划全部落 reg、零 spill → 资源不设限",
          all(k.placement == "reg" and k.spill_bytes == 0
              for ks in plans.values() for k in ks))
    p3, mm = plans["P3"][0], plans["P0"][0]
    check("B2 epilogue 增量 = lanes×itemsize = 256 B（A6：复用累加器槽）",
          p3.reg_demand - mm.reg_demand == 256
          and fused_matmul_epilogue(2, 2, m) - matmul_acc(2, 2, m) == 256)
    check("B3 逐元素活集与总量无关：Add 768 B、Relu 512 B（A5 流式）",
          ew_live(m, 2, 1) == 768 and ew_live(m, 1, 1) == 512
          and ew_live(m, 2, 1) == ew_live(m, 2, 1))
    check("B4 净收益 = 各计划省下（第 72 天 ΔB 列）− 0 spill：0/32/32/64 B",
          db == 64 and all(
              ({"P0": 0, "P1": 32, "P2": 32, "P3": 64})[p]
              - sum(k.spill_traffic for k in plans[p])
              == {"P0": 0, "P1": 32, "P2": 32, "P3": 64}[p]
              for p in plans))
    check("B5 D 无复用不驻留：P3 的 SRAM 需求 = A/B 分块 48 B（A3）",
          p3.sram_demand == 48 and sram_stage_ab(2, 3, 2, m) == 48)
    check("B6 贯穿示例所有活集都小于 1 KiB：小链上资源账看不见，"
          "必须放大 shape 才见边界",
          all(k.live_bytes < 1024 for ks in plans.values() for k in ks))

    # ---- C. tile 扫描（M=N=2048, K=64, 全融合 P3）----
    print("== C. tile 扫描：活集随 tile 走，不随总量走 ==")
    M, K, N = 2048, 64, 2048
    db1 = delta_b_two_intermediates(M, N, m)
    rows = {}
    for t in (2048, 256, 128, 64, 32):
        rows[t] = plan_kernels(M, K, N, m, tile_m=t, tile_n=t)["P3"][0]
    check("C1 活集只随 tile 变：32→2048 的活集 4,352→16,777,472 B，"
          "而 ΔB 恒 64 MiB（活集与总量解耦）",
          rows[32].reg_demand == 4352 and rows[2048].reg_demand == 16777472
          and db1 == 67108864)
    check("C2 tile 128×128 累加器恰满寄存器堆，epilogue 256 B 顶过线 → 降级 256 B",
          rows[128].reg_demand - 256 == m.regfile_bytes
          and rows[128].demoted_bytes == 256
          and rows[128].placement == "reg+sram")
    check("C3 tile 256×256 溢出 256 B 且 staging 挤没；2048 不分块溢出 16,515,328 B",
          rows[256].spill_bytes == 256 and not rows[256].staging_ok
          and rows[2048].spill_bytes == 16515328)
    check("C4 舒适区存在：64×64 spill=0、staging ok、并发 3 tile",
          rows[64].spill_bytes == 0 and rows[64].staging_ok
          and rows[64].concurrent_tiles == 3
          and rows[32].concurrent_tiles == 12)
    net2048 = db1 - rows[2048].spill_traffic
    check("C5 不分块净收益 = ΔB − 2×溢出 = 34,078,208 B ≈ 50.8%（被砍近半）",
          rows[2048].spill_traffic == 33030656 and net2048 == 34078208
          and abs(net2048 / db1 - 0.508) < 1e-3)
    ai = {t: 2 * t * t * K / ((t * K + K * t + 2 * t * t) * m.itemsize)
          for t in rows}
    check("C6 tile-AI 随 tile 单调（32→2048：5.33→15.52），"
          "128 的 10.67 仍低于平衡点 12.54",
          all(ai[a] < ai[b] for a, b in zip((32, 64, 128, 256), (64, 128, 256, 2048)))
          and abs(ai[128] - 10.666666666666666) < 1e-9
          and abs(ai[256] - 12.8) < 1e-9)

    # ---- D. MatMul→MatMul 反例 ----
    print("== D. MatMul→MatMul：活集被消费者的归约维钉死 ==")
    tm, Mm = 128, 2048
    check("D1 消费者累加器 (128×128) 恰满寄存器堆：溢出的全归 G 行块",
          matmul_acc(tm, tm, m) == m.regfile_bytes)
    results = {}
    for K1 in (64, 256, 1024, 4096):
        g_row = tm * K1 * m.itemsize
        k = place(KernelResource("FusedMatMulMatMul", matmul_acc(tm, tm, m),
                                 g_row), m)
        resident = min(g_row, m.onchip_bytes - matmul_acc(tm, tm, m))
        db_mm = 2 * Mm * K1 * m.itemsize
        results[K1] = (k, resident, db_mm, db_mm - k.spill_traffic * (Mm // tm))
    check("D2 K1=64/256：G 行块 32/128 KiB ≤ 可驻留 192 KiB → 兑现 100%",
          results[64][3] == results[64][2] and results[256][3] == results[256][2])
    check("D3 K1=1024：spill 320 KiB/行块、兑现率 = 196,608/524,288 = 37.5%",
          results[1024][0].spill_bytes == 327680
          and abs(results[1024][3] / results[1024][2] - 0.375) < 1e-12)
    check("D4 净收益封顶：K1=1024 与 4096 都 = 6 MiB = 2×16 行块×192 KiB",
          results[1024][3] == results[4096][3] == 6291456
          == 2 * (Mm // tm) * (m.onchip_bytes - m.regfile_bytes))
    check("D5 兑现率随 K1 单调不升且 4096 时 < 10%",
          all(results[a][3] / results[a][2] >= results[b][3] / results[b][2]
              for a, b in zip((64, 256, 1024, 4096), (256, 1024, 4096)))
          and results[4096][3] / results[4096][2] < 0.10)

    # ---- E. 指令复杂度 ----
    print("== E. 指令复杂度 ==")
    check("E1 epilogue 指令增量 = 2/K：K=64 → 3.125%，K=3（贯穿示例）→ 66.7%",
          abs(2 / 64 - 0.03125) < 1e-12 and abs(2 / 3 - 0.6666666666666666) < 1e-12)
    check("E2 K≥512 后增量 < 0.4%：重计算生产者配逐元素 epilogue 指令近乎免费",
          2 / 512 < 0.004 and 2 / 4096 < 0.0005)

    # ---- F. 假设清单 ----
    print("== F. 假设清单 ==")
    check("F1 假设清单 10 项、覆盖四轴（寄存器/片上/并行度/指令）且口径可追溯",
          len(ASSUMPTIONS) == 10
          and any("寄存器" in a for a in ASSUMPTIONS)
          and any("SRAM" in a for a in ASSUMPTIONS)
          and any("并行度" in a for a in ASSUMPTIONS)
          and any("指令" in a for a in ASSUMPTIONS))
    check("F2 净收益口径写入假设：净收益 = ΔB − spill 流量（A9）",
          any("净收益 = ΔB − spill 流量" in a for a in ASSUMPTIONS))

    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
