#!/usr/bin/env python3
"""D110 模型引导搜索：Cost Model 排序 → 只实测前 5 名 → 决赛 → 搜索时间对比。

D108 的账（outputs/search-cost.txt）：98 个候选槽全测 57.1 s；外推 D106 全空间
（12,970 个候选）要 ~13 天。今天的流水线把『测』换成『算』：

    校准（一次，~0.2 s）→ 静态排序（µs/候选）→ 只实测模型 top-5（3+7）
    → 决赛 top-3 ∪ 缺省（3+21）→ 冠军

纪律（D107/D108 的规矩原样继承）：
  · 每个被实测的候选都过正确性门——模型负责排序，不负责豁免正确性；
  · 筛选/决赛协议与 D108 完全相同（3+7 / 3+21），冠军同协议可比；
  · 投毒内核（no-tail）不在模型空间里：模型假设完整结构，投毒双胞胎由门守着。

搜索时间对比的三本账：
  · 实测账：本运行的真实墙钟（校准 + 分析 + bench_one 的 Σwall）；
  · 基线账：D108 记录里逐条累加的 Σwall（inputs/results-d108.jsonl）；
  · 外推账：D106 的 12,970 候选空间 × 实测的每候选分析耗时 —— 明确标注
    『外推估算，非实测』，基线引用 D108 search-cost.txt 的 13 天估算。

用法：
  python3 tune_guided.py --exp guided    # 完整运行 → outputs/guided-search.txt
  python3 tune_guided.py --exp topk      # 名额扫描 → outputs/topk-sensitivity.txt
  python3 tune_guided.py --exp drift     # 漂移 A/B 复核 → outputs/drift-a-b.txt
  python3 tune_guided.py --exp extrap    # 外推账单独成文 → outputs/extrapolation.txt
"""

from __future__ import annotations

import dataclasses
import json
import os
import statistics
import time

from bench import (BenchSpec, Protocol, bench_one, capture_env, iso_now)
from kernel_gen import KernelConfig, make_kernel
import cost_model as cm

BAR = "=" * 78
HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUTS = os.path.join(HERE, "outputs")

SCREEN_PROTO = Protocol(warmup=3, repeats=7)    # 与 D108 筛选段同款
FINAL_PROTO = Protocol()                        # 与 D108 决赛段同款（3/21）
TOP_K = 5                                       # 模型预筛后实测的名额
N_FINALISTS = 3                                 # 决赛名额（∪ 缺省，与 D108 同款）
SCHEMA = "d110.guided-result/1"

# D106/D108 文档化的外推参数（引用出处，不在今天重测）
D106_SPACE = 12970                              # D108 search-cost.txt 第四节
D108_13DAYS_NOTE = "12,970×11×7.8 s ≈ 13 天（D108 search-cost.txt 第四节外推，非实测）"


@dataclasses.dataclass
class GuidedRun:
    """一次模型引导搜索的全部记账。"""
    shape_id: str
    M: int
    N: int
    K: int
    n_space: int
    calib_ms: float
    analyze_ms: float
    per_cand_us: float
    model_top5: list
    screen_model_order: list    # [(名次, 配置名, 预测 ms, 实测 ms)]，按模型名次
    screen_walls_ms: list
    final_walls_ms: list
    measured: list          # [(cfg.describe(), median_ms)]
    final_measured: list
    champion: str
    champion_ms: float
    d108_champion: str
    d108_champion_ms: float
    agree: bool


def _append_jsonl(path, rec):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()


def _decorate(rec, sid, stage, pred_ms):
    """bench 记录 → D110 引导搜索记录：盖 d110 章（模型预测值随记录走）。"""
    rec = dict(rec)
    rec["schema"] = SCHEMA
    rec["d110"] = {"shape_id": sid, "stage": stage,
                   "model_pred_ms": round(pred_ms, 3), "top_k": TOP_K}
    return rec


def guided_search(verbose=True, results_path=None):
    """三 shape 各跑一遍：校准 → 排序 → top-5 实测 → 决赛。

    返回 (runs, calib_note)：calib_note 说明单价来自缓存还是现场校准。
    """
    env = capture_env()
    records = cm.load_d108()
    final_truth = cm.stage_truth(records, "final")
    if results_path and os.path.exists(results_path):
        os.remove(results_path)

    costs, calib_note = cm.get_costs()
    calib_ms = costs.wall_ms

    if verbose:
        print(f" 校准来源：{calib_note}")
    runs = []
    for sid, M, N, K in cm.SHAPES:
        cands = cm.build_space(sid, M, N, K)

        # ① 静态排序：零内核执行
        t_an0 = time.perf_counter()
        ranked = sorted(((cm.predict_ms(cm.count_ops(M, N, K, cfg), costs), cfg)
                         for cfg in cands), key=lambda t: t[0])
        analyze_ms = (time.perf_counter() - t_an0) * 1000.0
        per_cand_us = analyze_ms / len(cands) * 1000.0

        # ② 只实测模型 top-5（3+7，过门）
        spec = BenchSpec(M=M, N=N, K=K, seed=42)
        screen = []
        screen_walls = []
        for pred, cfg in ranked[:TOP_K]:
            rec = bench_one(cfg, spec, SCREEN_PROTO, env)
            if results_path:
                _append_jsonl(results_path, _decorate(rec, sid, "screen", pred))
            screen_walls.append(rec["wall_ms"])
            if rec["correctness"]["passed"]:
                screen.append((cfg, rec["stats_ms"]["median"]))
            if verbose:
                tag = (f"{rec['stats_ms']['median']:7.2f} ms"
                       if rec["correctness"]["passed"] else "REJECTED")
                print(f"   screen {cfg.describe():<26} 模型预测 {pred:6.1f} ms → {tag}")

        # ③ 决赛：实测 top-3 ∪ 缺省（3+21）
        med_of = {c: ms for c, ms in screen}
        model_order = [(i, cfg.describe(), pred, med_of.get(cfg, float("nan")))
                       for i, (pred, cfg) in enumerate(ranked[:TOP_K], 1)]
        screen.sort(key=lambda t: t[1])
        want = [cfg for cfg, _ in screen[:N_FINALISTS]]
        if cm.DEFAULT_CFG not in want and cm.DEFAULT_CFG in cands:
            want.append(cm.DEFAULT_CFG)
        final = []
        final_walls = []
        for cfg in want:
            rec = bench_one(cfg, spec, FINAL_PROTO, env)
            if results_path:
                _append_jsonl(results_path, _decorate(rec, sid, "final", float("nan")))
            final_walls.append(rec["wall_ms"])
            if rec["correctness"]["passed"]:
                final.append((cfg, rec["stats_ms"]["median"]))
            if verbose:
                tag = (f"{rec['stats_ms']['median']:7.2f} ms"
                       if rec["correctness"]["passed"] else "REJECTED")
                print(f"   final  {cfg.describe():<26} → {tag}")
        final.sort(key=lambda t: t[1])
        champ_cfg, champ_ms = final[0]

        d108_final = sorted(final_truth[sid], key=lambda t: t[1])
        d108_champ_cfg, d108_champ_ms = d108_final[0][:2]

        runs.append(GuidedRun(
            shape_id=sid, M=M, N=N, K=K, n_space=len(cands),
            calib_ms=calib_ms, analyze_ms=analyze_ms, per_cand_us=per_cand_us,
            model_top5=[cfg.describe() for _, cfg in ranked[:TOP_K]],
            screen_model_order=model_order,
            screen_walls_ms=screen_walls, final_walls_ms=final_walls,
            measured=[(c.describe(), ms) for c, ms in screen],
            final_measured=[(c.describe(), ms) for c, ms in final],
            champion=champ_cfg.describe(), champion_ms=champ_ms,
            d108_champion=d108_champ_cfg.describe(),
            d108_champion_ms=d108_champ_ms,
            agree=(champ_cfg == d108_champ_cfg)))
    return runs, calib_note


def exp_guided() -> str:
    records = cm.load_d108()
    screen_wall = cm.screen_wall_ms(records)
    final_wall = cm.final_wall_ms(records)
    results_path = os.path.join(OUTPUTS, "guided-results.jsonl")

    print(" 模型引导搜索：校准 → 静态排序 → 只实测 top-5 → 决赛（协议与 D108 全同）")
    runs, calib_note = guided_search(verbose=True, results_path=results_path)

    out = [BAR, " D110 模型引导搜索：Cost Model 预筛 + 少量实测", BAR,
           f" 协议：筛选 {SCREEN_PROTO.describe()}", f"       决赛 {FINAL_PROTO.describe()}",
           f" 预筛名额 TOP_K = {TOP_K}（模型排序前 5 名才进实测）",
           f" 校准：{calib_note}；独立部署时校准是一次性成本（~2 s）",
           f" 纪律：所有实测候选过正确性门；投毒内核不在模型空间（门守着，不豁免）",
           f" 环境：{iso_now()}", ""]
    t_all_ms = 0.0
    base_all_ms = 0.0
    for r in runs:
        guided_ms = r.calib_ms / len(cm.SHAPES) + r.analyze_ms \
            + sum(r.screen_walls_ms) + sum(r.final_walls_ms)
        baseline_ms = screen_wall[r.shape_id] + final_wall[r.shape_id]
        t_all_ms += guided_ms
        base_all_ms += baseline_ms
        out.append(f" [{r.shape_id}] {r.M}×{r.N}×{r.K}：空间 {r.n_space} 个候选")
        out.append(f"   模型 top-5（静态排序，{r.analyze_ms:.1f} ms 总计，"
                   f"{r.per_cand_us:.0f} µs/候选）：")
        for i, name in enumerate(r.model_top5, 1):
            out.append(f"     {i}. {name}")
        out.append("   实测（3+7 过门）：" +
                   "  ".join(f"{n}={ms:.2f}" for n, ms in r.measured))
        out.append("   决赛（3+21）：" +
                   "  ".join(f"{n}={ms:.2f}" for n, ms in r.final_measured))
        out.append(f"   冠军：{r.champion} = {r.champion_ms:.2f} ms"
                   f"（D108 全测冠军：{r.d108_champion} = {r.d108_champion_ms:.2f} ms，"
                   f"{'同一配置' if r.agree else '不同配置——跨进程读数，'}"
                   f"{'同进程可比' if r.agree else '见 drift-a-b.txt 交错复核'}）")
        out.append(f"   搜索时间：引导 {guided_ms:.0f} ms（校准摊 "
                   f"{r.calib_ms / len(cm.SHAPES):.0f} + 分析 {r.analyze_ms:.1f} + "
                   f"实测 Σwall {sum(r.screen_walls_ms) + sum(r.final_walls_ms):.0f}）")
        out.append(f"            基线 D108 全测 Σwall = {baseline_ms:.0f} ms"
                   f"（筛选 {screen_wall[r.shape_id]:.0f} + 决赛 {final_wall[r.shape_id]:.0f}，"
                   f"逐条来自 D108 记录）")
        out.append(f"   提速 {baseline_ms / guided_ms:.1f}×；"
                   f"实测候选 {len(r.screen_walls_ms) + len(r.final_walls_ms)} 个"
                   f" vs D108 全测的基线名额")
        out.append("")

    out.append(f" 总账：引导搜索 {t_all_ms / 1000:.1f} s vs D108 全测基线 "
               f"{base_all_ms / 1000:.1f} s → 提速 {base_all_ms / t_all_ms:.1f}×")
    out.append(f" （基线含 D108 全部 98 个筛选槽 + 12 个决赛的 Σwall；"
               f"引导只实测 {sum(len(r.screen_walls_ms) + len(r.final_walls_ms) for r in runs)} 个）")
    agree_n = sum(1 for r in runs if r.agree)
    out.append(f" 冠军一致性：{agree_n}/{len(runs)} 个 shape 与 D108 全测冠军同配置"
               f"（注意：这是跨进程比较——D107 实测过 ~8.6% 漂移，模型预测只差"
               f" ~0.4% 的近对会随机器状态互换；分歧时以 drift-a-b.txt 的"
               f"同进程交错复核为准）")
    out.append(f" 落盘：{os.path.basename(results_path)}"
               f"（{sum(1 for _ in open(results_path))} 条 bench 记录，含模型预测值）")
    return "\n".join(out)


def exp_topk() -> str:
    """TOP_K 敏感性：把预筛名额从 1 扫到 5，看每个名额会选谁。

    实验设计：top-5 的实测只做一次（筛选协议对每个候选独立），
    K<i 的行为 = 只看前 i 条实测记录——等价于当时就把名额设成 i。
    """
    print(" TOP_K 敏感性实验：每 shape 实测模型 top-5 一次，然后按名额切片复盘")
    runs, _ = guided_search(verbose=False)
    out = [BAR, " TOP_K 敏感性：预筛名额 K 扫描（模型误差的直接代价账）", BAR,
           " 问题：名额 K 给多少才够？K=1 等于『完全相信模型』——模型的第 1 名",
           " 是不是真冠军？每个 K 选出的冠军与 D108 真冠军差多少？", ""]
    for r in runs:
        out.append(f" [{r.shape_id}] {r.M}×{r.N}×{r.K}（D108 真冠军 "
                   f"{r.d108_champion} = {r.d108_champion_ms:.2f} ms）")
        out.append("   名额K   选中的配置                 实测 ms   vs 真冠军   判定")
        for kk in (1, 2, 3, 4, 5):
            topk = r.screen_model_order[:kk]
            pick = min(topk, key=lambda t: t[3])
            loss = (pick[3] - r.d108_champion_ms) / r.d108_champion_ms * 100
            if pick[1] == r.d108_champion:
                verdict = "✓ 真冠军（与 D108 同配置）"
            elif loss < 0:
                verdict = "→ 比 D108 记录更快（漂移，非模型误差）"
            else:
                verdict = f"✗ 漏掉（慢 {loss:.1f}%：模型误差的代价）"
            out.append(f"   {kk:>4}    {pick[1]:<26} {pick[3]:7.2f}   "
                       f"{loss:+5.1f}%    {verdict}")
        out.append("")
    # 结尾读法按本次数据计算，不写死配置名
    m1s, ranks = [], []
    for r in runs:
        m1 = r.screen_model_order[0]
        loss1 = (m1[3] - r.d108_champion_ms) / r.d108_champion_ms * 100
        m1s.append(f"{r.shape_id} 的模型第 1 名 {m1[1]}（实测比 D108 冠军 "
                   f"{loss1:+.1f}%）")
        rank = next((i for i, nm, _, _ in r.screen_model_order
                     if nm == r.d108_champion), None)
        ranks.append(rank if rank is not None else 6)
    out.append(f" 读法：K=1 = 完全相信模型——会选中 {'；'.join(m1s)}。")
    out.append(f"       D108 真冠军在模型第 {min(ranks)}~{max(ranks)} 名，"
               f"K={max(ranks)} 起全部进入名额。分工就是：")
    out.append("       模型负责砍数量（recall@K 才是它的 KPI），同进程实测负责定名次。")
    out.append("       判定为『→ 更快』的行是环境漂移：选中的配置在当下进程里确实")
    out.append("       比 D108 冠军的记录还快——这不是模型选对了，也不是选错了，")
    out.append("       是两台机器状态的读数不能同表比较（D107 的纪律）。（3+7 中位数）")
    return "\n".join(out)


def exp_extrap() -> str:
    """外推账：把今天的流水线放大到 D106 的 12,970 候选空间（明确标注估算）。"""
    t0 = time.perf_counter()
    for cfg in cm.build_space("S2", 96, 96, 96):
        cm.count_ops(96, 96, 96, cfg)
    per_cand_us = (time.perf_counter() - t0) / len(cm.build_space("S2", 96, 96, 96)) * 1e6

    # 每候选实测成本：用 D108 S2 记录的平均 wall（3+7 协议，含门+预热+计时）
    records = cm.load_d108()
    s2_screen = [r["wall_ms"] for r in records
                 if r["tune"]["shape_id"] == "S2" and r["tune"]["stage"] == "screen"]
    avg_bench_s = sum(s2_screen) / len(s2_screen) / 1000.0

    analysis_s = D106_SPACE * per_cand_us / 1e6
    bench_s = TOP_K * avg_bench_s + 4 * avg_bench_s * 3   # top-5 筛选 + 4 决赛(3/21 按 3 倍估)
    full_s = D106_SPACE * avg_bench_s

    out = [BAR, " 外推账：模型引导搜索放大到 D106 全空间（12,970 候选）", BAR,
           " 以下为外推估算，非实测——每个因子单独实测，乘法是算出来的：", "",
           f" ① 每候选静态分析耗时（本机实测，S2 形状）：{per_cand_us:.0f} µs",
           f"    → 12,970 个候选全部分析完：{analysis_s:.1f} s",
           f" ② 每候选实测成本（D108 S2 记录平均 wall，3+7 协议）：{avg_bench_s:.2f} s",
           f"    → 模型引导只测 top-5 筛选 + 4 决赛：≈ {TOP_K}×{avg_bench_s:.2f} + "
           f"4×{avg_bench_s * 3:.2f} ≈ {bench_s:.0f} s",
           f"    → 全空间逐个实测：12,970 × {avg_bench_s:.2f} s ≈ {full_s / 3600:.1f} 小时",
           f"       （D108 的口径是 512³ 大 shape：{D108_13DAYS_NOTE}）",
           "",
           f" 结论（估算）：模型引导 ≈ 校准 0.2 s + 分析 {analysis_s:.1f} s + 实测 {bench_s:.0f} s"
           f" ≈ {analysis_s + bench_s + 0.2:.0f} s 量级",
           f"          vs 全测的 {full_s / 3600:.1f} 小时（96³ 口径）~ 13 天（512³ 口径）——",
           "          搜索成本从『天』压到『分钟』，前提只有一个：真冠军得留在模型 top-K 里。",
           "          今天三个 shape 的 D108 真冠军都留在模型 top-5（accuracy.txt 的 recall@5，",
           "          自检有断言把守）；但 recall@K 是经验数字，换执行环境（换机器/换",
           "          Python 版本）要重新对账。"]
    return "\n".join(out)


def exp_drift() -> str:
    """漂移 A/B：D108 冠军 kij 与它的 j 家族近邻 ikj，同进程交错重测 3 回合。

    动机：复现时发现引导搜索选出的冠军与 D108 记录互换（ikj ↔ kij）。
    这对候选在模型预测里只差 ~0.4%，在 D108 记录里差 ~8%——近对的实测
    次序会随机器状态漂移（D107 量过跨进程 ~8.6%）。交错 A/B 在同一进程
    里回答：当下这台机器，谁快？分歧到底是模型误差还是环境漂移？
    """
    records = cm.load_d108()
    truth = cm.stage_truth(records, "final")
    env = capture_env()
    spec = BenchSpec(M=64, N=64, K=64, seed=42)
    pair = {"kij": KernelConfig(64, 64, 64, "kij", 1),
            "ikj": KernelConfig(64, 64, 64, "ikj", 1)}
    d108 = {}
    for cfg, ms, _name in truth["S1"]:
        for nm, c in pair.items():
            if cfg == c:
                d108[nm] = ms

    print(" 漂移 A/B 复核：S1 的 ikj vs kij（D108 冠军），交错 3 回合 × 3+21")
    rows = {nm: [] for nm in pair}
    for rnd in (1, 2, 3):
        line = f"   回合 {rnd}："
        for nm in ("kij", "ikj"):
            rec = bench_one(pair[nm], spec, FINAL_PROTO, env)
            ms = rec["stats_ms"]["median"]
            rows[nm].append(ms)
            line += f"{nm}={ms:6.2f} ms（spread {rec['stats_ms']['spread_pct']:.1f}%）  "
        print(line)

    med = {nm: statistics.median(rows[nm]) for nm in pair}
    cur_fast = min(med, key=med.get)
    d108_fast = min(d108, key=d108.get)
    flipped = cur_fast != d108_fast
    gap_now = (med[max(med, key=med.get)] - med[cur_fast]) / med[cur_fast] * 100
    gap_108 = (d108[max(d108, key=d108.get)] - d108[d108_fast]) / d108[d108_fast] * 100

    out = [BAR, " 漂移 A/B：ikj vs kij（模型近对，预测只差 ~0.4%）", BAR,
           f" 协议：{FINAL_PROTO.describe()}；3 回合交错，同进程同环境（{iso_now()}）",
           "",
           "          本回合（当下进程）            D108 决赛记录（另一进程）"]
    for nm in ("kij", "ikj"):
        out.append(f"   {nm}  中位 {med[nm]:6.2f} ms  3 回合 "
                   f"{' '.join(f'{x:.2f}' for x in rows[nm])}"
                   f"    中位 {d108[nm]:6.2f} ms")
    out += ["",
            f" 当下更快：{cur_fast}（另一边慢 {gap_now:.1f}%）"
            f"    D108 记录更快：{d108_fast}（另一边慢 {gap_108:.1f}%）",
            f" 判定：{'次序互换——机器状态漂移，不是模型误差、也不是内核变化' if flipped else '次序未变'}。"]
    if flipped:
        out += [" 解释：模型给 ikj/kij 的预测本来只差 0.3~0.4%（近对）；实测里这对近对",
                "       随机器状态互换领先者。D108 进程量到 kij 快 ~8%，本进程量到 ikj",
                "       快 ~6%——同协议同门，两个进程各自的读数都自洽，但不能进同一张",
                "       排名表（D107 纪律：跨进程漂移 ~8.6%）。引导搜索的冠军是『当下",
                "       进程里的最快』，这正是调优器的本职——对当下环境负责。"]
    out += [" 启示：① 排行榜（模型）稳定是因为它不执行代码；实测冠军会随环境漂移。",
            "       ② cost model 的 KPI 是 recall@K（把所有可能冠军留在名额里），",
            "       不是精确名次；③ 跨进程的冠军对比只能当参考，结论以同进程 A/B 为准。"]
    return "\n".join(out)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D110 模型引导搜索")
    ap.add_argument("--exp", required=True, choices=["guided", "topk", "drift", "extrap"])
    args = ap.parse_args()
    os.makedirs(OUTPUTS, exist_ok=True)
    if args.exp == "guided":
        print(exp_guided())
    elif args.exp == "topk":
        print(exp_topk())
    elif args.exp == "drift":
        print(exp_drift())
    else:
        print(exp_extrap())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
