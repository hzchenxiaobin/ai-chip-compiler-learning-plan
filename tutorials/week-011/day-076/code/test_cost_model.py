#!/usr/bin/env python3
"""test_cost_model.py —— 第 76 天独立验收测试。

不复用主实验的运行结果：每个用例重新构造候选、重新计价、重新决策，再对照
「预期判决 + 预期数字 + 预期理由归属」。分八组：

  A ground truth 回归（16 例 auto 判决 + force 列语义）
  B 评分数字（R1 双形式 / R2ctl / R3 双形式 / R4 / 恒等式 / spill 共用）
  C 门槛归因（评分 ≤ 0 / spill 一票否决 / 并行度门槛 / 三门槛全过）
  D 模式差异（force 合法即融 / 动态 Shape / 评分照记）
  E 误差参数轴（换机器卡：R4 翻转 / 32 KiB 卡的三个翻转 / 评分不变）
  F 记账对拍独立重跑（10 组随机，种子与主实验不同）
  G IR 对照（kernel 数 / keep-recompute 的 outs 差别 / kept alloc）
  H 可解释性（出处标注 / 未计价清单 / 形式提示 / 动态提示）

运行：python3 test_cost_model.py
"""

from __future__ import annotations

import random

from cost_model import (
    Machine, CostModel, FusionCandidate, Intermediate,
    can_fuse, price_keep, price_recompute, explain,
    ledger_bytes, chain_ops, cand_full, cand_mm_mm, cand_skinny,
    wing_a_cases, wing_b_cases,
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
    model = CostModel(m)

    # ---- A. ground truth 回归 ----
    print("== A. ground truth 回归：16 例 × auto/force ==")
    all_cases = wing_a_cases() + wing_b_cases()
    auto_ok = force_ok = 0
    for e in all_cases:
        c = e.build()
        if model.evaluate(c, "auto").action == e.expect_auto:
            auto_ok += 1
        expect_force = "refuse" if not can_fuse(c).ok else "fuse"
        if model.evaluate(c, "force").action == expect_force:
            force_ok += 1
    check("A1 auto 判决与 D75 案例库 16 例逐例一致（ground truth 回归）",
          auto_ok == 16)
    check("A2 force 列语义：非法 8 例 refuse（force 也不融非法的图）、"
          "合法 8 例 fuse", force_ok == 16)
    n_refuse_b = sum(1 for e in wing_b_cases()
                     if model.evaluate(e.build(), "auto").action == "refuse")
    check("A3 翼 B 的 auto 判决分布：5 拒（R1/R1ctl/R2/R3重算/R4）3 融"
          "（R2ctl/R3keep/R4ctl）", n_refuse_b == 5)

    # ---- B. 评分数字（独立重算）----
    print("\n== B. 评分数字（独立重算）==")
    r1_keep = cand_mm_mm(2048, 64, 1024, 2048, (128, 128), out_users=1,
                         name="R1 keep")
    rep_k = model.evaluate(r1_keep, "auto")
    rep_x = model.evaluate(
        cand_mm_mm(2048, 64, 1024, 2048, (128, 128), out_users=1,
                   name="R1 recompute", form="recompute"), "auto")
    fk, fx = rep_k.forms["keep"], rep_x.forms["recompute"]
    check("B1 R1 keep 评分 −2,097,152 B（ΔB 8,388,608 − spill 10,485,760）",
          fk.score == -2_097_152 and fk.delta_b == 8_388_608
          and fk.spill_traffic == 10_485_760)
    check("B2 R1 recompute 评分 +13,893,632 B"
          "（消除 25,165,824 − 罚 786,432 − spill 10,485,760）",
          fx.score == 13_893_632 and fx.recompute_elim == 25_165_824
          and fx.recompute_penalty == 786_432)
    check("B3 R1 两形式的资源账共用：spill 同为 10,485,760 B（核结构一样）",
          fk.spill_traffic == fx.spill_traffic == 10_485_760
          and fk.live_bytes == fx.live_bytes == 589_824)
    check("B4 形式排序差 = 15,990,784 B（recompute 消掉了写趟＋组外读，"
          "只多付一遍生产者输入重读）",
          fx.score - fk.score == 15_990_784)
    r2ctl = model.evaluate(cand_mm_mm(2048, 64, 64, 2048, (64, 64),
                                      name="R2ctl"), "auto")
    check("B5 R2ctl 评分 +1,048,576 B、零 spill、寄存器并发 4",
          r2ctl.forms["keep"].score == 1_048_576
          and r2ctl.forms["keep"].spill_bytes == 0
          and r2ctl.forms["keep"].reg_tiles == 4)
    r3k = model.evaluate(cand_skinny(64, 4096, 64, out_users=2,
                                     name="R3keep"), "auto")
    r3x = model.evaluate(cand_skinny(64, 4096, 64, out_users=2,
                                     name="R3x", form="recompute"), "auto")
    check("B6 R3keep 评分 +16,384 B；寄存器并发 3 而完整模型并发 1"
          "（工作集与复用是两个量——门槛用前者）",
          r3k.forms["keep"].score == 16_384
          and r3k.forms["keep"].reg_tiles == 3
          and r3k.forms["keep"].concurrent_tiles == 1)
    check("B7 R3recompute 评分 −4,128,768 B（消除 65,536 − 罚 4,194,304）",
          r3x.forms["recompute"].score == -4_128_768
          and r3x.forms["recompute"].recompute_elim == 65_536
          and r3x.forms["recompute"].recompute_penalty == 4_194_304)
    r4 = model.evaluate(cand_full(2048, 64, 2048, tile=(128, 128),
                                  name="R4"), "auto")
    check("B8 R4 评分 +67,108,864 B、零 spill、寄存器并发 1"
          "（评分正但门槛拦——与 D75 的分歧行同判）",
          r4.forms["keep"].score == 67_108_864
          and r4.forms["keep"].spill_bytes == 0
          and r4.forms["keep"].reg_tiles == 1)
    id_ok = True
    for e in wing_b_cases():
        rep = model.evaluate(e.build(), "auto")
        if rep.legal and rep.forms[rep.form].known:
            fs = rep.forms[rep.form]
            id_ok &= (fs.score == sum(i.sign * i.bytes for i in fs.items))
    check("B9 评分恒等式：score == Σ sign·bytes（翼 B 全部声明形式）", id_ok)

    # ---- C. 门槛归因 ----
    print("\n== C. 门槛归因（谁在拒绝）==")
    r1ctl = model.evaluate(cand_mm_mm(2048, 64, 1024, 2048, (128, 128),
                                      name="R1ctl"), "auto")
    check("C1 R1ctl：评分 +6,291,456 B > 0 仍拒——首条理由是 spill 一票否决",
          r1ctl.forms["keep"].score == 6_291_456
          and r1ctl.action == "refuse"
          and r1ctl.reasons[0].startswith("一票否决"))
    check("C2 R4：评分正、零 spill，首条理由是并行度门槛（寄存器并发 1 < 3）",
          r4.action == "refuse" and r4.reasons[0].startswith("并行度门槛"))
    check("C3 R2ctl：三门槛全过才融（评分 / 零 spill / 并发 4 ≥ 3）",
          r2ctl.action == "fuse" and r2ctl.reasons[0].startswith("评分"))
    prefixes = ("合法性：", "评分", "一票否决", "并行度门槛", "评分未知")
    refuse_rows = [model.evaluate(e.build(), "auto") for e in all_cases]
    refuse_rows = [r for r in refuse_rows if r.action == "refuse"]
    check("C4 全部 13 个拒绝行（翼 A 8 ＋ 翼 B 5）的首条理由都可归因到"
          "四类前缀之一", all(r.reasons[0].startswith(prefixes)
                            for r in refuse_rows) and len(refuse_rows) == 13)

    # ---- D. 模式差异 ----
    print("\n== D. 模式差异（force vs auto）==")
    legal_fuse = all(model.evaluate(e.build(), "force").action == "fuse"
                     for e in wing_b_cases())
    check("D1 force 对翼 B 全部 8 例（含 5 个 auto 拒绝的）都 fuse",
          legal_fuse)
    dyn = cand_full(-1, 64, 2048, tile=(64, 64), name="dyn")
    check("D2 动态 Shape：auto 拒（评分未知）、force 融（只看合法性）",
          model.evaluate(dyn, "auto").action == "refuse"
          and model.evaluate(dyn, "force").action == "fuse")
    rf4 = model.evaluate(cand_full(2048, 64, 2048, tile=(128, 128),
                                   name="R4"), "force")
    check("D3 force 的理由里评分照记：R4 force 融且理由含 67,108,864 B",
          rf4.action == "fuse" and "67,108,864" in rf4.reasons[0])

    # ---- E. 误差参数轴：换机器卡 ----
    print("\n== E. 误差参数轴：只换机器卡，看判决翻转 ==")
    big = CostModel(Machine(name="wide", regfile_bytes=256 * 1024))
    r4_big = big.evaluate(cand_full(2048, 64, 2048, tile=(128, 128),
                                    name="R4"), "auto")
    check("E1 寄存器堆 64→256 KiB：R4 寄存器并发 1→3、refuse→fuse；"
          "评分不变 67,108,864 B（翻转全部来自门槛，不来自计价）",
          r4_big.action == "fuse" and r4_big.forms["keep"].reg_tiles == 3
          and r4_big.forms["keep"].score == 67_108_864)
    small = CostModel(Machine(name="narrow", regfile_bytes=32 * 1024))
    flips = []
    for nm, c in (("R2ctl", cand_mm_mm(2048, 64, 64, 2048, (64, 64), name="R2ctl")),
                  ("R3keep", cand_skinny(64, 4096, 64, out_users=2, name="R3keep")),
                  ("R4ctl", cand_full(2048, 64, 2048, tile=(64, 64), name="R4ctl"))):
        if (model.evaluate(c, "auto").action == "fuse"
                and small.evaluate(c, "auto").action == "refuse"):
            flips.append(nm)
    check("E2 寄存器堆 64→32 KiB：R2ctl / R3keep / R4ctl 三个原本融合的"
          "全部翻成 refuse（参数误差的另一侧）", flips == ["R2ctl", "R3keep", "R4ctl"])
    s_r2ctl = small.evaluate(cand_mm_mm(2048, 64, 64, 2048, (64, 64),
                                        name="R2ctl"), "auto")
    check("E3 同一候选换卡只翻判决不翻计价：32 KiB 卡下 R2ctl 评分仍为 "
          "+1,048,576 B（ΔB 与机器无关，spill 仍为 0）",
          s_r2ctl.forms["keep"].score == 1_048_576
          and s_r2ctl.forms["keep"].spill_bytes == 0)

    # ---- F. 记账对拍（独立随机，种子 760 ≠ 主实验的 76）----
    print("\n== F. 记账对拍（独立随机 10 组）==")
    rng = random.Random(760)
    ok_keep = ok_recompute = n_recompute = 0
    for t in range(10):
        kind = rng.choice(("p3", "mm2", "skinny"))
        M, K, N, Kmid = (rng.randint(1, 40) for _ in range(4))
        r = rng.randint(0, 3)
        if kind == "p3":
            c = FusionCandidate(
                f"t{t}", chain_ops(M, K, N),
                intermediates=(Intermediate("C", M * N, 1, r, kept=r > 0),),
                workload=(M, K, N))
        elif kind == "mm2":
            c = cand_mm_mm(M, K, Kmid, N, (M, N), out_users=r, name=f"t{t}")
        else:
            c = cand_skinny(M, K, N, out_users=r, name=f"t{t}")
        b, f = ledger_bytes(c, "keep")
        if b - f == price_keep(c, m).delta_b:
            ok_keep += 1
        if any(it.out_group_users > 0 for it in c.intermediates):
            n_recompute += 1
            b2, f2 = ledger_bytes(c, "recompute")
            fr_ = price_recompute(c, m)
            if b2 - f2 == fr_.recompute_elim - fr_.recompute_penalty:
                ok_recompute += 1
    check("F1 keep 对拍 10/10：记账差值 == ΔB 公式", ok_keep == 10)
    check("F2 recompute 对拍：记账差值 == elim − 罚（有组外的全部一致）",
          n_recompute >= 4 and ok_recompute == n_recompute)
    c_mm = cand_mm_mm(2048, 64, 1024, 2048, (128, 128))
    b_mm, f_mm = ledger_bytes(c_mm, "keep")
    check("F3 对拍边界：记账器差值 == ΔB 16,777,216 B，但看不见 spill "
          "10,485,760 B——容量项只能靠模型（误差的口径轴）",
          b_mm - f_mm == 16_777_216
          and price_keep(c_mm, m).spill_traffic == 10_485_760)

    # ---- G. IR 对照 ----
    print("\n== G. IR 对照 ==")
    p3 = model.evaluate(cand_full(2, 3, 2), "auto")
    check("G1 贯穿链 IR：融合前 3 kernel/3 alloc → 融合后 1 kernel/1 alloc，"
          "kernel 名 mini.fused_matmul_bias_relu",
          p3.ir_before.count("memref.alloc") == 3
          and p3.ir_after.count("memref.alloc") == 1
          and "mini.fused_matmul_bias_relu" in p3.ir_after)
    r1r = model.evaluate(cand_mm_mm(2048, 64, 1024, 2048, (128, 128),
                                    out_users=1, name="R1k"), "auto")
    r1x = model.evaluate(cand_mm_mm(2048, 64, 1024, 2048, (128, 128),
                                    out_users=1, name="R1x",
                                    form="recompute"), "auto")
    out_r = [l for l in r1r.ir_after.splitlines() if "outs(" in l][0]
    out_x = [l for l in r1x.ir_after.splitlines() if "outs(" in l][0]
    check("G2 R1 双形式 IR：keep 的 outs 是 (%g, %f)、recompute 的 outs 只 (%f)",
          "%g" in out_r and "%f" in out_r and "_keep" in out_r
          and "%g" not in r1x.ir_after and "_recompute" in out_x)
    r3k = model.evaluate(cand_skinny(64, 4096, 64, out_users=2, name="R3k"),
                         "auto")
    r3x = model.evaluate(cand_skinny(64, 4096, 64, out_users=2, name="R3x",
                                     form="recompute"), "auto")
    check("G3 R3 双形式 IR：keep 有 %c = memref.alloc（C 落盘喂组外）、"
          "recompute 无 %c（C 不落盘）",
          "%c = memref.alloc" in r3k.ir_after
          and "%c" not in r3x.ir_after)
    check("G4 融合前 IR 的 kernel 数 == 算子数（16 例合法候选全部成立）",
          all(model.evaluate(e.build(), "auto").ir_before.count("mini.")
              + model.evaluate(e.build(), "auto").ir_before.count("experimental.")
              == len(e.build().ops)
              for e in wing_b_cases()))

    # ---- H. 可解释性 ----
    print("\n== H. 可解释性（报告是人能读的）==")
    txt = explain(rep_k)
    check("H1 明细账每项带出处：R1 keep 报告含 [D72] 与 [D73] 标注",
          "[D72]" in txt and "[D73]" in txt)
    check("H2 未计价清单如实：含 launch/编译时间 与 并发 proxy 两条",
          any("launch" in u for u in rep_k.unpriced)
          and any("proxy" in u for u in rep_k.unpriced))
    check("H3 形式提示：R1（keep 拒）提示 recompute 评分更高；"
          "R3recompute（recompute 拒）提示 keep 评分更高",
          any("recompute 形式评分" in h for h in rep_k.hints)
          and any("keep 形式评分" in h
                  for h in model.evaluate(
                      cand_skinny(64, 4096, 64, out_users=2, name="R3x",
                                  form="recompute"), "auto").hints))
    dyn_rep = model.evaluate(dyn, "auto")
    check("H4 动态 Shape 的报告说人话：评分未知 + 「特化」出口",
          "未知" in explain(dyn_rep) and "特化" in explain(dyn_rep))

    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
