#!/usr/bin/env python3
"""test_fusion_traffic.py —— 第 72 天独立验收测试。

不信任主实验的打印，用随机 shape 的性质测试独立复验：
  A. 公式与仪器化执行器在随机 (M,K,N) 上逐计划一致
  B. 收益公式：ΔB = 被消除的中间 × 2 趟 × itemsize
  C. 省比公式 4MN/(MK+KN+6MN) 及其上界 2/3
  D. 多使用者：keep 策略的收益 = 组内趟数规则
  E. bias 广播不改变 ΔB，只改分母
  F. dtype 缩放：ΔB ∝ itemsize，省比不变
  G. 扫描单调性：K↑ 省比↓，n↑ 省比↑

运行：python3 test_fusion_traffic.py
"""

from __future__ import annotations

import numpy as np

from fusion_traffic_lab import (
    Dram,
    fusion_savings_passes,
    intermediates_bytes,
    plan_bytes,
    run_multi_keep,
    run_multi_refuse,
    run_plan,
)

PASSED = 0
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASSED, CHECKS
    CHECKS += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' ' + detail) if detail else ''}")
    if cond:
        PASSED += 1
    return cond


def rand_chain(rng, M=None, K=None, N=None):
    M = M or int(rng.integers(1, 33))
    K = K or int(rng.integers(1, 33))
    N = N or int(rng.integers(1, 33))
    A = rng.standard_normal((M, K)).astype(np.float32)
    B = rng.standard_normal((K, N)).astype(np.float32)
    D = rng.standard_normal((M, N)).astype(np.float32)
    return M, K, N, A, B, D


def main() -> None:
    rng = np.random.default_rng(72)
    shapes = [rand_chain(rng) for _ in range(25)]

    # ---- A. 公式 vs 仪器化（随机 shape × 4 计划）----
    print("== A. 公式 vs 仪器化执行（25 组随机 (M,K,N) × 4 计划）==")
    ok_all, ok_val, ok_delta = True, True, True
    for M, K, N, A, B, D in shapes:
        formulas = plan_bytes(M, K, N)
        Fs = []
        for plan in ("P0", "P1", "P2", "P3"):
            dram = Dram()
            F = run_plan(plan, A, B, D, dram)
            fr, fw = formulas[plan]
            if not (dram.reads == fr and dram.writes == fw):
                ok_all = False
            Fs.append(F)
        if not all(np.array_equal(Fs[0], f) for f in Fs[1:]):
            ok_val = False
        t0 = sum(formulas["P0"])
        t3 = sum(formulas["P3"])
        if t0 - t3 != intermediates_bytes(M, N):
            ok_delta = False
    check("A1 25 组随机 shape：四种计划的读写记账 == 公式", ok_all)
    check("A2 融合不改变数值：四种计划 F 逐位相等", ok_val)
    check("A3 全融合 ΔB == 16·MN（2 中间 × 2 趟 × itemsize）", ok_delta)

    # ---- B. 收益公式的结构 ----
    print("== B. 收益公式：逐项拆解 ==")
    ok_part, ok_sum = True, True
    for M, K, N, *_ in shapes:
        f = plan_bytes(M, K, N)
        t0, t1, t2, t3 = (sum(f[p]) for p in ("P0", "P1", "P2", "P3"))
        if t0 - t1 != 2 * (M * N) * 4 or t0 - t2 != 2 * (M * N) * 4:
            ok_part = False          # 消掉一个 MN 中间 = 8·MN 字节
        if t1 != t2:
            ok_part = False          # 本链两个中间同尺寸：P1 与 P2 字节相同
        if t3 != (M * K + K * N + 2 * M * N) * 4:
            ok_sum = False           # 融合后只剩任务流量
    check("B1 两算子融合 ΔB == 8·MN（1 中间 × 2 趟）且 P1 == P2", ok_part)
    check("B2 全融合总流量 == (MK + KN + 2MN) × itemsize（纯任务流量）", ok_sum)

    # ---- C. 省比公式与上界 ----
    print("== C. 省比 = 4MN/(MK+KN+6MN)，恒 < 2/3 ==")
    ok_frac, ok_bound = True, True
    for M, K, N, *_ in shapes:
        f = plan_bytes(M, K, N)
        got = (sum(f["P0"]) - sum(f["P3"])) / sum(f["P0"])
        want = 4 * M * N / (M * K + K * N + 6 * M * N)
        if abs(got - want) > 1e-12:
            ok_frac = False
        if not 0 < got < 2 / 3:
            ok_bound = False
    check("C1 省比 == 4MN/(MK+KN+6MN)（25 组随机 shape）", ok_frac)
    check("C2 0 < 省比 < 2/3（上界：MN 再大也压不过任务流量）", ok_bound)

    # ---- D. 多使用者 ----
    print("== D. 多使用者：keep 策略的收益规则 ==")
    ok_planner, ok_instr, ok_refuse = True, True, True
    for M, K, N, A, B, D in shapes[:12]:
        da, db = Dram(), Dram()
        run_multi_refuse(A, B, D, da)
        run_multi_keep(A, B, D, db)
        planner = fusion_savings_passes(
            [("C", M * N, 1, 0), ("E", M * N, 1, 1)], itemsize=4)
        if da.total - db.total != planner:
            ok_planner = False
        # 仪器化拆解：C 省 2 趟 + E 省 1 趟 = 12·MN 字节
        if da.total - db.total != 3 * (M * N) * 4:
            ok_instr = False
        if da.total != sum(plan_bytes(M, K, N)["P0"]) + 2 * (M * N) * 4:
            ok_refuse = False       # 拒绝策略 = P0 + G 读 E + G 写 G_out
    check("D1 收益公式（多使用者版）== 仪器化 keep vs refuse（12 组）", ok_planner)
    check("D2 keep 策略 ΔB == 3 趟 × MN × itemsize（C 2 趟 + E 1 趟）", ok_instr)
    check("D3 拒绝策略总流量 == P0 + G 的固定账（ΔB = 0）", ok_refuse)

    # ---- E. bias 广播 ----
    print("== E. bias (M,N) → (N,)：ΔB 不变，分母变小 ==")
    ok_inv, ok_shrink = True, True
    for M, K, N, *_ in shapes:
        full0 = sum(plan_bytes(M, K, N)["P0"])
        full3 = sum(plan_bytes(M, K, N)["P3"])
        bc0 = sum(plan_bytes(M, K, N, bias="bc")["P0"])
        bc3 = sum(plan_bytes(M, K, N, bias="bc")["P3"])
        if full0 - full3 != bc0 - bc3:
            ok_inv = False
        if not bc0 <= full0:
            ok_shrink = False
        if M > 1 and not bc0 < full0:
            ok_shrink = False          # M=1 时 (N,) 与 (1,N) 元素数相同
    check("E1 广播不改变 ΔB（省几趟只看中间 Tensor，不看 bias 怎么读）", ok_inv)
    check("E2 广播让不融合总流量不增（M>1 时严格变小：少读 MN−N 个元素）",
          ok_shrink)

    # ---- F. dtype 缩放 ----
    print("== F. dtype：ΔB ∝ itemsize，省比不变 ==")
    ok_dt = True
    for M, K, N, *_ in shapes[:12]:
        f32 = plan_bytes(M, K, N)
        f16 = plan_bytes(M, K, N, itemsize=2)
        d32 = sum(f32["P0"]) - sum(f32["P3"])
        d16 = sum(f16["P0"]) - sum(f16["P3"])
        if d32 != 2 * d16:
            ok_dt = False
        if abs(d32 / sum(f32["P0"]) - d16 / sum(f16["P0"])) > 1e-12:
            ok_dt = False
    check("F1 fp16 的 ΔB == fp32 的一半，且省比完全相同（元素比口径）", ok_dt)

    # ---- G. 扫描单调性 ----
    print("== G. Shape 扫描的单调性与天花板 ==")
    ks = [1, 4, 16, 64, 256, 1024, 4096]
    fr = []
    for K in ks:
        f = plan_bytes(256, K, 256)
        fr.append((sum(f["P0"]) - sum(f["P3"])) / sum(f["P0"]))
    check("G1 M=N=256 时省比随 K 严格下降（输入变大稀释中间占比）",
          all(a > b for a, b in zip(fr, fr[1:])))
    ns = [16, 64, 256, 1024, 4096]
    fn = []
    for n in ns:
        f = plan_bytes(n, 64, n)
        fn.append((sum(f["P0"]) - sum(f["P3"])) / sum(f["P0"]))
    check("G2 K=64 时省比随 n 严格上升，且最后一点 > 66%",
          all(a < b for a, b in zip(fn, fn[1:])) and fn[-1] > 0.66)
    check("G3 天花板：正方形省比 = 2n/(K+3n)，n→∞ 时 → 2/3 ≈ 66.7%",
          abs(fn[-1] - 2 * 4096 / (64 + 3 * 4096)) < 1e-12
          and 2 / 3 - fn[-1] < 0.0035)

    print(f"\n== 结果：{PASSED}/{CHECKS} 项验收通过 ==")
    return None


if __name__ == "__main__":
    main()
