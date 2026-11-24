#!/usr/bin/env python3
"""test_negative_cases.py —— 第 75 天独立验收测试。

不复用主实验的运行结果：每个用例重新构造候选、重新算账，再对照
「预期判决 + 预期数字」。分六组：

  A 结构负例回归（8 例 + D74 对照 + 不误伤）
  B R1 多使用者（ΔB 塌缩 / 翻转 / 不变量）
  C R2 资源超限（数字 / tile 救活 / 理由归属）
  D R3 重复计算（两本账 / 恒等式 / 守卫）
  E R4 并行度（舒适区 / ΔB-tile 无关 / 基线对照）
  F 案例库与判决一致性（16 例的 expect 全对上）

运行：python3 test_negative_cases.py
"""

from __future__ import annotations

from negative_case_lab import (
    Machine, Op, Intermediate, FusionCandidate,
    can_fuse, d74_can_fuse, should_fuse, price_recompute,
    decide, comfort_ok, run_case, wing_a_cases, wing_b_cases,
    cand_full, cand_mm_mm, cand_skinny, chain_ops,
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


def main() -> None:
    m = Machine()

    # ================= A 结构负例 =================
    print("== A. 结构负例回归 ==")
    wing_a = {e.name: e for e in wing_a_cases()}
    legs = {n: can_fuse(e.build()) for n, e in wing_a.items()}
    check("A1 八个结构负例全部被拦（与主实验独立重算）",
          all(not r.ok for r in legs.values()))
    rule = {"A1 模式不支持": "L1", "A2 副作用算子": "L2", "A3 逐元素 Shape 不齐": "L3",
            "A4 int8 全链": "L5", "A5 偷走中间": "L4", "A6 无使用者": "L4",
            "A7 组内循环依赖": "L6", "A8 边形状不匹配": "L3b"}
    check("A2 每个负例的理由定位到预期规则号",
          all(legs[n].reasons[0].startswith(r) for n, r in rule.items()))
    check("A3 两个新负例在 D74 规则集下会漏过（新规则各自补上一个洞）",
          d74_can_fuse(wing_a["A7 组内循环依赖"].build()).ok
          and d74_can_fuse(wing_a["A8 边形状不匹配"].build()).ok)
    positives = [cand_full(2, 3, 2),
                cand_full(2048, 64, 2048, tile=(128, 128)),
                cand_mm_mm(2048, 64, 1024, 2048, (128, 128)),
                cand_skinny(64, 4096, 64),
                FusionCandidate("动态维度",  # D74 §7 的动态候选也不能被新规则误伤
                                (Op("matmul", ((-1, 3), (3, 2)), (-1, 2)),
                                 Op("add", ((-1, 2), (-1, 2)), (-1, 2)),
                                 Op("relu", ((-1, 2),), (-1, 2))),
                                intermediates=(Intermediate("C", -1, 1, 0),
                                               Intermediate("E", -1, 1, 0)),
                                workload=(-1, 3, 2))]
    check("A4 新规则不误伤：贯穿链/放大版/MM→MM/skinny/动态维度仍合法",
          all(can_fuse(c).ok for c in positives))
    # L3b 的 -1 通配：动态维度的边也放行
    dyn_edge = FusionCandidate("动态边", (Op("matmul", ((2, 3), (3, 4)), (2, -1)),
                                           Op("add", ((-1, 4), (-1, 4)), (2, 4))))
    check("A5 L3b 沿用 D61 口径：-1 未知维度在边上按通配处理",
          can_fuse(dyn_edge).reasons == [] or
          not any(r.startswith("L3b") for r in can_fuse(dyn_edge).reasons))

    # ================= B R1 多使用者 =================
    print("== B. R1 多使用者 ==")
    r1 = cand_mm_mm(2048, 64, 1024, 2048, (128, 128), out_users=1)
    r1c = cand_mm_mm(2048, 64, 1024, 2048, (128, 128), out_users=0)
    p1, p1c = should_fuse(r1, m), should_fuse(r1c, m)
    check("B1 两张图都合法（keep：组外使用者有人喂）",
          can_fuse(r1).ok and can_fuse(r1c).ok)
    check("B2 ΔB 塌缩一半：16,777,216 → 8,388,608 B",
          p1c.delta_b == 16_777_216 and p1.delta_b == 8_388_608)
    check("B3 资源分文未动：spill 流量同为 10,485,760 B（负收益全来自 ΔB）",
          p1c.spill_traffic == p1.spill_traffic == 10_485_760)
    check("B4 净收益翻转：+6,291,456 → −2,097,152 B；cons/auto 一致拒绝",
          p1c.net_gain == 6_291_456 and p1.net_gain == -2_097_152
          and decide(can_fuse(r1), p1).action == "refuse"
          and decide(can_fuse(r1), p1, "auto").action == "refuse"
          and decide(can_fuse(r1c), p1c, "auto").action == "fuse")
    check("B5 不变量：net(对照) − net(R1) = |G|×4 = 8,388,608 B（写趟被钉回）",
          p1c.net_gain - p1.net_gain == p1c.delta_b - p1.delta_b == 8_388_608)
    check("B6 兑现率符号如实报告：R1 为 −25%（净收益/ΔB）",
          p1.redeem_rate is not None and abs(p1.redeem_rate + 0.25) < 1e-12)

    # ================= C R2 资源超限 =================
    print("== C. R2 资源超限 ==")
    r2 = cand_mm_mm(2048, 64, 64, 2048, (2048, 2048))
    r2c = cand_mm_mm(2048, 64, 64, 2048, (64, 64))
    p2, p2c = should_fuse(r2, m), should_fuse(r2c, m)
    check("C1 图合法；不分块活集 17,301,504 B，spill 17,039,360 B",
          can_fuse(r2).ok and p2.live_bytes == 17_301_504
          and p2.spill_bytes == 17_039_360)
    check("C2 净收益 −33,030,144 B（约 −31.5 MiB）：ΔB 1 MiB 被 spill 两趟税吞掉",
          p2.delta_b == 1_048_576 and p2.spill_traffic == 34_078_720
          and p2.net_gain == -33_030_144)
    check("C3 cons 与 auto 一致拒绝（下界口径也救不回来）",
          decide(can_fuse(r2), p2).action == "refuse"
          and decide(can_fuse(r2), p2, "auto").action == "refuse")
    check("C4 同图 tile=64 救活：活集 32,768 B、并发 4、净收益 +1,048,576 B",
          p2c.live_bytes == 32_768 and p2c.concurrent_tiles == 4
          and p2c.net_gain == 1_048_576
          and decide(can_fuse(r2c), p2c).action == "fuse")
    check("C5 拒绝理由归属收益层（前缀「保守策略」），合法性报告干净",
          decide(can_fuse(r2), p2).reasons[0].startswith("保守策略")
          and can_fuse(r2).reasons == [])

    # ================= D R3 重复计算 =================
    print("== D. R3 重复计算 ==")
    r3 = cand_skinny(64, 4096, 64, out_users=2)
    pk = should_fuse(r3, m)
    pr = price_recompute(r3, m)
    check("D1 keep 账本：ΔB = 1×|C|×4 = 16,384 B、零 spill → 门放行",
          pk.delta_b == 16_384 and pk.spill_bytes == 0
          and decide(can_fuse(r3), pk).action == "fuse")
    check("D2 重算消除 = (1写+1组内读+2组外读)×16,384 = 65,536 B",
          pr.recompute_elim == 65_536)
    check("D3 重读罚 = 2 个组外使用者 × (|A|+|B|)×4 = 2×524,288×4 = 4,194,304 B",
          pr.recompute_penalty == 4_194_304
          and (64 * 4096 + 4096 * 64) * 4 == 2_097_152)
    check("D4 重算净收益 = 65,536 − 4,194,304 = −4,128,768 B ≤ 0 → 拒绝",
          pr.net_gain == -4_128_768
          and decide(can_fuse(r3), pr).action == "refuse"
          and decide(can_fuse(r3), pr, "auto").action == "refuse")
    check("D5 恒等式：net = elim − 重读罚 − spill 流量（keep 形式同样成立）",
          pr.net_gain == pr.recompute_elim - pr.recompute_penalty - pr.spill_traffic
          and pk.net_gain == pk.delta_b - pk.spill_traffic)
    check("D6 守卫：无组外使用者时重算形式没有意义（如实记理由，不装糊涂）",
          price_recompute(cand_skinny(64, 4096, 64, out_users=0), m).reasons != []
          and "无组外使用者" in price_recompute(
              cand_skinny(64, 4096, 64, out_users=0), m).reasons[0])

    # ================= E R4 并行度 =================
    print("== E. R4 并行度 ==")
    r4 = cand_full(2048, 64, 2048, tile=(128, 128), name="R4 P3 tile128")
    r4c = cand_full(2048, 64, 2048, tile=(64, 64), name="R4ctl P3 tile64")
    p4, p4c = should_fuse(r4, m), should_fuse(r4c, m)
    base = FusionCandidate("基线 MatMul tile64",
                           (Op("matmul", ((2048, 64), (64, 2048)), (2048, 2048)),),
                           workload=(2048, 64, 2048), tile=(64, 64))
    pb = should_fuse(base, m)
    check("E1 D74 门放行 R4：零 spill、净收益 67,108,864 B → cons fuse",
          p4.spill_bytes == 0 and p4.net_gain == 67_108_864
          and decide(can_fuse(r4), p4).action == "fuse")
    check("E2 但占用 65,792 B > 寄存器堆 65,536 B → 并发 1；"
          "comfort_ok = False → 案例库拒绝",
          p4.reg_demand == 65_792 and p4.concurrent_tiles == 1
          and not comfort_ok(p4))
    check("E3 对照 tile=64：并发 3、comfort_ok = True、库放行",
          p4c.concurrent_tiles == 3 and comfort_ok(p4c))
    check("E4 ΔB 与 tile 无关：两行同为 67,108,864 B（消除的是中间不是分块）",
          p4.delta_b == p4c.delta_b == 67_108_864)
    check("E5 融合的并行度税：未融合 MatMul@tile64 并发 4，融合后 3（−25%，软代价）",
          pb.reg_demand == 16_384 and pb.concurrent_tiles == 4
          and p4c.reg_demand == 16_640 and p4c.concurrent_tiles == 3)
    check("E6 comfort_ok 的三个分量独立可查：零 spill / staging ok / 并发 ≥ 3"
          "（R2ctl 三项全过）",
          comfort_ok(should_fuse(
              cand_mm_mm(2048, 64, 64, 2048, (64, 64)), m)))

    # ================= F 案例库一致性 =================
    print("== F. 案例库与判决一致性 ==")
    outs = {}
    for e in wing_a_cases() + wing_b_cases():
        outs[e.name] = run_case(e, m)
    check("F1 16 例全部登记，翼 A 8 例翼 B 8 例",
          len(outs) == 16
          and sum(1 for o in outs.values() if o["entry"].wing == "A 结构负例") == 8)
    mismatch = [n for n, o in outs.items()
                if o["dec_cons"].action != o["entry"].expect_gate
                or o["lib_action"] != o["entry"].expect_lib]
    check("F2 每例的实际判决与案例库预期一致（gate 与库两列都对上）",
          not mismatch, detail=f"不一致：{mismatch}" if mismatch else "")
    legal_refused = [n for n, o in outs.items()
                     if o["leg"].ok and o["lib_action"] == "refuse"]
    check("F3 「图结构合法但应拒绝」≥ 2 例（计划底线），实际覆盖四类",
          {"R1 多使用者", "R2 资源超限", "R3 重算形式", "R4 并行度下降"}
          <= set(legal_refused)
          and len(legal_refused) >= 2)
    check("F4 四类负收益各有合法被拒案例，且对照案例各有放行",
          all(outs[n]["lib_action"] == "refuse" for n in
              ("R1 多使用者", "R2 资源超限", "R3 重算形式", "R4 并行度下降"))
          and all(outs[n]["lib_action"] == "fuse" for n in
                  ("R2 对照（tile 64）", "R3 keep 形式", "R4 对照（tile 64）")))
    check("F5 拒绝理由归属可机检：合法性/保守策略/重算账/并行度四个前缀都在",
          any(o["lib_reason"].startswith("合法性：L") for o in outs.values())
          and any(o["lib_reason"].startswith("保守策略") for o in outs.values())
          and any(o["lib_reason"].startswith("重算账") for o in outs.values())
          and any(o["lib_reason"].startswith("并行度") for o in outs.values()))
    check("F6 门与库的分歧只有 R4 一处（账本未计价的软代价），且如实记录",
          [n for n, o in outs.items()
           if o["dec_cons"].action != o["lib_action"]] == ["R4 并行度下降"]
          and outs["R4 并行度下降"]["dec_cons"].action == "fuse")

    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
