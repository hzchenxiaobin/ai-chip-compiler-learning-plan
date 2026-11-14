#!/usr/bin/env python3
"""D108 Auto-tuning v0.1：把 D106 的候选生成和 D107 的 bench_one 接成一个自动循环。

    对每个 shape：枚举候选 → 编译（mini Lowering）→ 正确性门 → 筛选测量 → 排名
                   → 决赛复测 → 冠军；全程边测边写 JSONL，断点可续跑。

今天的学习目标——三种时间的账，全部真实测量：
    编译时间  生成+编译一个候选的一次性成本（tune.compile_ms，本环境 ~0.3 ms/候选；
              真实 MLIR/LLVM 管线是 0.1~10 s 量级，账会完全反过来）
    执行时间  内核每次调用跑多久（stats_ms.median，D107 协议，每次生产调用都付）
    搜索成本  整场调优的总账 = Σ编译 + Σ门/预热/计时 + 记账开销（一次性 per shape 集合，
              要靠摊销收回：N_break-even = 搜索成本 ÷ 每次省下的执行时间）

v0.1 的搜索成本三道闸门：
    ① 空间精选  3 个 shape × {32,64} cube tile + 单 tile × 6 顺序 × U∈{1,4}
                = 96 个规则候选（D106 的 12,970 全空间按本环境成本模型外推 ~12 天，
                教程里跑精选空间验证闭环，循环原样可放大）
    ② 两段式    筛选段 3+7（D107 前缀扫描：k≥7 最坏摆 0.11%）→ 决赛段恢复 3+21；
                决赛名单 = 筛选 top-3 ∪ 缺省对照（冠军 vs 缺省同协议同进程可比）
    ③ 断点续跑  每条记录追加式落盘（flush），重启按 (shape, kernel, stage) 键跳过已完成

投毒探针：S3（90×96×64，M=90 不被 4 整除）放两个 no-tail 内核——错误版本
比正确双胞胎快（少算尾部），验证门在自动搜索里依然先行（D97 错误三）。

分工边界：本文件只负责循环和记账；统计口径是 D107 的，生成纪律是 D106 的，
GFLOPS/算术强度是 D109 的，cost model 预剪是 D110 的。
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import os
import sys
import tempfile
import time

from kernel_gen import KernelConfig, make_kernel
from bench import BenchSpec, Protocol, bench_one, capture_env, iso_now

BAR = "=" * 78
SCHEMA = "d108.tune-result/1"      # d107.bench-result/1 的字段只增不改（tune 块）
SUMMARY_SCHEMA = "d108.tune-summary/1"

# ---------------------------------------------------------------- 搜索空间说明书

SHAPES = (
    ("S1", 64, 64, 64),    # 整除、小
    ("S2", 96, 96, 96),    # 整除、D97~107 主力
    ("S3", 90, 96, 64),    # M=90 不被 4 整除：尾部路径 + 投毒现场
)
CUBE_TILES = (32, 64)                          # D97~107 一路的主力 tile
UNROLLS = (1, 4)                               # U=1 缺省；U=4（CPython 已知吃亏，留着让账说话）
ORDERS = tuple("".join(p) for p in itertools.permutations("ijk"))
DEFAULT_CFG = KernelConfig(32, 32, 32, "ijk", 1)   # 工程师不调优时的缺省（D97 baseline 同构）

# 投毒探针：no-tail 内核（尾部循环不生成）。只在 S3 上投——inner=i 的展开在
# M=90 上必有 2 圈尾部（90%4=2；t=32 时最后一块 26 行，26%4=2），
# 少算的活让它比正确双胞胎快，纯计时表里它是黑马。
POISON = (
    ("S3", KernelConfig(90, 96, 64, "jki", 4), "no-tail"),
    ("S3", KernelConfig(32, 32, 32, "jki", 4), "no-tail"),
)

SCREEN_PROTO = Protocol(warmup=3, repeats=7)   # 筛选段：血统同 D107，样本 21→7
FINAL_PROTO = Protocol()                       # 决赛段：D107 全协议 3/21


def kernel_name(cfg: KernelConfig, poisoned: bool = False) -> str:
    """与 make_kernel().name 同款命名（含 /no-tail 后缀），续跑键用它——
    不编译就能查键，缓存账才不会被『查个名字』污染。"""
    return f"tiled-matmul/{cfg.describe()}" + ("/no-tail" if poisoned else "")


def build_space(shape_id, M, N, K, poisons=POISON):
    """一个 shape 的候选槽：cube tile {32,64} ∩ 放得下 + 单 tile（去重）× 6 顺序 × U{1,4}。

    单 tile = (M,N,K)：一次 tile 外壳都不跑的对照（CPython 里循环开销主导，它常赢——
    这反映字节码成本模型，不反映硬件缓存收益，README 5.3 有边界说明）。
    """
    tiles = [t for t in CUBE_TILES if t <= min(M, N, K)]
    if (M, N, K) not in [(t, t, t) for t in tiles]:
        tiles.append((M, N, K))
    cands = []
    for t in tiles:
        tm, tn, tk = (t, t, t) if isinstance(t, int) else t
        for order in ORDERS:
            for u in UNROLLS:
                cands.append((KernelConfig(tm, tn, tk, order, u), False))
    for sid, cfg, tag in poisons:
        if sid == shape_id:
            assert tag == "no-tail"
            cands.append((cfg, True))
    seen = set()
    for cfg, poisoned in cands:                 # 双保险：空间内不允许重复键
        key = (cfg, poisoned)
        assert key not in seen, f"重复候选 {key}"
        seen.add(key)
    return cands


# ---------------------------------------------------------------- 记录与落盘


def key_of(rec: dict) -> tuple:
    """断点续跑的键：(shape, kernel 名含 /no-tail 后缀, stage)。"""
    return (rec["tune"]["shape_id"], rec["kernel"]["name"], rec["tune"]["stage"])


def load_records(path: str) -> list:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def append_jsonl(path: str, rec: dict) -> None:
    """追加式落盘，立刻 flush——断点续跑的地基（D107 埋的钉子今天兑现）。"""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()


def decorate(rec: dict, shape_id: str, stage: str, cand_idx: int,
             compile_ms: float, cached: bool, name: str) -> dict:
    """D107 记录 → D108 调优记录：升 schema、盖 tune 章。

    bench.record_from 用 cfg.describe() 起名，投毒内核会与正确双胞胎同名——
    这里用带 /no-tail 后缀的名字覆盖，死因台账才分得清双胞胎。
    """
    rec = dict(rec)
    rec["schema"] = SCHEMA
    rec["kernel"] = dict(rec["kernel"])
    rec["kernel"]["name"] = name
    rec["tune"] = {
        "shape_id": shape_id,
        "stage": stage,
        "cand_idx": cand_idx,
        "compile_ms": round(compile_ms, 4),
        "compile_cached": cached,
    }
    return rec


# ---------------------------------------------------------------- 编译缓存、记账与摊销


@dataclasses.dataclass
class RunStats:
    slots: int = 0               # 走到的候选槽
    measured: int = 0            # 新测量记录数（screen+final）
    skipped: int = 0            # 断点续跑跳过的已完成键
    compile_misses: int = 0
    compile_hits: int = 0
    compile_ms: float = 0.0
    invocations: int = 0         # 内核调用次数（门+预热+计时）
    bench_wall_ms: float = 0.0   # Σ bench_one 的 wall（含输入生成+参考实现+门+计时）
    budget_hit: bool = False


def compile_step(cfg: KernelConfig, poisoned: bool, cache: dict, st: RunStats):
    """编译一个候选（源码生成→compile→exec）。缓存键=(cfg, no-tail)，跨 shape、跨段复用。"""
    k = (cfg, poisoned)
    if k in cache:
        st.compile_hits += 1
        return cache[k], 0.0, True
    t0 = time.perf_counter()
    kernel = make_kernel(cfg, drop_tail=poisoned)
    cms = (time.perf_counter() - t0) * 1000.0
    st.compile_misses += 1
    st.compile_ms += cms
    cache[k] = kernel
    return kernel, cms, False


def runs_of(rec: dict) -> int:
    """一条记录烧掉多少次内核调用：过门 1 次 + 预热 + 计时；被拒的只烧门那 1 次。"""
    if not rec["correctness"]["passed"]:
        return 1
    p = rec["protocol"]
    return 1 + p["warmup"] + p["repeats"]


def break_even(cost_ms: float, saved_ms: float) -> float:
    """N_break-even = 搜索成本 ÷ 每次省下的执行时间；省不出时间就永不回本。"""
    if saved_ms <= 0:
        return float("inf")
    return cost_ms / saved_ms


# ---------------------------------------------------------------- 主循环：tune


def tune_run(outdir: str = "outputs", limit=None, screen_repeats: int = 7,
             n_finalists: int = 3, shapes=SHAPES, poisons=POISON,
             results_path=None, verbose=True) -> str:
    """跑一遍调优循环。limit=N：新测量满 N 条就收工（断点续跑演示用）。"""
    os.makedirs(outdir, exist_ok=True)
    results_path = results_path or os.path.join(outdir, "results.jsonl")
    env = capture_env()
    screen_proto = Protocol(warmup=3, repeats=screen_repeats)
    final_proto = FINAL_PROTO

    existing = load_records(results_path)
    done = {key_of(r): r for r in existing}
    st = RunStats()
    cache = {}
    t0 = time.perf_counter()
    lines = [BAR, " Auto-tuning v0.1：枚举 → 编译 → 门 → 筛选测量 → 排名 → 决赛复测", BAR,
             f" shapes：{' / '.join(f'{s[0]} {s[1]}×{s[2]}×{s[3]}' for s in shapes)}",
             f" 筛选协议 {screen_proto.describe()}    决赛协议 {final_proto.describe()}",
             f" 断点续跑：results.jsonl 已有 {len(existing)} 条记录，按键跳过", ""]

    for sid, M, N, K in shapes:
        spec = BenchSpec(M=M, N=N, K=K, seed=42)
        cands = build_space(sid, M, N, K, poisons)
        lines.append(f" [{sid}] {M}×{N}×{K}：{len(cands)} 个候选进入筛选段")
        for idx, (cfg, poisoned) in enumerate(cands):
            st.slots += 1
            key = (sid, kernel_name(cfg, poisoned), "screen")
            if key in done:
                st.skipped += 1
                continue
            if limit is not None and st.measured >= limit:
                st.budget_hit = True
                break
            kernel, cms, cached = compile_step(cfg, poisoned, cache, st)
            rec = bench_one(cfg, spec, screen_proto, env, kernel=kernel)
            rec = decorate(rec, sid, "screen", idx, cms, cached, kernel_name(cfg, poisoned))
            append_jsonl(results_path, rec)
            done[key] = rec
            st.measured += 1
            st.invocations += runs_of(rec)
            st.bench_wall_ms += rec["wall_ms"]
            if verbose:
                s = rec["stats_ms"]
                tag = (f"{s['median']:8.2f} ms" if s
                       else f"REJECTED err={rec['correctness']['max_abs_err']:.2f}")
                lines.append(f"   #{idx + 1:>2} {kernel_name(cfg, poisoned).split('/', 1)[1]:<26} → {tag}")
        if st.budget_hit:
            lines.append(f" 预算到站：新测 {st.measured} 条已全部落盘，本次收工——"
                         f"重启后同一命令从断点继续（已有记录全部有效）")
            break

        # ---- 决赛段：筛选 top-K ∪ 缺省对照，恢复 D107 全协议 3/21 ----
        screened = [r for r in done.values()
                    if r["tune"]["shape_id"] == sid and r["tune"]["stage"] == "screen"
                    and r["correctness"]["passed"]]
        screened.sort(key=lambda r: r["stats_ms"]["median"])
        want = [KernelConfig(r["kernel"]["tm"], r["kernel"]["tn"], r["kernel"]["tk"],
                             r["kernel"]["order"], r["kernel"]["unroll"])
                for r in screened[:n_finalists]]
        if DEFAULT_CFG not in want and DEFAULT_CFG in [c for c, _ in cands]:
            want.append(DEFAULT_CFG)            # 缺省进决赛：冠军 vs 缺省同协议同进程
        lines.append(f" [{sid}] 决赛段：top-{n_finalists} ∪ 缺省 {DEFAULT_CFG.describe()}"
                     f" → {len(want)} 个候选恢复 3/21 复测")
        for cfg in want:
            key = (sid, kernel_name(cfg), "final")
            if key in done:
                st.skipped += 1
                continue
            kernel, cms, cached = compile_step(cfg, False, cache, st)
            rec = bench_one(cfg, spec, final_proto, env, kernel=kernel)
            rec = decorate(rec, sid, "final", -1, cms, cached, kernel_name(cfg))
            append_jsonl(results_path, rec)
            done[key] = rec
            st.measured += 1
            st.invocations += runs_of(rec)
            st.bench_wall_ms += rec["wall_ms"]
            if verbose:
                s = rec["stats_ms"]
                lines.append(f"   final {kernel_name(cfg).split('/', 1)[1]:<26} → {s['median']:8.2f} ms")

    wall_s = time.perf_counter() - t0
    run = {
        "wall_s": round(wall_s, 2),
        "measured": st.measured,
        "skipped": st.skipped,
        "slots_seen": st.slots,
        "compile_misses": st.compile_misses,
        "compile_hits": st.compile_hits,
        "compile_ms": round(st.compile_ms, 2),
        "invocations": st.invocations,
        "bench_wall_s": round(st.bench_wall_ms / 1000.0, 2),
        "budget_hit": st.budget_hit,
        "timestamp": iso_now(),
    }
    _append_summary(outdir, run)

    lines.append("")
    lines.append(f" 本段小结：新测 {st.measured} 条 / 跳过已完成 {st.skipped} 条；"
                 f"编译 {st.compile_misses} 次（缓存命中 {st.compile_hits} 次，"
                 f"Σcompile={st.compile_ms:.1f} ms）")
    lines.append(f" 本段墙钟 {wall_s:.1f} s（bench_one 的 wall 合计 {st.bench_wall_ms / 1000.0:.1f} s，"
                 f"内核调用 {st.invocations:,} 次）")
    return "\n".join(lines)


def _append_summary(outdir: str, run: dict) -> None:
    """调优运行的记账摘要：多段（断点续跑）累计保存在 runs 列表里。"""
    path = os.path.join(outdir, "tune-summary.json")
    data = {"schema": SUMMARY_SCHEMA, "runs": []}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            pass
    if "runs" not in data:
        data["runs"] = []
    data["runs"].append(run)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 表：每 shape 排名 + 死因台账


def _short(name: str) -> str:
    return name.split("/", 1)[1] if "/" in name else name


def exp_table(outdir: str = "outputs") -> str:
    records = load_records(os.path.join(outdir, "results.jsonl"))
    if not records:
        return "没有记录：先跑 --exp tune"
    lines = [BAR, " Auto-tuning v0.1 结果表：每 shape 排名（含被拒台账）", BAR]

    champs = []
    rejected = []
    for sid, M, N, K in SHAPES:
        screens = [r for r in records if r["tune"]["shape_id"] == sid
                   and r["tune"]["stage"] == "screen"]
        finals = [r for r in records if r["tune"]["shape_id"] == sid
                  and r["tune"]["stage"] == "final"]
        if not screens:
            continue
        lines.append("")
        lines.append(f" [{sid}] C=A·B+bias，{M}×{N}×{K}，seed=42："
                     f"{len(screens)} 个候选筛选 / {len(finals)} 个决赛")
        lines.append(f" {'名次':<4} {'配置':<24} {'screen':>8} {'final':>8} {'MAD':>7}"
                     f" {'spread%':>8}  gate")
        lines.append("-" * 78)
        rows = []
        for r in screens:
            if not r["correctness"]["passed"]:
                rejected.append(r)
                continue
            fin = next((f for f in finals if f["kernel"]["name"] == r["kernel"]["name"]), None)
            best = fin or r
            rows.append((best, r, fin))
        rows.sort(key=lambda t: t[0]["stats_ms"]["median"])
        fin_meds = sorted(f["stats_ms"]["median"] for f in finals)
        for rank, (best, r, fin) in enumerate(rows, 1):
            s, sf = r["stats_ms"], best["stats_ms"]
            fin_disp = f"{fin['stats_ms']['median']:>8.2f}" if fin else f"{'—':>8}"
            mark = ""
            if fin and fin_meds and sf["median"] == fin_meds[0]:
                mark = " ←冠军"
            if (r["kernel"]["tm"], r["kernel"]["tn"], r["kernel"]["tk"],
                    r["kernel"]["order"], r["kernel"]["unroll"]) == \
                    (DEFAULT_CFG.tm, DEFAULT_CFG.tn, DEFAULT_CFG.tk,
                     DEFAULT_CFG.order, DEFAULT_CFG.unroll):
                mark = " ←缺省"
            lines.append(f" {rank:<4} {_short(r['kernel']['name']):<24}"
                         f" {s['median']:>8.2f} {fin_disp}"
                         f" {sf['mad']:>7.3f} {sf['spread_pct']:>8.2f}  PASS{mark}")
        for r in screens:
            if not r["correctness"]["passed"]:
                lines.append(f" {'—':<4} {_short(r['kernel']['name']):<24} {'—':>8} {'—':>8}"
                             f" {'—':>7} {'—':>8}  REJECTED"
                             f" max_abs_err={r['correctness']['max_abs_err']:.3g}")
        if len(fin_meds) >= 2:
            gap = (fin_meds[1] - fin_meds[0]) / fin_meds[0] * 100
            lines.append(f" 决赛第 1～2 名差距 {gap:.2f}%（同进程同协议 3/21，D107 纪律）")
        if fin_meds:
            champ = next((t[2] for t in rows if t[2] and t[2]["stats_ms"]["median"] == fin_meds[0]), None)
            if champ is not None:
                champs.append((sid, f"{M}×{N}×{K}", champ["kernel"]["name"], fin_meds[0]))

    lines.append("")
    lines.append(BAR)
    lines.append(" 冠军汇总（决赛协议 3/21，中位数口径）")
    lines.append(BAR)
    for sid, shape, name, med in champs:
        lines.append(f"   {sid} {shape:<12} {_short(name):<26} {med:8.2f} ms")
    lines.append("")
    lines.append(f" 被拒台账（fail-visible，D107 门纪律在自动搜索里继续生效）：{len(rejected)} 条")
    for r in rejected:
        c = r["correctness"]
        lines.append(f"   {r['tune']['shape_id']} {_short(r['kernel']['name']):<30}"
                     f" passed={c['passed']} max_abs_err={c['max_abs_err']:.3g} → 不计时")
    lines.append("")
    lines.append(f" 记录数：{len(records)} 条 = screen"
                 f" {sum(1 for r in records if r['tune']['stage'] == 'screen')}"
                 f" + final {sum(1 for r in records if r['tune']['stage'] == 'final')}"
                 f"（schema {SCHEMA}，原始样本全在 samples_ms）")
    return "\n".join(lines)


# ---------------------------------------------------------------- 搜索成本账 + 摊销


def exp_cost(outdir: str = "outputs") -> str:
    records = load_records(os.path.join(outdir, "results.jsonl"))
    if not records:
        return "没有记录：先跑 --exp tune"
    summary = {"runs": []}
    spath = os.path.join(outdir, "tune-summary.json")
    if os.path.exists(spath):
        with open(spath, encoding="utf-8") as fh:
            summary = json.load(fh)
    runs = summary["runs"]
    total_wall = sum(r["wall_s"] for r in runs)
    invocations = sum(r["invocations"] for r in runs)
    compile_ms = sum(r["compile_ms"] for r in runs)
    compile_n = sum(r["compile_misses"] for r in runs)
    compile_hits = sum(r["compile_hits"] for r in runs)

    n_screen = sum(1 for r in records if r["tune"]["stage"] == "screen")
    n_final = sum(1 for r in records if r["tune"]["stage"] == "final")
    wall_screen = sum(r["wall_ms"] for r in records if r["tune"]["stage"] == "screen") / 1000.0
    wall_final = sum(r["wall_ms"] for r in records if r["tune"]["stage"] == "final") / 1000.0
    inv_rec = sum(runs_of(r) for r in records)

    lines = [BAR, " 搜索成本账：编译时间 / 执行时间 / 搜索成本，三种时间分开记", BAR]

    # ---- 一、总账 ----
    lines.append(" 一、总账（本次真实运行，含断点续跑各段）")
    lines.append(f"   候选槽 {n_screen} 个（筛选段）+ 决赛 {n_final} 个；"
                 f"调优分 {len(runs)} 段执行，进程墙钟合计 {total_wall:.1f} s")
    lines.append(f"   编译：{compile_n} 次 / 缓存命中 {compile_hits} 次 /"
                 f" Σcompile = {compile_ms:.1f} ms")
    lines.append("   （断点续跑的代价：编译缓存不跨进程，第二段要重新编译它新测的候选）")
    lines.append(f"   筛选段 bench Σwall = {wall_screen:.1f} s；决赛段 bench Σwall = {wall_final:.1f} s")
    lines.append(f"   内核调用：按记录逐条数 {inv_rec:,} 次（分段记账合计 {invocations:,} 次，两者应一致）")
    gap = total_wall - wall_screen - wall_final - compile_ms / 1000.0
    lines.append(f"   差额 {gap:.1f} s = 循环开销 + 报告/IO——诚实不是免费的：")
    lines.append("   参考实现每个候选都要跑一遍给门对答案，已含在 bench wall 里")
    lines.append("")

    # ---- 二、三种时间 ----
    finals = [r for r in records if r["tune"]["stage"] == "final" and r["stats_ms"]]
    lines.append(" 二、三种时间（今天的核心概念，数字全部实测）")
    avg_compile = compile_ms / max(1, compile_n)
    medians = [r["stats_ms"]["median"] for r in finals]
    lines.append(f"   编译时间：平均 {avg_compile:.2f} ms/候选（一次性；本环境是迷你 Lowering，")
    lines.append("              真实 MLIR/LLVM 管线是 0.1~10 s/候选量级，这一格会反超测量）")
    if medians:
        lines.append(f"   执行时间：决赛中位数 {min(medians):.1f}~{max(medians):.1f} ms/次"
                     f"（每次生产调用都付；排名口径）")
    lines.append(f"   搜索成本：{total_wall:.1f} s（本场一次性）= Σ编译({compile_ms:.0f} ms)"
                 f" + Σ测量({wall_screen + wall_final:.1f} s) + 记账")
    ratio = (wall_screen + wall_final) * 1000.0 / max(compile_ms, 1e-9)
    lines.append(f"   本环境 编译:测量 ≈ 1 : {ratio:,.0f}——纯 Python 里编译几乎白送；")
    lines.append(f"   换成 1 s/候选的真实后端，Σ编译 = {compile_n} s 直接反超 Σ测量："
                 f"循环结构不变，账全变")
    lines.append("")

    # ---- 三、摊销：break-even ----
    lines.append(" 三、摊销账：搜索成本什么时候回本")
    lines.append(f"   {'shape':<6} {'缺省 ms':>9} {'冠军 ms':>9} {'每次省 ms':>10}"
                 f" {'搜索成本分摊 s':>14} {'回本调用数 N':>12}")
    lines.append("-" * 78)
    n_be_all = []
    for sid, M, N, K in SHAPES:
        fin_by_name = {r["kernel"]["name"]: r for r in records
                      if r["tune"]["shape_id"] == sid and r["tune"]["stage"] == "final"}
        if not fin_by_name:
            continue
        def_name = kernel_name(DEFAULT_CFG)
        if def_name not in fin_by_name:
            continue
        champ = min(fin_by_name.values(), key=lambda r: r["stats_ms"]["median"])
        d = fin_by_name[def_name]["stats_ms"]["median"]
        w = champ["stats_ms"]["median"]
        share_ms = sum(r["wall_ms"] + r["tune"]["compile_ms"] for r in records
                      if r["tune"]["shape_id"] == sid)
        saved = d - w
        n_be = break_even(share_ms, saved)
        tag = f"{n_be:>12,.0f}" if n_be != float("inf") else "   永不回本"
        lines.append(f"   {sid:<6} {d:>9.2f} {w:>9.2f} {saved:>10.2f}"
                     f" {share_ms / 1000:>14.1f} {tag}")
        if n_be != float("inf"):
            n_be_all.append(n_be)
    lines.append("-" * 78)
    if n_be_all:
        lines.append("   N_break-even = 搜索成本分摊 ÷ 每次省下的执行时间；")
        lines.append(f"   结论：每 shape 约 {min(n_be_all):,.0f}~{max(n_be_all):,.0f} 次调用回本——")
        lines.append("   每天跑一次的脚本回不了本；推理服务百万次/天，几分钟就回本。")
        lines.append("   搜索成本是『一次性投资』，执行时间是『每次都付』——两种时间不能混。")
    lines.append("")

    # ---- 四、全空间外推（标注为估算，非实测） ----
    lines.append(" 四、把循环放大到 D106 全空间会怎样（外推估算，非实测）")
    s2_finals = [r for r in records if r["tune"]["shape_id"] == "S2"
                 and r["tune"]["stage"] == "final"]
    if s2_finals and n_screen:
        s2_champ_ms = min(r["stats_ms"]["median"] for r in s2_finals)
        per_run_512_s = s2_champ_ms * (512 ** 3) / (96 ** 3) / 1000.0
        est_days = 12970 * (1 + 3 + 7) * per_run_512_s / 86400.0
        lines.append(f"   本场筛选段 {n_screen} 个候选花 {wall_screen:.1f} s（小 shape、纯 Python）")
        lines.append(f"   D106 的 12,970 个候选是为 512³ 生成的：96³ 冠军 {s2_champ_ms:.0f} ms"
                     f" × (512/96)³ ≈ {per_run_512_s:.1f} s/次（量级估算）")
        lines.append(f"   全空间按 v0.1 筛选协议 ≈ 12,970×11×{per_run_512_s:.1f} s ≈ {est_days:.0f} 天——")
        lines.append("   而且这是下界：tile 外壳和慢顺序让多数候选更慢。")
        lines.append("   这就是为什么真实调优器必须有 cost model 预剪（D110）和分层搜索：")
        lines.append("   循环本身今天已经立起来了，『测得起』是另一门功课（D106 的老警告）。")
    return "\n".join(lines)


# ---------------------------------------------------------------- 换口径不重跑：重复次数稳定性


def exp_stability(outdir: str = "outputs") -> str:
    """对照实验：把筛选样本从 7 砍到 3/5，排名稳不稳？（读 samples_ms 重算，不重跑内核）"""
    records = load_records(os.path.join(outdir, "results.jsonl"))
    if not records:
        return "没有记录：先跑 --exp tune"
    from statistics import median as _med

    lines = [BAR, " 筛选重复次数扫描：k=3/5 vs k=7（同一批落盘样本重算，内核一次不跑）", BAR,
             " 问题：筛选段 repeats=7 买保险；砍到 3 能省多少搜索成本、排名付出什么代价？", ""]
    for sid, M, N, K in SHAPES:
        screens = [r for r in records if r["tune"]["shape_id"] == sid
                   and r["tune"]["stage"] == "screen" and r["correctness"]["passed"]]
        if not screens:
            continue
        lines.append(f" [{sid}] {M}×{N}×{K}（{len(screens)} 个过门候选）")
        rank7 = {r["kernel"]["name"]: r["stats_ms"]["median"] for r in screens}
        order7 = sorted(rank7, key=rank7.get)
        pos7 = {n: i for i, n in enumerate(order7)}
        for k in (3, 5):
            medk = {r["kernel"]["name"]: _med(r["samples_ms"][:k]) for r in screens}
            orderk = sorted(medk, key=medk.get)
            shifts = [abs(orderk.index(n) - pos7[n]) for n in order7]
            top3_7, top3_k = set(order7[:3]), set(orderk[:3])
            cost_pct = (11 - (4 + k)) / 11 * 100
            same_top = "不变" if top3_7 == top3_k else f"变了（{len(top3_k - top3_7)} 个换人）"
            same_champ = "不变" if orderk[0] == order7[0] else "翻车：" + _short(orderk[0])
            lines.append(f"   k={k}：名次摆动最大 {max(shifts)} 位；top-3 名单{same_top}；"
                         f"冠军{same_champ}；筛选段成本省 {cost_pct:.0f}%")
        lines.append("")
    lines.append(" 读法：名次摆动出现在中游（中位数差距小于噪声的邻居互换）；")
    lines.append(" top-3 和冠军稳定 → 两段式『筛选粗、决赛精』成立：省下的是 90+ 个")
    lines.append(" 注定进不了决赛的候选的重复次数。D107 的『样本落盘』让本实验零成本。")
    return "\n".join(lines)


# ---------------------------------------------------------------- 自检


def self_test() -> str:
    import tempfile

    results = []

    def assert_eq(name, got, want):
        results.append((name, got == want, f"got {got!r}, want {want!r}"))

    def assert_true(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    # ---- 空间：每 shape 的候选数、去重、投毒、缺省在场 ----
    s1 = build_space("S1", 64, 64, 64)
    s2 = build_space("S2", 96, 96, 96)
    s3 = build_space("S3", 90, 96, 64)
    assert_eq("S1 空间 = 2 tile×6×2", len(s1), 24)
    assert_eq("S2 空间 = 3 tile×6×2", len(s2), 36)
    assert_eq("S3 空间 = 3 tile×6×2 + 2 投毒", len(s3), 38)
    assert_true("S3 含 2 个投毒探针", sum(1 for _, p in s3 if p) == 2)
    assert_true("投毒都以内层 i 收尾（尾部必现）",
                all(cfg.order[-1] == "i" for cfg, p in s3 if p))
    assert_true("缺省 32³ ijk U=1 在每个 shape 空间里",
                all(any(cfg == DEFAULT_CFG and not p for cfg, p in sp) for sp in (s1, s2, s3)))
    assert_eq("S1 单 tile 与 64 cube 去重（6×2=12 个）",
              len([1 for cfg, _ in s1 if (cfg.tm, cfg.tn, cfg.tk) == (64, 64, 64)]), 12)

    # ---- 协议 ----
    assert_eq("筛选协议 3+7", (SCREEN_PROTO.warmup, SCREEN_PROTO.repeats), (3, 7))
    assert_eq("决赛协议 3+21（D107 血统）", (FINAL_PROTO.warmup, FINAL_PROTO.repeats), (3, 21))

    # ---- 记录口径 ----
    assert_eq("schema 升为 d108", SCHEMA, "d108.tune-result/1")
    fake = {"tune": {"shape_id": "S1", "stage": "screen"},
            "kernel": {"name": "tiled-matmul/32³ ijk U=1"}}
    assert_eq("key_of 三元组", key_of(fake), ("S1", "tiled-matmul/32³ ijk U=1", "screen"))
    assert_eq("过门记录烧 1+3+7 次调用",
              runs_of({"correctness": {"passed": True},
                       "protocol": {"warmup": 3, "repeats": 7}}), 11)
    assert_eq("被拒记录只烧门 1 次",
              runs_of({"correctness": {"passed": False},
                       "protocol": {"warmup": 3, "repeats": 7}}), 1)
    assert_eq("kernel_name 带投毒后缀", kernel_name(DEFAULT_CFG, True),
              "tiled-matmul/32³ ijk U=1/no-tail")

    # ---- 编译缓存 ----
    st = RunStats()
    cache = {}
    k1, cms, cached = compile_step(DEFAULT_CFG, False, cache, st)
    k2, cms2, cached2 = compile_step(DEFAULT_CFG, False, cache, st)
    assert_true("第一次编译是 miss", not cached and cms > 0)
    assert_true("第二次命中缓存（0 ms）", cached2 and cms2 == 0.0)
    assert_true("命中同一个内核对象", k1 is k2)
    assert_eq("记账：1 miss + 1 hit", (st.compile_misses, st.compile_hits), (1, 1))
    twin_cfg = KernelConfig(90, 96, 64, "jki", 4)   # 真实投毒 cfg 的正确双胞胎
    compile_step(twin_cfg, True, cache, RunStats())
    assert_true("投毒键与正确双胞胎分开",
                (twin_cfg, True) in cache and (twin_cfg, False) not in cache)

    # ---- 摊销公式 ----
    assert_eq("N_be = 成本 ÷ 每次省时", break_even(30000.0, 12.0), 2500.0)
    assert_true("省不出时间 → 永不回本", break_even(30000.0, 0.0) == float("inf"))

    # ---- 微型端到端：小 shape + 投毒，走完整循环（含断点续跑） ----
    with tempfile.TemporaryDirectory() as td:
        tiny_shapes = (("T", 10, 10, 10),)
        tiny_poison = (("T", KernelConfig(10, 10, 10, "jki", 4), "no-tail"),)
        tune_run(td, screen_repeats=3, n_finalists=1,
                 shapes=tiny_shapes, poisons=tiny_poison, verbose=False)
        recs = load_records(os.path.join(td, "results.jsonl"))
        n_screen = sum(1 for r in recs if r["tune"]["stage"] == "screen")
        n_final = sum(1 for r in recs if r["tune"]["stage"] == "final")
        assert_eq("微型空间 6×2+1投毒 = 13 候选", n_screen, 13)
        assert_eq("决赛 top-1 恰好 1 条", n_final, 1)
        poisons_r = [r for r in recs if "/no-tail" in r["kernel"]["name"]]
        assert_eq("投毒 1 条记录", len(poisons_r), 1)
        assert_true("投毒被拒且不计时",
                    poisons_r[0]["correctness"]["passed"] is False
                    and poisons_r[0]["stats_ms"] is None)
        assert_true("投毒 max_abs_err 量级正确（尾部 2 圈没算）",
                    poisons_r[0]["correctness"]["max_abs_err"] > 0.1)
        passed = [r for r in recs if r["tune"]["stage"] == "screen"
                  and r["correctness"]["passed"]]
        assert_true("12 个正确候选全部过门", len(passed) == 12)
        champ = min((r for r in recs if r["tune"]["stage"] == "final"),
                    key=lambda r: r["stats_ms"]["median"])
        assert_true("冠军记录带 tune 章", champ["tune"]["stage"] == "final")
        assert_true("冠军记录 schema=d108", champ["schema"] == SCHEMA)
        assert_true("记录自带 env+protocol（D107 自包含遗产）",
                    "python" in champ["env"] and champ["protocol"]["repeats"] == 21)

        out2 = tune_run(td, screen_repeats=3, n_finalists=1,
                        shapes=tiny_shapes, poisons=tiny_poison, verbose=False)
        recs2 = load_records(os.path.join(td, "results.jsonl"))
        assert_eq("重跑后记录数不变（断点续跑全跳过）", len(recs2), len(recs))
        assert_true("重跑报告写明跳过", "跳过已完成" in out2)

    # ---- 搜索成本外推公式（与 exp_cost 第四节同一算式） ----
    est = 12970 * 11 * 7.5 / 86400.0
    assert_true("全空间外推 ≈ 12 天量级（12.4 附近）", 12.0 < est < 13.0)

    n_pass = sum(1 for _, ok, _ in results if ok)
    lines = [BAR, f" 自检：{n_pass}/{len(results)} 项断言通过", BAR]
    for name, ok, detail in results:
        lines.append(("  ✓ " if ok else "  ✗ ") + name + ("" if ok else f"  ——  {detail}"))
    text = "\n".join(lines)
    if n_pass != len(results):
        print(text)
        raise SystemExit("自检失败")
    return text


# ---------------------------------------------------------------- CLI


EXPS = ("tune", "table", "cost", "stability", "self-test", "env")


def env_block() -> str:
    e = capture_env()
    return "\n".join([
        f"环境：Python {e['python']}（{e['implementation']}），{e['system']}/{e['machine']}，"
        f"{e['cpu_count']} 逻辑核",
        f"CPU：{e['cpu_model']}",
        f"时钟：{e['clock']}（分辨率 {e['clock_res_us']} µs）",
        "依赖：kernel_gen.py / bench.py 逐字复用 D107（测量协议与内核工厂血统不变）",
        "筛选协议：warmup=3、repeats=7（D107 前缀扫描：k≥7 最坏摆 0.11%）",
        "决赛协议：warmup=3、repeats=21（D107 全协议）",
        f"记录格式：{SCHEMA}（= d107.bench-result/1 字段 + tune 块：shape_id/stage/compile_ms）",
        f"运行日期：{iso_now()}",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="D108 Auto-tuning v0.1")
    ap.add_argument("--exp", default="all", help="tune/table/cost/stability/self-test/env")
    ap.add_argument("--outdir", default="outputs")
    ap.add_argument("--limit", type=int, default=None,
                    help="tune：新测量满 N 条收工（断点续跑演示）")
    ap.add_argument("--screen-repeats", type=int, default=7)
    ap.add_argument("--finalists", type=int, default=3)
    args = ap.parse_args()

    if args.exp == "all":
        print("请用 ./run_all.sh（按 self-test → resume-demo → tune → table → cost 顺序执行）")
        return 2
    if args.exp == "tune":
        print(tune_run(args.outdir, limit=args.limit,
                       screen_repeats=args.screen_repeats, n_finalists=args.finalists))
        return 0
    if args.exp == "table":
        print(exp_table(args.outdir))
        return 0
    if args.exp == "cost":
        print(exp_cost(args.outdir))
        return 0
    if args.exp == "stability":
        print(exp_stability(args.outdir))
        return 0
    if args.exp == "self-test":
        print(self_test())
        return 0
    if args.exp == "env":
        print(env_block())
        return 0
    print(f"未知实验：{args.exp!r}（可选 {'/'.join(EXPS)}）", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
