#!/usr/bin/env python3
"""D107 统一 Benchmark 工具：一个入口、一套协议、一种结果格式。

昨天（D106）的 12,970 个幸存者排队等计时协议；D97 已经把"怎么测才诚实"
趟过一遍——但那是一次性实验脚本：协议写死在 main 里、结果只有文本表、
环境记录单独躺在 env.txt 里，换一个配置就得再手搓一遍。今天把它立成工具：

    统一入口   bench_one(cfg, spec, protocol) → 一条记录（dict）
    固定输入   spec.seed 决定 A/B/bias——同一 spec 永远同一份数据
    正确性门   先于一切计时（D97 错误三：错误版本往往更快，不配进表）
    固定协议   warmup=3、repeats=21、perf_counter、中位数口径（D97 遗产）
    环境随行   每条记录自带 env 快照——记录离开 outputs/ 也不会失去户口
    结果格式   JSONL：schema 版本号 + 原始样本全部落盘，统计可换口径重算

统计口径（今天的学习目标）：
    预热 warmup      丢弃冷启动成本（缺页/首次调用/分配器冷态）
    重复 repeats     性能是随机变量，单次样本不是答案（D97：4/6 排名翻车）
    中位数 median    对离群值稳健——"典型一次有多快"
    均值 mean        对总量估算正确——"整晚 auto-tuning 要跑多久"用它
    异常值 outliers  MAD 修正 z 分数（|x−median| > 3.5×1.4826×MAD）；
                     只标记、只计数，不悄悄删除——离群值是数据，不是污点

分工边界（D74/D106 的分离原则继续生效）：本工具只测量、只记录；
排序给 D110 的 cost model，搜索给 D108 的 auto-tuning，GFLOPS 给 D109。
"""

from __future__ import annotations

import argparse
import dataclasses
import gc as _gc
import itertools
import json
import os
import platform
import sys
import time
from statistics import mean as _mean
from statistics import median as _median
from statistics import stdev as _stdev

from kernel_gen import KernelConfig, alloc_c, make_inputs, make_kernel, max_abs_err, ref_matmul

BAR = "=" * 78
SCHEMA = "d107.bench-result/1"          # 格式版本号：将来改字段先改它，不静默破坏
MAD_K = 3.5 * 1.4826                    # 修正 z 分数阈值（Iglewicz–Hoaglin）


# ---------------------------------------------------------------- 统计（纯函数，可断言）


def median(xs: list) -> float:
    return _median(xs)


def mad(xs: list) -> float:
    """MAD = median(|x − median|)——离群值也拉不动的波动度量。"""
    m = median(xs)
    return _median([abs(x - m) for x in xs])


def outlier_indices(xs: list) -> list:
    """MAD 修正 z 分数：|x − median| > 3.5 × 1.4826 × MAD 记为离群。

    MAD = 0（样本全等）时规则退化，只返回空表并在表里看 spread——
    这是已知行为，不是漏报。
    """
    m = median(xs)
    d = mad(xs)
    if d == 0:
        return []
    return [i for i, x in enumerate(xs) if abs(x - m) > MAD_K * d]


def trimmed_mean(xs: list, pct: float = 10.0) -> float:
    """两端各去 pct% 后取均值——均值和_median之间的折中口径。"""
    ys = sorted(xs)
    k = int(len(ys) * pct / 100.0)
    ys = ys[k:len(ys) - k] if k else ys
    return _mean(ys)


def summarize_ms(xs: list) -> dict:
    med = median(xs)
    mu = _mean(xs)
    m = mad(xs)
    spread = (max(xs) - min(xs)) / med * 100 if med else 0.0
    out = outlier_indices(xs)
    cv = _stdev(xs) / mu * 100 if mu else 0.0
    return {
        "n": len(xs),
        "median": round(med, 3),
        "mean": round(mu, 3),
        "trimmed_mean": round(trimmed_mean(xs), 3),
        "min": round(min(xs), 3),
        "max": round(max(xs), 3),
        "mad": round(m, 3),
        "spread_pct": round(spread, 2),
        "cv_pct": round(cv, 2),
        "outliers": len(out),
        "outlier_idx": out,
        "mean_minus_median_pct": round((mu - med) / med * 100, 2),
    }


def median_of_prefix(xs: list, k: int) -> float:
    """前 k 个样本的中位数——重复次数扫描实验的零件。"""
    return median(xs[:k])


# ---------------------------------------------------------------- 环境快照（随每条记录走）


def capture_env() -> dict:
    """机器/解释器/时钟快照。不收主机名、不收用户名——性能要户口，不要隐私。"""
    cpu_model = ""
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="ignore") as fh:
            for ln in fh:
                if ln.startswith("model name") or ln.startswith("Processor"):
                    cpu_model = ln.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_model": cpu_model or "n/a",
        "clock": "time.perf_counter",
        "clock_res_us": round(time.get_clock_info("perf_counter").resolution * 1e6, 3),
    }


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------------------------------------------------------------- 协议与负载身份


@dataclasses.dataclass(frozen=True)
class BenchSpec:
    """被测负载的身份：换 shape/seed 就是换了被测对象（控制变量）。"""

    M: int = 96
    N: int = 96
    K: int = 96
    seed: int = 42
    op: str = "matmul_bias"

    def flops_nominal(self) -> int:
        return 2 * self.M * self.N * self.K      # 每 MAC 记 2 FLOP，全表统一口径

    def describe(self) -> str:
        return f"{self.op} {self.M}×{self.N}×{self.K} seed={self.seed}"


@dataclasses.dataclass(frozen=True)
class Protocol:
    """测量协议：所有候选共用同一份，改协议 = 换了一把尺子。

    warmup/repeats 沿用 D97 的 3/21；gc_enabled 是两种合法口径的开关——
    False=排除口径（内核自己的时间），True=包含口径（解释器后台工作
    也算被测时间）。选哪种取决于要回答什么问题，但必须写进记录。
    """

    warmup: int = 3
    repeats: int = 21
    clock: str = "perf_counter"
    gc_enabled: bool = False
    policy: str = "bitwise"               # bitwise / tolerance
    tol: float = 1e-9

    def describe(self) -> str:
        return (f"warmup={self.warmup} repeats={self.repeats} clock={self.clock} "
                f"gc={'on' if self.gc_enabled else 'off'} policy={self.policy}")


@dataclasses.dataclass
class BenchResult:
    """一次统一入口调用的全部产出。被拒配置也有记录：失败要留痕，不要静默。"""

    cfg: KernelConfig
    spec: BenchSpec
    protocol: Protocol
    passed: bool
    max_abs_err: float
    samples_ms: list | None
    stats: dict | None
    wall_ms: float = 0.0                  # 整次调用墙钟（门+预热+计时），元信息
    timestamp: str = ""

    @property
    def rejected(self) -> bool:
        return not self.passed


def bench_one(cfg: KernelConfig, spec: BenchSpec | None = None,
              protocol: Protocol | None = None, env: dict | None = None,
              kernel=None) -> dict:
    """统一 Benchmark 入口：给一个配置，还一条自包含记录（dict/JSONL 行）。

    门 → 预热 → 计时 → 统计。kernel 参数允许传入预构建的内核
    （比如故意做坏的 no-tail 版）——坏内核也要走同一个门，被拒的配置
    返回 correctness.passed=false、stats=null 的记录——D108 的 auto-tuning
    需要知道谁死在了门上、为什么。
    """
    spec = spec or BenchSpec()
    protocol = protocol or Protocol()
    env = env or capture_env()
    t_all = time.perf_counter()

    kernel = kernel if kernel is not None else make_kernel(cfg)

    # ① 固定输入：同一 spec 永远同一份 A/B/bias
    A, B, bias = make_inputs(spec.M, spec.N, spec.K, spec.seed)
    C0 = alloc_c(bias, spec.M, spec.N)
    Cref = ref_matmul(A, B, bias, spec.M, spec.N, spec.K)

    # ② 正确性门：先于一切计时。不正确就没有参赛资格（D97 错误三）
    C = [row[:] for row in C0]
    kernel(A, B, C, spec.M, spec.N, spec.K)
    err = max_abs_err(C, Cref)
    if protocol.policy == "bitwise":
        passed = C == Cref
    else:
        passed = err <= protocol.tol

    samples = None
    stats = None
    if passed:
        # ③ 预热：把冷启动成本烧掉，全部丢弃，不计分
        gc_state = _gc.isenabled()
        if not protocol.gc_enabled:
            _gc.disable()
        try:
            for _ in range(protocol.warmup):
                C = [row[:] for row in C0]
                kernel(A, B, C, spec.M, spec.N, spec.K)

            # ④ 计时：每个样本从同一初始状态出发，时钟只包住内核
            samples = []
            for _ in range(protocol.repeats):
                C = [row[:] for row in C0]
                t0 = time.perf_counter()
                kernel(A, B, C, spec.M, spec.N, spec.K)
                t1 = time.perf_counter()
                samples.append((t1 - t0) * 1000.0)
            stats = summarize_ms(samples)
        finally:
            if not protocol.gc_enabled and gc_state:
                _gc.enable()

    wall_ms = (time.perf_counter() - t_all) * 1000.0
    return record_from(BenchResult(cfg=cfg, spec=spec, protocol=protocol, passed=passed,
                                   max_abs_err=err, samples_ms=samples, stats=stats,
                                   wall_ms=wall_ms, timestamp=iso_now()), env)


def record_from(res: BenchResult, env: dict) -> dict:
    """BenchResult → JSONL 行（dict）。字段分层：身份/环境/协议/门/统计/样本。"""
    return {
        "schema": SCHEMA,
        "kernel": {
            "name": f"tiled-matmul/{res.cfg.describe()}",
            "tm": res.cfg.tm, "tn": res.cfg.tn, "tk": res.cfg.tk,
            "order": res.cfg.order, "unroll": res.cfg.unroll,
        },
        "workload": {
            "op": res.spec.op, "M": res.spec.M, "N": res.spec.N, "K": res.spec.K,
            "seed": res.spec.seed, "flops_nominal": res.spec.flops_nominal(),
        },
        "env": env,
        "protocol": {
            "warmup": res.protocol.warmup, "repeats": res.protocol.repeats,
            "clock": res.protocol.clock,
            "gc": "on" if res.protocol.gc_enabled else "off",
            "policy": res.protocol.policy, "tol": res.protocol.tol,
        },
        "correctness": {"passed": res.passed, "max_abs_err": res.max_abs_err,
                        "rejected": res.rejected},
        "stats_ms": res.stats,
        "samples_ms": ([round(x, 3) for x in res.samples_ms] if res.samples_ms else None),
        "wall_ms": round(res.wall_ms, 1),
        "timestamp": res.timestamp,
    }


def write_jsonl(path: str, records: list) -> None:
    """一行一条记录追加式落盘——D108 的 auto-tuning 边测边写就用它。"""
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- 人类可读的表


def render_table(records: list) -> str:
    """性能表：中位数是成绩单；差距小于波动的行不许宣布排名（D97 规则）。"""
    ok = [r for r in records if r["correctness"]["passed"]]
    rej = [r for r in records if not r["correctness"]["passed"]]
    lines = [BAR, " 统一 Benchmark 表（中位数口径，单位 ms）", BAR,
             f" {'config':<20} {'median':>9} {'mean':>9} {'trimmed':>9} {'min':>8}"
             f" {'MAD':>7} {'spread%':>8} {'outl':>5} {'mean−med%':>10}  gate",
             "-" * 78]
    rows = sorted(ok, key=lambda r: r["stats_ms"]["median"])
    best = rows[0] if rows else None
    for r in rows:
        s = r["stats_ms"]
        name = r["kernel"]["name"].split("/", 1)[1]
        mark = " ←BEST" if r is best else ""
        lines.append(f" {name:<20} {s['median']:>9.2f} {s['mean']:>9.2f}"
                     f" {s['trimmed_mean']:>9.2f} {s['min']:>8.2f} {s['mad']:>7.3f}"
                     f" {s['spread_pct']:>8.2f} {s['outliers']:>5}"
                     f" {s['mean_minus_median_pct']:>10.2f}  PASS{mark}")
    if len(rows) > 1:
        s1, s2 = rows[0]["stats_ms"], rows[1]["stats_ms"]
        gap = (s2["median"] - s1["median"]) / s1["median"] * 100
        noise = max(s1["mad"], s2["mad"]) / s1["median"] * 100
        verdict = ("成立" if gap > 2 * noise else
                   "在波动内，无法区分（加样本或如实写并列）")
        lines.append(f" 第 1～2 名差距 {gap:.2f}% vs 2×MAD 口径 {2 * noise:.2f}%"
                     f" → 结论：{verdict}")
    for r in rej:
        c = r["correctness"]
        lines.append(f" {r['kernel']['name'].split('/', 1)[1]:<20}"
                     f" {'—':>9} {'—':>9} {'—':>9} {'—':>8} {'—':>7} {'—':>8} {'—':>5}"
                     f" {'—':>10}  REJECTED max_abs_err={c['max_abs_err']:.3g}")
    lines.append(f" 协议：{records[0]['protocol'] if records else ''}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 实验


def exp_table(outdir: str | None = None, warmup: int = 3, repeats: int = 21) -> str:
    """主实验：7 个真实配置过统一入口，出表 + JSONL + 样本 CSV。"""
    spec = BenchSpec()
    proto = Protocol(warmup=warmup, repeats=repeats)
    env = capture_env()
    cfgs = [
        KernelConfig(32, 32, 32, "ijk", 1),     # k 最内层：B 跨步访问（D97 baseline 同构）
        KernelConfig(32, 32, 32, "ikj", 1),     # j 最内层：行访问（D96 reorder 同构）
        KernelConfig(32, 32, 32, "kij", 1),      # k 最外层的行访问变体
        KernelConfig(32, 32, 32, "jik", 1),      # k 中层的行访问变体
        KernelConfig(32, 32, 32, "jki", 1),      # i 最内层：C/A 双跨步（预期最惨）
        KernelConfig(32, 32, 32, "ikj", 8),      # U=8：展开在 CPython 里的真实下场
        KernelConfig(96, 96, 96, "ikj", 1),      # 单 tile：tile 外壳开销对照
    ]
    records = [bench_one(cfg, spec, proto, env) for cfg in cfgs]
    lines = [BAR, " 实验一（主交付物）：7 个配置过统一入口", BAR,
             f" 负载 {spec.describe()}    flops_nominal={spec.flops_nominal():,}",
             f" 协议 {proto.describe()}", ""]
    lines.append(render_table(records))
    lines.append("")
    lines.append(" 读法：median=典型一次；mean=被离群值拖动后的一次；trimmed=去两端后的均值；")
    lines.append(" outl=MAD 离群样本数；mean−med%>0 说明慢尾在拉均值（性能样本天然左偏）。")
    if outdir:
        write_jsonl(os.path.join(outdir, "results.jsonl"), records)
        with open(os.path.join(outdir, "samples.csv"), "w", encoding="utf-8") as fh:
            fh.write("config,sample_idx,ms\n")
            for r in records:
                name = r["kernel"]["name"].split("/", 1)[1].replace(" ", "_")
                if r["samples_ms"]:
                    for i, x in enumerate(r["samples_ms"]):
                        fh.write(f"{name},{i},{x}\n")
    return "\n".join(lines)


def exp_outliers(outdir: str | None = None) -> str:
    """长跑实验：201 个样本，看离群值长什么样、均值被拖多远、样本要几个。

    gc 用包含口径（gc_enabled=True）：让解释器自己的后台回收有机会
    落进计时窗——这是真实负载里最常见的『外部干扰』来源之一，不是
    人工噪声：门开低一点，让真实干扰进来，看统计口径怎么接住它。
    """
    spec = BenchSpec()
    proto = Protocol(warmup=3, repeats=201, gc_enabled=True)
    rec = bench_one(KernelConfig(32, 32, 32, "ikj", 1), spec, proto)
    s = rec["stats_ms"]
    xs = rec["samples_ms"]
    med, mu = s["median"], s["mean"]

    lines = [BAR, " 实验二：长跑 201 样本——离群值、均值、重复次数", BAR,
             f" 负载 {spec.describe()}    协议 {proto.describe()}",
             f" 口径说明：gc=on（包含口径）——解释器后台工作落在被测时间里", ""]

    lines.append(" ① 离群值（MAD 修正 z 分数：|x−median| > 3.5×1.4826×MAD）")
    idxs = s["outlier_idx"]
    if not idxs:
        lines.append("   本次运行 0 个 MAD 离群——机器安静，规则没失效；")
        lines.append("   离群规则的价值在干扰真的来时（共享机器/后台任务），不在每次都开张。")
    else:
        imax = max(idxs, key=lambda i: abs(xs[i] - med))
        d_mad = MAD_K * s["mad"]
        lines.append(f"   阈值 = 3.5×1.4826×MAD = {d_mad:.2f} ms（MAD 只有 {s['mad']:.2f}："
                     f"分布主体极稳时阈值自动收紧，规则变敏感）")
        lines.append(f"   共 {len(idxs)} 个离群样本，最大者 #{imax}: {xs[imax]:.2f} ms"
                     f"（{(xs[imax] - med) / med * 100:+.2f}%）")
        if len(idxs) > 1:
            runs, cur = [], [idxs[0]]
            for i in idxs[1:]:
                if i == cur[-1] + 1:
                    cur.append(i)
                else:
                    runs.append(cur)
                    cur = [i]
            runs.append(cur)
            lines.append(f"   {len(idxs)} 个离群聚成 {len(runs)} 个连续短串（最长的 {max(len(r) for r in runs)}"
                         f" 个样本）——离群在时间上成串出现：")
            lines.append("   一次机器忙碌/后台回收让相邻几个样本一起变慢，不是一个个独立噪声。")
        shown = "   " + "  ".join(f"#{i}:{(xs[i] - med) / med * 100:+.2f}%" for i in idxs[:8])
        lines.append(shown + ("  …（其余见 outliers-samples.json）" if len(idxs) > 8 else ""))
    lines.append("")
    lines.append(" ② 三个统计口径在同一批样本上的分歧")
    lines.append(f"   median        {med:8.2f} ms   ← 典型一次（离群值拉不动）")
    lines.append(f"   mean          {mu:8.2f} ms   ← 被慢尾拖着走（搜索总时长估算用）")
    lines.append(f"   trimmed_mean  {s['trimmed_mean']:8.2f} ms   ← 两端各去 10% 的折中")
    lines.append(f"   mean − median = {s['mean_minus_median_pct']:+.2f}%   spread {s['spread_pct']:.1f}%"
                 f"   MAD {s['mad']:.2f}   CV {s['cv_pct']:.1f}%")
    if idxs:
        maxdev = max((xs[i] - med) / med * 100 for i in idxs)
        lines.append(f"   {len(idxs)}/{len(xs)} 个离群也只把均值拖了 {s['mean_minus_median_pct']:+.2f}%："
                     f"最大离群 {maxdev:+.1f}% 被 {len(xs)} 个样本稀释。")
        lines.append(f"   均值的脆弱度 ∝ 离群幅度 ÷ 样本数——repeats=3 时同一个 {maxdev:+.1f}% 的离群")
        lines.append(f"   能把均值拖走约 +{maxdev / 3:.1f}%；中位数对哪种样本量都免疫。样本少，更要中位数。")
    else:
        lines.append("   本轮 0 离群、机器安静：mean≈median 不是『均值很稳』的证据，")
        lines.append("   只是离群还没来——均值脆弱性是概率性的，忙日子会咬人。")
    lines.append("")

    lines.append(" ③ 重复次数扫描：前 k 个样本的中位数 vs 全体中位数（同一样本集换口径，不用重跑）")
    lines.append(f"   {'k':>5} {'median_of_k':>12} {'drift%':>8} {'成本(k×单次)':>14}")
    full = median(xs)
    ks = (1, 3, 5, 7, 11, 21, 31, 51, 101, 201)
    drifts = {}
    for k in ks:
        mk = median_of_prefix(xs, k)
        drifts[k] = (mk - full) / full * 100
        lines.append(f"   {k:>5} {mk:>12.2f} {drifts[k]:>+8.2f}"
                     f" {k * med / 1000:>13.1f}s")
    worst_early = max(abs(drifts[k]) for k in ks if k <= 7)
    worst_late = max(abs(drifts[k]) for k in ks if k >= 21)
    lines.append(f"   本轮读数：k≤7 的口径最坏摆 {worst_early:.2f}%，k≥21 后最坏 {worst_late:.2f}%。")
    if abs(drifts[1]) >= 1.0:
        lines.append(f"   k=1 偏了 {drifts[1]:+.2f}%——单样本口径的翻车现场"
                     "（D97 的 4/6 排名翻车是忙时段版）。")
    else:
        lines.append(f"   k=1 只偏 {drifts[1]:+.2f}% 是运气——本轮 spread {s['spread_pct']:.1f}%、"
                     f"离群 {len(idxs)} 个，")
        lines.append("   单样本落在离群段就是另一副长相（D97 的 4/6 排名翻车是忙时段证据）。")
    lines.append("   repeats=21 买的是对忙时段的保险；收敛之后的样本只花时间，不再买保险。")
    if outdir:
        with open(os.path.join(outdir, "outliers-samples.json"), "w", encoding="utf-8") as fh:
            json.dump({"samples_ms": xs, "stats": s}, fh, ensure_ascii=False, indent=1)
    return "\n".join(lines)


def exp_gc(outdir: str | None = None) -> str:
    """口径对照：同一个内核，gc 关（排除口径）vs 开（包含口径）。

    两种口径都合法，回答的问题不同：排除口径量『内核自己的成本』，
    包含口径量『用户真实等待的时间』。它们差多少，只能测，不能猜。
    """
    spec = BenchSpec()
    env = capture_env()
    cfg = KernelConfig(32, 32, 32, "ikj", 1)
    rec_off = bench_one(cfg, spec, Protocol(gc_enabled=False), env)
    rec_on = bench_one(cfg, spec, Protocol(gc_enabled=True), env)
    so, sn = rec_off["stats_ms"], rec_on["stats_ms"]
    lines = [BAR, " 实验三：口径对照——计时窗内 gc 关 vs 开", BAR,
             f" 负载 {spec.describe()}    配置 {cfg.describe()}",
             "",
             f" {'口径':<10} {'median':>9} {'mean':>9} {'MAD':>7} {'spread%':>8} {'outl':>5} {'mean−med%':>10}",
             "-" * 78]
    for tag, s in (("gc=off", so), ("gc=on", sn)):
        lines.append(f" {tag:<10} {s['median']:>9.2f} {s['mean']:>9.2f} {s['mad']:>7.3f}"
                     f" {s['spread_pct']:>8.2f} {s['outliers']:>5} {s['mean_minus_median_pct']:>10.2f}")
    d = (sn["median"] - so["median"]) / so["median"] * 100
    lines.append("-" * 78)
    lines.append(f" 中位数差 {d:+.2f}%——读数就是读数：工具负责量出差别并写进 protocol.gc，")
    lines.append(" 选哪种口径由『要回答什么问题』决定，而不是哪种数字好看。")
    if outdir:
        write_jsonl(os.path.join(outdir, "gc-records.jsonl"), [rec_off, rec_on])
    return "\n".join(lines)


def exp_gate(outdir: str | None = None) -> str:
    """正确性门套件：小奇数 shape × 6 顺序 × 3 展开全 PASS；no-tail 内核被拒。"""
    env = capture_env()
    proto = Protocol()
    lines = [BAR, " 实验四：正确性门——先于一切计时", BAR,
             " 门是逐位相等（==，不是阈值）：所有排列/tile/展开下每个 C[i][j] 都按 k 升序",
             " 做同一串 IEEE 双精度加法——累加序列逐位相同（D97 的 -ffp-contract=off 论据）。", ""]
    shapes = [(5, 7, 3), (13, 17, 19), (31, 29, 23)]
    records = []
    n_pass = 0
    for (M, N, K) in shapes:
        spec = BenchSpec(M=M, N=N, K=K)
        row = []
        for order in itertools.permutations("ijk"):
            for U in (1, 4, 8):
                rec = bench_one(KernelConfig(32, 32, 32, "".join(order), U), spec, proto, env)
                records.append(rec)
                n_pass += 1 if rec["correctness"]["passed"] else 0
                row.append("✓" if rec["correctness"]["passed"] else "✗")
        lines.append(f" shape {M:>3}×{N:>3}×{K:>3}: 18/18 {''.join(row)} 全 PASS"
                     if all(r["correctness"]["passed"] for r in records[-18:])
                     else f" shape {M:>3}×{N:>3}×{K:>3}: 有 FAIL")
    lines.append(f" 门成绩：{n_pass}/54 逐位相等")

    lines.append("")
    lines.append(" 靶子：no-tail 内核（尾部循环整段不生成——D96『跑得飞快、结果全错』的 Python 版）")
    spec = BenchSpec(13, 17, 19)
    bad_cfg = KernelConfig(32, 32, 32, "ikj", 4)
    rec = bench_one(bad_cfg, spec, proto, env, kernel=make_kernel(bad_cfg, drop_tail=True))
    c = rec["correctness"]
    lines.append(f"   {rec['kernel']['name']}: passed={c['passed']} max_abs_err={c['max_abs_err']:.3g}")
    assert rec["stats_ms"] is None and rec["samples_ms"] is None
    lines.append("   stats=None、samples=None——被拒配置不计时：错误版本往往更快，快也不许进表")
    lines.append("   被拒照样产记录（fail-visible）：D108 的搜索要把『谁死在门上、为什么』记下来")
    records.append(rec)
    if outdir:
        write_jsonl(os.path.join(outdir, "gate-records.jsonl"), records)
    return "\n".join(lines)


def exp_show_src(outdir: str | None = None) -> str:
    """把一个配置生成的真实源码落盘——统一入口测的不是黑盒。"""
    from kernel_gen import kernel_source
    cfg = KernelConfig(32, 32, 32, "ikj", 4)
    src = kernel_source(cfg)
    lines = [BAR, " 实验五：配置 → 源码（迷你 Lowering 的产物）", BAR,
             f" {cfg.describe()} 生成的内核源码：", ""]
    lines += [" " + ln for ln in src.splitlines()]
    if outdir:
        with open(os.path.join(outdir, "src-ikj-u4.txt"), "w", encoding="utf-8") as fh:
            fh.write(src)
    return "\n".join(lines)


# ---------------------------------------------------------------- 自检（断言式）


def self_test() -> str:
    import math

    results = []

    def assert_eq(name, got, want):
        results.append((name, got == want, f"got {got!r}, want {want!r}"))

    def assert_true(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    # ---- 统计口径：手算样例 ----
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert_eq("median 奇数长度", median(xs), 5)
    assert_eq("MAD 手算", mad(xs), 2)
    assert_eq("无离群（阈值 3.5×1.4826×2≈10.4）", outlier_indices(xs), [])
    ys = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    m = median(ys)
    assert_eq("median 偶数长度（两中点取均值）", m, 5.5)
    assert_eq("离群规则抓住 100", outlier_indices(ys), [9])
    assert_true("均值被 100 拖走", _mean(ys) > 13, f"mean={_mean(ys)}")
    assert_eq("MAD 手算（偶数长度）", mad(ys), 2.5)
    zs = [10.0] * 12
    assert_eq("MAD=0 规则退化为不报离群（已知行为）", outlier_indices(zs), [])
    xs21 = list(range(21))
    assert_eq("repeats=21 的中位数是第 11 个次序统计量", median(xs21), 10)
    assert_eq("median_of_prefix k=1 = 第一个样本", median_of_prefix(xs21, 1), 0)
    assert_eq("trimmed_mean 两端各 10%", round(trimmed_mean(list(range(10)), 10), 4),
              round(_mean(list(range(1, 9))), 4))
    s = summarize_ms([5, 5, 5, 5, 6, 5, 5, 5, 5])
    assert_eq("spread% = (max−min)/median", s["spread_pct"], 20.0)
    assert_true("mean−median% 为正在此例", s["mean_minus_median_pct"] > 0)

    # ---- 固定输入 ----
    A1, B1, b1 = make_inputs(9, 7, 5, seed=42)
    A2, B2, b2 = make_inputs(9, 7, 5, seed=42)
    assert_true("同一 seed 两次生成逐元素相等", A1 == A2 and B1 == B2 and b1 == b2)
    A3, _, _ = make_inputs(9, 7, 5, seed=7)
    assert_true("换 seed 得到不同数据", A1 != A3)

    # ---- 门：拒错、放对、拒后不计时 ----
    spec = BenchSpec(13, 17, 19)
    proto = Protocol()
    env = capture_env()
    good = bench_one(KernelConfig(32, 32, 32, "ikj", 4), spec, proto, env)
    assert_true("好内核过门（逐位）", good["correctness"]["passed"] is True)
    assert_eq("好内核 max_abs_err 为 0", good["correctness"]["max_abs_err"], 0.0)
    bad = _bench_broken(spec, proto, env)
    assert_true("no-tail 内核被拒", bad["correctness"]["passed"] is False)
    assert_true("被拒配置不计时（samples 为 None）", bad["samples_ms"] is None)
    assert_true("被拒配置不产统计（stats 为 None）", bad["stats_ms"] is None)
    assert_true("被拒记录照样落盘且带错误量", bad["correctness"]["max_abs_err"] > 0.1)

    # ---- 记录格式：自包含、可往返 ----
    for key in ("schema", "kernel", "workload", "env", "protocol", "correctness",
                "stats_ms", "samples_ms", "timestamp"):
        assert_true(f"记录含 {key}", key in good)
    assert_eq("schema 版本号", good["schema"], SCHEMA)
    rt = json.loads(json.dumps(good, ensure_ascii=False))
    assert_eq("JSON 往返逐字段相等", rt, good)
    assert_eq("样本数 = repeats", len(good["samples_ms"]), proto.repeats)
    assert_eq("workload 名义 flops = 2·M·N·K", good["workload"]["flops_nominal"],
              2 * 13 * 17 * 19)
    assert_true("环境快照在记录里（python/cpu_count）",
                "python" in good["env"] and "cpu_count" in good["env"])
    assert_true("协议在记录里（warmup/repeats/gc）",
                good["protocol"]["warmup"] == 3 and good["protocol"]["repeats"] == 21
                and good["protocol"]["gc"] == "off")
    assert_true("记录不收主机名/用户名（性能要户口不要隐私）",
                "hostname" not in good["env"] and "user" not in good["env"])

    # ---- 协议默认与 fail-closed ----
    d = Protocol()
    assert_eq("默认 warmup=3（D97 遗产）", d.warmup, 3)
    assert_eq("默认 repeats=21", d.repeats, 21)
    assert_eq("默认排除口径 gc=off", d.gc_enabled, False)
    assert_eq("默认门=bitwise", d.policy, "bitwise")
    assert_true("MAD 阈值常数 = 3.5×1.4826", math.isclose(MAD_K, 3.5 * 1.4826))

    # ---- 内核工厂 fail-closed ----
    try:
        KernelConfig(32, 32, 32, "aabb", 1)
        results.append(("order 非排列被拒", False, "未抛出"))
    except ValueError:
        results.append(("order 非排列被拒", True, ""))
    try:
        KernelConfig(32, 32, 32, "ijk", 0)
        results.append(("unroll=0 被拒", False, "未抛出"))
    except ValueError:
        results.append(("unroll=0 被拒", True, ""))

    # ---- 真跑一条：统一入口全链路 ----
    tiny = bench_one(KernelConfig(8, 8, 8, "ijk", 1), BenchSpec(8, 8, 8), Protocol(warmup=1, repeats=5))
    assert_true("统一入口真跑出统计", tiny["stats_ms"]["n"] == 5)
    assert_true("中位数落在 min..max", tiny["stats_ms"]["min"] <= tiny["stats_ms"]["median"]
                <= tiny["stats_ms"]["max"])
    assert_true("wall_ms 覆盖全链路（门+预热+计时）", tiny["wall_ms"] > 0)

    n_pass = sum(1 for _, ok, _ in results if ok)
    lines = [BAR, f" 自检：{n_pass}/{len(results)} 项断言通过", BAR]
    for name, ok, detail in results:
        lines.append(("  ✓ " if ok else "  ✗ ") + name + ("" if ok else f"  ——  {detail}"))
    if n_pass != len(results):
        raise SystemExit("自检失败")
    return "\n".join(lines)


def _bench_broken(spec: BenchSpec, proto: Protocol, env: dict) -> dict:
    """no-tail 内核走统一入口（kernel 参数换掉默认的好内核）。"""
    cfg = KernelConfig(32, 32, 32, "ikj", 4)
    return bench_one(cfg, spec, proto, env, kernel=make_kernel(cfg, drop_tail=True))


# ---------------------------------------------------------------- CLI


EXPS = {
    "table": exp_table,
    "outliers": exp_outliers,
    "gc": exp_gc,
    "gate": exp_gate,
    "show-src": exp_show_src,
    "self-test": self_test,
}


def env_block() -> str:
    e = capture_env()
    return "\n".join([
        f"环境：Python {e['python']}（{e['implementation']}），{e['system']}/{e['machine']}，"
        f"{e['cpu_count']} 逻辑核",
        f"CPU：{e['cpu_model']}",
        f"时钟：{e['clock']}（分辨率 {e['clock_res_us']} µs）",
        f"协议默认：warmup=3、repeats=21、gc=off、policy=bitwise（D97 遗产，今天立成工具）",
        "被测内核：纯 Python tiled MatMul+bias（CPython 字节码成本模型，不代表硬件）",
        f"记录格式：{SCHEMA}（JSONL，每条自包含 env+protocol+原始样本）",
        f"运行日期：{iso_now()}",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="D107 统一 Benchmark 工具")
    ap.add_argument("--exp", default="all",
                    help="all/table/outliers/gc/gate/show-src/self-test/bench")
    ap.add_argument("--outdir", default=None, help="结果写入目录（outputs/）")
    ap.add_argument("--config", default="32,32,32,ikj,1",
                    help="bench 模式的内核配置：tm,tn,tk,order,unroll")
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=21)
    ap.add_argument("--gc-on", action="store_true", help="计时窗口包含 gc（包含口径）")
    ap.add_argument("--shape", default="96,96,96", help="bench 模式的 M,N,K")
    args = ap.parse_args()

    if args.exp == "bench":
        tm, tn, tk, order, unroll = args.config.split(",")
        M, N, K = (int(v) for v in args.shape.split(","))
        proto = Protocol(warmup=args.warmup, repeats=args.repeats, gc_enabled=args.gc_on)
        rec = bench_one(KernelConfig(int(tm), int(tn), int(tk), order, int(unroll)),
                        BenchSpec(M=M, N=N, K=K), proto)
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 0

    if args.exp == "all":
        texts = {
            "bench-table.txt": exp_table(args.outdir),
            "outliers.txt": exp_outliers(args.outdir),
            "gc.txt": exp_gc(args.outdir),
            "correctness.txt": exp_gate(args.outdir),
            "src-ikj-u4.txt": exp_show_src(args.outdir),
            "test-all.txt": self_test(),
            "env.txt": env_block(),
        }
        for name, text in texts.items():
            print(text + "\n")
            if args.outdir:
                os.makedirs(args.outdir, exist_ok=True)
                with open(os.path.join(args.outdir, name), "w", encoding="utf-8") as fh:
                    fh.write(text + "\n")
        return 0

    fn = EXPS.get(args.exp)
    if fn is None:
        print(f"未知实验：{args.exp!r}（可选 {'/'.join(EXPS)}）", file=sys.stderr)
        return 2
    text = fn(args.outdir) if args.exp not in ("self-test",) else fn()
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
