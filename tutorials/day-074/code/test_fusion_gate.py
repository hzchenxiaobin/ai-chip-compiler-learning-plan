#!/usr/bin/env python3
"""test_fusion_gate.py —— 第 74 天独立验收测试（不依赖主实验输出文件）。

从零构造断言，覆盖四块：
  A. 接口边界：can_fuse 不读机器；should_fuse 不重查结构；decide 只读报告
  B. 合法性 Pattern：正例 + 六类负例 + 动态维度的处理
  C. 收益性分析：D72 的 ΔB（含多使用者 48 B）与 D73 的资源账逐位一致
  D. 策略层：conservative / auto / force 的行为与拒绝理由的归属
  E. 假设清单完备性

运行：python3 test_fusion_gate.py
"""

from __future__ import annotations

import inspect

from fusion_gate_lab import (ASSUMPTIONS, FusionCandidate, Intermediate, Machine,
                             Op, can_fuse, chain_ops, decide, run_gate,
                             should_fuse)

PASSED = 0
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASSED, CHECKS
    CHECKS += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' ' + detail) if detail else ''}")
    if cond:
        PASSED += 1
    return cond


M0, K0, N0 = 2, 3, 2


def main() -> None:
    m = Machine()

    # ---- A. 接口边界 ----
    print("== A. 接口边界：三层各自的输入 ==")
    leg_params = set(inspect.signature(can_fuse).parameters)
    prof_params = set(inspect.signature(should_fuse).parameters)
    dec_params = set(inspect.signature(decide).parameters)
    check("A1 can_fuse 签名里没有机器参数（「能否」与机器无关）",
          not ({"m", "machine"} & leg_params))
    check("A2 should_fuse 签名里有 Machine（账本依赖假设卡）且不产出合法性结论",
          "m" in prof_params
          and not any(f.name == "legal" for f in
                      inspect.signature(should_fuse).parameters.values()))
    check("A3 decide 只吃两份报告：换策略不需要动前两层（D76 的接缝）",
          {"leg", "prof", "policy"} <= dec_params
          and not ({"c", "candidate"} & dec_params))

    # ---- B. 合法性 ----
    print("== B. 合法性 Pattern：正例、六类负例、动态维度 ==")
    from fusion_gate_lab import cand_full, cand_p1, cand_p2
    p1, p2, p3 = cand_p1(M0, K0, N0), cand_p2(M0, K0, N0), cand_full(M0, K0, N0)
    check("B1 贯穿链 P1/P2/P3 三种融合形式全部合法",
          all(can_fuse(c).ok for c in (p1, p2, p3)))
    check("B2 模式名正确：mini.fused_add_relu / mini.fused_matmul_bias / "
          "mini.fused_matmul_bias_relu",
          can_fuse(p1).pattern_name == "mini.fused_add_relu"
          and can_fuse(p2).pattern_name == "mini.fused_matmul_bias"
          and can_fuse(p3).pattern_name == "mini.fused_matmul_bias_relu")
    negs = {
        "模式": FusionCandidate("n", (Op("relu", ((2, 2),), (2, 2)),
                                    Op("matmul", ((2, 2), (2, 2)), (2, 2)))),
        "纯度": FusionCandidate("n", (Op("matmul", ((2, 3), (3, 2)), (2, 2)),
                                      Op("add", ((2, 2), (2, 2)), (2, 2),
                                         pure=False),
                                      Op("relu", ((2, 2),), (2, 2)))),
        "Shape": FusionCandidate("n", (Op("matmul", ((2, 3), (3, 2)), (2, 2)),
                                       Op("add", ((2, 3), (2, 2)), (2, 3)),
                                       Op("relu", ((2, 3),), (2, 3)))),
        "dtype": FusionCandidate("n", (Op("matmul", ((2, 3), (3, 2)), (2, 2),
                                          dtype="int8"),
                                       Op("add", ((2, 2), (2, 2)), (2, 2),
                                          dtype="int8"),
                                       Op("relu", ((2, 2),), (2, 2),
                                          dtype="int8"))),
        "内维": FusionCandidate("n", (Op("matmul", ((2, 3), (4, 2)), (2, 2)),
                                      Op("add", ((2, 2), (2, 2)), (2, 2)),
                                      Op("relu", ((2, 2),), (2, 2)))),
        "偷中间": FusionCandidate("n", chain_ops(M0, K0, N0),
                                  intermediates=(Intermediate("C", 4, 1, 0),
                                                 Intermediate("E", 4, 1, 1))),
        "无使用者": FusionCandidate("n", chain_ops(M0, K0, N0),
                                    intermediates=(Intermediate("C", 4, 0, 0),)),
    }
    leg_all = {k: can_fuse(v) for k, v in negs.items()}
    check("B3 七类负例全部拦截：模式/纯度/Shape/dtype/内维/偷中间/无使用者",
          all(not r.ok for r in leg_all.values()))
    check("B4 每个负例给出可定位的规则号（L1–L5）",
          all(any(rr.startswith(f"L{i}") for rr in rep.reasons)
              for rep, i in ((leg_all["模式"], 1), (leg_all["纯度"], 2),
                             (leg_all["Shape"], 3), (leg_all["dtype"], 5),
                             (leg_all["内维"], 3), (leg_all["偷中间"], 4),
                             (leg_all["无使用者"], 4))))
    dyn = FusionCandidate("dyn", (Op("matmul", ((-1, 3), (3, 2)), (-1, 2)),
                                  Op("add", ((-1, 2), (-1, 2)), (-1, 2)),
                                  Op("relu", ((-1, 2),), (-1, 2))),
                          intermediates=(Intermediate("C", -1, 1, 0),
                                         Intermediate("E", -1, 1, 0)),
                          workload=(-1, 3, 2))
    check("B5 动态维度不改变合法性（-1 通配，D61 口径），报告标记 dynamic",
          can_fuse(dyn).ok and can_fuse(dyn).dynamic)

    # ---- C. 收益性 ----
    print("== C. 收益性分析：ΔB 与资源账逐位对上 D72/D73 ==")
    pr = {c.name: should_fuse(c, m) for c in (p1, p2, p3)}
    check("C1 ΔB 对上 D72：P1=P2=32 B、P3=64 B（组内中间才省两趟）",
          pr["P1 FusedAddReLU"].delta_b == 32
          and pr["P2 FusedMatMulBias"].delta_b == 32
          and pr["P3 全融合"].delta_b == 64)
    check("C2 资源账对上 D73：P3 reg 272 B（累加器 16 + bias 在飞 256）、"
          "staging 48 B；P1 的在飞向量 768 B",
          pr["P3 全融合"].reg_demand == 272
          and pr["P3 全融合"].sram_demand == 48
          and pr["P1 FusedAddReLU"].reg_demand == 768)
    check("C3 净收益恒等式 net = ΔB − spill 流量，三个候选零 spill",
          all(p.net_gain == p.delta_b - p.spill_traffic == p.delta_b
              for p in pr.values()))
    keep_e = FusionCandidate("keep", chain_ops(M0, K0, N0),
                             intermediates=(Intermediate("C", 4, 1, 0),
                                            Intermediate("E", 4, 1, 1, kept=True)),
                             workload=(M0, K0, N0))
    check("C4 多使用者 keep：ΔB = 48 B = C 两趟 32 + E 一趟 16（D72 §5 口径）",
          should_fuse(keep_e, m).delta_b == 48
          and can_fuse(keep_e).kept_outputs == ["E"])
    M1, K1s, N1 = 2048, 64, 2048
    tiles = {t: should_fuse(cand_full(M1, K1s, N1, tile=(t, t)), m)
             for t in (32, 64, 128, 256, 2048)}
    check("C5 活集随 tile：4,352 / 16,640 / 65,792 / 262,400 / 16,777,472 B"
          "（D73 扫描表逐位一致），ΔB 恒 64 MiB",
          [tiles[t].reg_demand for t in (32, 64, 128, 256, 2048)]
          == [4352, 16640, 65792, 262400, 16777472]
          and tiles[32].delta_b == 67108864)
    check("C6 tile 128 降级 256 B 零 spill（reg+sram）；tile 256 溢 256 B；"
          "2048 溢 16,515,328 B、流量 33,030,656 B",
          tiles[128].demoted_bytes == 256 and tiles[128].spill_bytes == 0
          and tiles[256].spill_bytes == 256
          and tiles[2048].spill_bytes == 16515328
          and tiles[2048].spill_traffic == 33030656)
    check("C7 2048 不分块净收益 34,078,208 B（兑现 50.8%，D73 口径）",
          tiles[2048].net_gain == 34078208
          and abs(tiles[2048].redeem_rate - 0.508) < 1e-3)
    check("C8 并发 tile 数对上 D73：32→12、64→3、128→1（需求超资源时下限 1）",
          tiles[32].concurrent_tiles == 12 and tiles[64].concurrent_tiles == 3
          and tiles[128].concurrent_tiles == 1)
    from fusion_gate_lab import cand_mm_mm
    mm = {k: should_fuse(cand_mm_mm(M1, K1s, k, N1, tile=(128, 128)), m)
          for k in (64, 256, 1024, 4096)}
    check("C9 MM→MM：ΔB = 1/4/16/64 MiB；K1=1024/4096 净收益都封顶 6 MiB"
          "（spill 按行块缩放，D73 A10）",
          mm[64].delta_b == 1048576 and mm[4096].delta_b == 67108864
          and mm[1024].net_gain == mm[4096].net_gain == 6291456)
    check("C10 K1=4096 兑现率 9.4%（6 MiB / 64 MiB）",
          abs(mm[4096].redeem_rate - 0.09375) < 1e-12)
    check("C11 epilogue 指令增量 2/K：贯穿示例 K=3 → 66.7%，大 shape K=64 → 3.1%",
          abs(pr["P3 全融合"].instr_overhead - 2 / 3) < 1e-12
          and abs(tiles[64].instr_overhead - 0.03125) < 1e-12)
    check("C12 动态维度 → known=False（不编造数字），而不是抛异常",
          not should_fuse(dyn, m).known)

    # ---- D. 策略层 ----
    print("== D. 策略：conservative / auto / force 与理由归属 ==")
    check("D1 保守门全收零 spill：tile 32/64/128",
          all(decide(can_fuse(cand_full(M1, K1s, N1, tile=(t, t))),
                     tiles[t]).action == "fuse" for t in (32, 64, 128)))
    d256 = decide(can_fuse(cand_full(M1, K1s, N1, tile=(256, 256))), tiles[256])
    check("D2 tile 256 保守拒绝，理由点名 spill（收益层），hint 给出口",
          d256.action == "refuse" and d256.reasons[0].startswith("保守策略")
          and "spill" in d256.reasons[0] and "缩小 tile" in d256.hint)
    d2048 = decide(can_fuse(cand_full(M1, K1s, N1, tile=(2048, 2048))),
                   tiles[2048], "auto")
    check("D3 同一候选 auto 放行（net 34,078,208 B > 0）——策略只换第三层",
          d2048.action == "fuse")
    check("D4 force 也不看收益：tile 2048 放行",
          decide(can_fuse(cand_full(M1, K1s, N1, tile=(2048, 2048))),
                 tiles[2048], "force").action == "fuse")
    check("D5 force 不能越过合法性：负例（偷中间）在 force 下仍拒绝",
          decide(can_fuse(negs["偷中间"]), None, "force").action == "refuse")
    d4096 = decide(can_fuse(cand_mm_mm(M1, K1s, 4096, N1, tile=(128, 128))),
                   mm[4096])
    check("D6 「合法 ≠ 值得」：K1=4096 合法且下界净收益 +6 MiB，"
          "但保守门拒绝；auto 放行",
          can_fuse(cand_mm_mm(M1, K1s, 4096, N1, tile=(128, 128))).ok
          and d4096.action == "refuse"
          and decide(can_fuse(cand_mm_mm(M1, K1s, 4096, N1, tile=(128, 128))),
                     mm[4096], "auto").action == "fuse")
    dyn_dec = decide(can_fuse(dyn), should_fuse(dyn, m))
    check("D7 动态维度：保守与 auto 都拒绝（收益未知），force 放行，"
          "hint 指向 D62 特化",
          dyn_dec.action == "refuse"
          and decide(can_fuse(dyn), should_fuse(dyn, m), "auto").action == "refuse"
          and decide(can_fuse(dyn), should_fuse(dyn, m), "force").action == "fuse"
          and "特化" in dyn_dec.hint)
    check("D8 拒绝理由能区分层次：非法候选的理由以「合法性：」开头，"
          "spill 拒绝以「保守策略：」开头",
          decide(can_fuse(negs["偷中间"]), None).reasons[0].startswith("合法性")
          and d256.reasons[0].startswith("保守策略"))
    from fusion_gate_lab import LegalityReport, ProfitReport
    zero = ProfitReport(delta_b=0, net_gain=0)
    ok_leg = LegalityReport(ok=True)
    check("D9 净收益为 0 → 拒绝（拒绝 = 回到已知正确的基线）；"
          "decide 可以只吃手造报告——第三层独立可测",
          decide(ok_leg, zero).action == "refuse"
          and decide(ok_leg, zero, "auto").action == "refuse")

    # ---- E. 假设清单 ----
    print("== E. 假设清单 ==")
    check("E1 假设清单 8 项（B1–B8），覆盖机器卡/ΔB/资源/策略/动态/枚举/调度",
          len(ASSUMPTIONS) == 8
          and any("机器假设卡" in b for b in ASSUMPTIONS)
          and any("多使用者规则" in b for b in ASSUMPTIONS)
          and any("下界" in b for b in ASSUMPTIONS)
          and any("行块" in b for b in ASSUMPTIONS))
    check("E2 默认策略写进假设：B4 明确 conservative 拒绝 spill > 0 与收益未知",
          any("conservative 拒绝 spill > 0" in b for b in ASSUMPTIONS))
    leg_r, prof_r, dec_r = run_gate(
        cand_full(M0, K0, N0, tile=(2, 2)), m, "conservative")
    check("E3 run_gate 三件套完整：报告＋账本＋决策（贯穿示例 P3 → fuse）",
          leg_r.ok and prof_r.net_gain == 64 and dec_r.action == "fuse")

    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
