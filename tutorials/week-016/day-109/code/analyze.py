#!/usr/bin/env python3
"""D109 性能分析：读 D108 的调优记录 → 有效 GFLOPS / 算术强度 / Roofline 瓶颈标记。

D108 的 results.jsonl 每条记录自带 workload.flops_nominal（= 2·M·N·K），
今天把它换成三个坐标系里的数：
  ① 有效 GFLOPS = flops_nominal ÷ 实测 median —— 回答『有多快』（速率，跨 shape 可比）
  ② 算术强度 AI = flops_nominal ÷ bytes_min —— 回答『搬 1 字节做多少 FLOP』
  ③ Roofline 位置 = min(算力屋顶, 带宽屋顶×AI) 与实测的对照 —— 回答『离极限多远、瓶颈在哪』

机器模型用三个探针实测（屋顶必须与被解释的数据同一执行层——D108 的
『冠军只对实测成本模型诚实』纪律在屋顶上的延续）：
  探针 A 解释屋顶：纯 Python 标量 FMA 循环（函数局部变量，镜像内核内层写法）
  探针 B Python 级流读：迭代式逐元素流读（名义 8 B/元素）＋下标式敏感性对照
  探针 C C 级流读：sum(array('d'))，64 MB 工作集（CPython 的 C 层内存通路）

诚实边界（README 3.4/5.3 展开）：
  - 名义 AI 假设每个元素单遍搬运；真实 tiled 内核会重读数据，实际 AI 更低
  - 探针 B 的『带宽』物理来源是解释器逐元素成本，不是 DRAM 带宽
  - 本环境无 BLAS/numpy，硬件级算力屋顶测不到——what-if 段用假设参数，明确标注
  - 探针与 D108 的测量不在同一进程：屋脊余量（85~127×）远大于 D107 实测的
    跨进程漂移（~8.6%），结论对漂移稳健
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
import zlib
from array import array
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parent
OUTDIR = CODE / "outputs"
INPUT = CODE / "inputs" / "results-d108.jsonl"
PROBES_JSON = OUTDIR / "probes.json"

D108_SHA256 = "e8c8daa36e55da1e81e1dd797a537a6848c292851bb612093a6cf271de31037f"

# 探针参数（反复测量取中位数；n 取百万级保证单次 ≥ 0.1 s，量得住）
FMA_ITERS = 2_000_000
FMA_REPS = 5
PYELEMS = 2_000_000
PY_REPS = 5
C_BYTES = 64_000_000           # 64 MB：大于典型 L2/L3，量的是内存通路
C_REPS = 5


# ---------------------------------------------------------------- 工作量与搬运量


def flops_matmul_bias(M: int, N: int, K: int) -> int:
    """名义计算量：乘法 MNK 次 ＋ 加法 MNK 次。

    bias 的 MN 次加法（S2 占 0.52%）与 D108 记录的 flops_nominal 口径一致地忽略
    ——工作量字段必须和记录对齐，否则换算出来的 GFLOPS 是另一个量的速率。
    """
    return 2 * M * N * K


def bytes_min_fp32(M: int, N: int, K: int) -> int:
    """名义单遍搬运量（fp32）：A 读一遍 ＋ B 读一遍 ＋ C 写一遍。

    bias 的 4N 字节（S2 占 0.35%）与 flops 侧的忽略对称。tiled 内核实际会
    重读数据，实际搬运量更大——名义 AI 因此是『理想强度』，见 README 3.3。
    """
    return 4 * (M * N + N * K + M * K)


def arithmetic_intensity(M: int, N: int, K: int) -> float:
    """名义算术强度（FLOP/B）。立方 shape 的闭式捷径：AI = n/6。"""
    return flops_matmul_bias(M, N, K) / bytes_min_fp32(M, N, K)


def gflops(flops: int, ms: float) -> float:
    """有效 GFLOPS：名义工作量 ÷ 实测时间。ms 用中位数口径（D107/D108 遗产）。"""
    return flops / (ms * 1e-3) / 1e9


def ridge_ai(peak_gflops: float, bw_gbps: float) -> float:
    """屋脊点：算力屋顶 ÷ 带宽屋顶（FLOP/B）。左边带宽区，右边算力区。"""
    return peak_gflops / bw_gbps


def attainable(ai: float, peak_gflops: float, bw_gbps: float) -> float:
    """Roofline 可达性能：min(算力屋顶, 带宽屋顶 × AI)。"""
    return min(peak_gflops, bw_gbps * ai)


# ---------------------------------------------------------------- 三个探针（机器模型）


def probe_interp_roof() -> dict:
    """探针 A：纯 Python 标量 FMA 循环 → 解释执行层的算力屋顶。

    镜像内核内层写法：函数局部变量（LOAD_FAST），每迭代 2 FLOPs。
    内核的内层是 Ci[v3] += a * Bv[v3]（带下标和存储），纯 FMA 无这些开销，
    所以它是解释层每个 FLOP 能付出的上界——屋顶就该比所有内核点都高。
    """
    def fma(n: int, a: float = 1.0000001, b: float = 1.0) -> float:
        acc = 0.0
        for _ in range(n):
            acc = acc * a + b
        return acc

    rates = []
    for _ in range(FMA_REPS):
        t0 = time.perf_counter()
        fma(FMA_ITERS)
        dt = time.perf_counter() - t0
        rates.append(2 * FMA_ITERS / dt / 1e9)          # GFLOPS
    return {"name": "A 解释屋顶（纯 Python 标量 FMA）", "value_gflops": statistics.median(rates),
            "reps": rates, "iters": FMA_ITERS}


def probe_py_stream() -> dict:
    """探针 B：Python 级流读 → 解释层逐元素吞吐（名义 8 B/元素）。

    迭代式（for x in lst）是逐元素解释成本的下界（比内核的下标访问便宜），
    作屋顶用；下标式（lst[i]）另测一次做敏感性对照（对照 B，README 5.4）。
    注意它的物理来源是字节码分发成本，不是 DRAM——README 3.4 讲这条边界。
    """
    lst = [0.5] * PYELEMS

    def stream_iter(xs) -> float:
        s = 0.0
        for x in xs:
            s += x
        return s

    def stream_sub(xs) -> float:
        s = 0.0
        n = len(xs)
        for i in range(n):
            s += xs[i]
        return s

    out = {}
    for tag, fn in (("iter", stream_iter), ("sub", stream_sub)):
        rates = []
        for _ in range(PY_REPS):
            t0 = time.perf_counter()
            fn(lst)
            dt = time.perf_counter() - t0
            rates.append(8 * PYELEMS / dt / 1e9)        # GB/s（名义 8 B/元素）
        out[tag] = rates
    return {"name": "B Python 级流读（名义 8 B/元素）", "value_gbps": statistics.median(out["iter"]),
            "reps": out["iter"], "sub_gbps": statistics.median(out["sub"]),
            "sub_reps": out["sub"], "elems": PYELEMS}


def probe_c_stream() -> dict:
    """探针 C：C 级缓冲区扫描（zlib.adler32）→ 这台机器的单流内存通路带宽。

    为什么不用 sum(array('d'))：它每个元素都要装箱成 PyFloat 对象（0.95 GB/s），
    量的是 CPython 的装箱吞吐，不是内存。adler32 是纯 C 读通道，逐字节扫过
    64 MB 缓冲区，无对象开销。crc32 本机上只有 0.99 GB/s（多项式计算拖慢），
    作为『探针风格敏感性』对照一并报告（README 5.4 对照 B）。
    """
    buf = b"\x00" * C_BYTES
    rates, rates_crc = [], []
    for _ in range(C_REPS):
        t0 = time.perf_counter()
        zlib.adler32(buf)
        rates.append(C_BYTES / (time.perf_counter() - t0) / 1e9)   # GB/s
        t0 = time.perf_counter()
        zlib.crc32(buf)
        rates_crc.append(C_BYTES / (time.perf_counter() - t0) / 1e9)
    return {"name": "C C 级缓冲区扫描（zlib.adler32，64 MB）",
            "value_gbps": statistics.median(rates), "reps": rates,
            "crc_gbps": statistics.median(rates_crc), "bytes": C_BYTES}


def run_probes() -> dict:
    print("机器模型探针（实测，反复取中位数；本环境与 D108 同机同日）")
    a = probe_interp_roof()
    print(f"  A {a['name']}: {a['value_gflops']:.4f} GFLOPS = {a['value_gflops']*1e3:.1f} MFLOPS"
          f"（5 次: {', '.join(f'{r*1e3:.1f}' for r in a['reps'])} MF）")
    b = probe_py_stream()
    print(f"  B {b['name']}: 迭代式 {b['value_gbps']:.3f} GB/s"
          f"（5 次: {', '.join(f'{r:.3f}' for r in b['reps'])}）")
    print(f"    敏感性对照·下标式: {b['sub_gbps']:.3f} GB/s"
          f"（5 次: {', '.join(f'{r:.3f}' for r in b['sub_reps'])}）")
    c = probe_c_stream()
    print(f"  C {c['name']}: {c['value_gbps']:.2f} GB/s"
          f"（5 次: {', '.join(f'{r:.2f}' for r in c['reps'])}）")
    print(f"    敏感性对照·crc32: {c['crc_gbps']:.2f} GB/s（另一个 C 级探针，多项式计算更慢）")
    return {"A": a, "B": b, "C": c}


def cached_probes() -> dict:
    """同一次复现内口径一致：有缓存就读缓存，没有就现场实测并落盘。

    跨进程漂移是 D107 实测过的真实现象（~8.6%）；table/roofline/env 三个报告
    必须引用同一组屋顶读数，否则文件之间互相打架。删除 probes.json 即可强制重测。
    """
    if PROBES_JSON.is_file():
        data = json.loads(PROBES_JSON.read_text(encoding="utf-8"))
        print(f"（探针读取缓存 {PROBES_JSON.name}：同一次复现内口径一致；删除它可强制重测）")
        return {k: v for k, v in data.items() if k in ("A", "B", "C")}
    probes = run_probes()
    OUTDIR.mkdir(exist_ok=True)
    PROBES_JSON.write_text(json.dumps(probes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"（探针读数已落盘 {PROBES_JSON.name}，供 table/roofline/env 复用）")
    return probes


# ---------------------------------------------------------------- 记录读取


def load_records(path: Path = INPUT) -> list:
    """读 D108 记录并验证血统：sha256 必须等于 D108 落盘原件。"""
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != D108_SHA256:
        raise SystemExit(f"输入血统校验失败：{path}\n  期望 sha256={D108_SHA256}\n  实际          ={digest}")
    recs = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    print(f"读取 {path.name}：{len(recs)} 条记录，sha256 校验通过（与 D108 outputs/results.jsonl 逐字节一致）")
    return recs


def analyze_records(recs: list) -> dict:
    """按 shape 聚合：每 shape 的工作量/搬运量/AI ＋ 通过记录的 GFLOPS 排名。

    排名口径纪律（D108 遗产）：决赛（3+21）与筛选（3+7）是两种协议，
    不混进同一张名次表——render_table 分两个子表各自排名。
    """
    shapes = {}
    for r in recs:
        sid = r["tune"]["shape_id"]
        w = r["workload"]
        M, N, K = w["M"], w["N"], w["K"]
        sh = shapes.setdefault(sid, {"M": M, "N": N, "K": K,
                                     "flops": w["flops_nominal"],
                                     "bytes_min": bytes_min_fp32(M, N, K),
                                     "ai": arithmetic_intensity(M, N, K),
                                     "passed": [], "rejected": []})
        if r["correctness"]["passed"]:
            med = r["stats_ms"]["median"]
            sh["passed"].append({
                "name": r["kernel"]["name"], "stage": r["tune"]["stage"],
                "median_ms": med, "mean_ms": r["stats_ms"]["mean"],
                "gflops": gflops(w["flops_nominal"], med),
                "gflops_mean": gflops(w["flops_nominal"], r["stats_ms"]["mean"])})
        else:
            sh["rejected"].append({"name": r["kernel"]["name"],
                                   "max_abs_err": r["correctness"]["max_abs_err"]})
    for sid, sh in shapes.items():
        sh["passed"].sort(key=lambda e: (-e["gflops"], e["median_ms"]))
    return shapes


def champion(sh: dict) -> dict:
    """某 shape 的冠军：决赛阶段、决赛协议（3+21）中位数最小的一条。"""
    finals = [e for e in sh["passed"] if e["stage"] == "final"]
    return min(finals, key=lambda e: e["median_ms"])


# ---------------------------------------------------------------- 交付物①：性能分析表


def render_table(shapes: dict, roof: float, bw_py: float) -> str:
    lines = []
    bar = "=" * 96
    lines += [bar, " 性能分析表：有效 GFLOPS / 算术强度 / 距屋顶倍数（D109 主交付物①）", bar]
    ridge = ridge_ai(roof, bw_py)
    for sid in ("S1", "S2", "S3"):
        sh = shapes[sid]
        M, N, K = sh["M"], sh["N"], sh["K"]
        cube = "（立方捷径 n/6）" if M == N == K else ""
        lines += ["",
                  f"[{sid}] C=A·B+bias，{M}×{N}×{K}，seed=42，fp32",
                  f"  flops_nominal = 2·{M}·{N}·{K} = {sh['flops']:,}",
                  f"  bytes_min     = 4·(MN+NK+MK) = {sh['bytes_min']:,} B{cube}",
                  f"  名义 AI       = {sh['flops']:,} ÷ {sh['bytes_min']:,} = {sh['ai']:.4f} FLOP/B"
                  f"（屋脊点 {ridge:.3f} 右侧 {sh['ai']/ridge:.0f} 倍 → 解释受限区）"]
        finals = [e for e in sh["passed"] if e["stage"] == "final"]
        screens = [e for e in sh["passed"] if e["stage"] == "screen"]
        lines += ["",
                  "  决赛（3+21 协议）——冠军与缺省同协议同进程可比（D108 纪律）",
                  "  名次  配置                        median ms   GFLOPS    MFLOPS  距屋顶×  屋顶利用率",
                  "  " + "-" * 86]
        for rank, e in enumerate(finals, 1):
            mark = " ←冠军" if e is champion(sh) else (" ←缺省" if e["name"].endswith("32³ ijk U=1") else "")
            lines.append(f"  {rank:3d}  {e['name']:<30.30s}  {e['median_ms']:7.2f}"
                         f"   {e['gflops']:.4f}   {e['gflops']*1e3:6.1f}   {roof/e['gflops']:5.2f}"
                         f"   {e['gflops']/roof*100:5.1f}%{mark}")
        lines += ["",
                  f"  筛选段（3+7 协议，{len(screens)} 条；GFLOPS 降序，只列极值——完整名单见 results-d108.jsonl）",
                  "  " + "-" * 86]
        for tag, e in (("最快", screens[0]), ("最慢", screens[-1])):
            lines.append(f"   {tag} {e['name']:<30.30s}  {e['median_ms']:7.2f}"
                         f"   {e['gflops']:.4f}   {e['gflops']*1e3:6.1f}   {roof/e['gflops']:5.2f}"
                         f"   {e['gflops']/roof*100:5.1f}%")
        if sh["rejected"]:
            for e in sh["rejected"]:
                lines.append(f"  被拒 {e['name']}  max_abs_err={e['max_abs_err']:.2f}"
                              f" → 不计时，不进性能表（D107 门纪律）")
        lines.append(f"  筛选段 GFLOPS 范围：{screens[-1]['gflops']*1e3:.1f} ~ {screens[0]['gflops']*1e3:.1f} MFLOPS"
                      f"（跨度 {(screens[0]['gflops']/screens[-1]['gflops']):.2f}×）")
    finals_all = [e for s in shapes.values() for e in s["passed"] if e["stage"] == "final"]
    lines += ["", "-" * 96,
              f" 全局（决赛口径）：有效 GFLOPS 范围 {min(e['gflops'] for e in finals_all):.4f}"
              f" ~ {max(e['gflops'] for e in finals_all):.4f} GFLOPS",
              f" 三 shape 冠军：S1 {champion(shapes['S1'])['gflops']*1e3:.1f} / "
              f"S2 {champion(shapes['S2'])['gflops']*1e3:.1f} / "
              f"S3 {champion(shapes['S3'])['gflops']*1e3:.1f} MFLOPS"
              f"——工作量差 3.4×，速率几乎平（解释受限的指纹，详见 roofline.txt）",
              f" 记录数：110 条 = 通过 108（screen 96 + final 12）+ 被拒 2；"
              f"被拒记录 stats_ms=null，天然进不了任何速率表",
              f" 口径：roof={roof:.4f} GFLOPS（探针 A 中位数）；BW={bw_py:.3f} GB/s（探针 B 迭代式中位数）；"
              f"屋脊 AI*={ridge:.3f} FLOP/B"]
    lines += [bar, ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- 交付物②：Roofline 报告


def render_roofline(shapes: dict, probes: dict) -> str:
    roof = probes["A"]["value_gflops"]
    bw_py = probes["B"]["value_gbps"]
    bw_py_sub = probes["B"]["sub_gbps"]
    bw_c = probes["C"]["value_gbps"]
    ridge = ridge_ai(roof, bw_py)
    ridge_sub = ridge_ai(roof, bw_py_sub)
    mult = [shapes[s]["ai"] / ridge for s in ("S1", "S2", "S3")]
    lines = []
    bar = "=" * 96
    lines += [bar, " Roofline 报告：机器模型 / 屋脊点 / 内核点定位 / 瓶颈标记（D109 主交付物②）", bar]

    lines += ["",
              " 一、机器模型（三个探针实测；屋顶与被分析数据同一执行层）",
              f"   A 解释屋顶 P_int   = {roof:.4f} GFLOPS（纯 Python 标量 FMA，{FMA_ITERS:,} 迭代 × {FMA_REPS} 次取中位数）",
              f"   B Python 级流读 BW = {bw_py:.3f} GB/s（迭代式，名义 8 B/元素；"
              f"下标式敏感性对照 {bw_py_sub:.3f} GB/s）",
              f"   C C 级缓冲区扫描 BW_C = {bw_c:.2f} GB/s（zlib.adler32，{C_BYTES//1_000_000} MB；"
              f"crc32 对照 {probes['C']['crc_gbps']:.2f} GB/s）",
              "",
              " 二、屋脊点 AI* = P ÷ BW（FLOP/B）：左边带宽区，右边算力区",
              f"   Python 层：AI* = {roof:.4f} ÷ {bw_py:.3f} = {ridge:.3f} FLOP/B",
              f"   敏感性：换成下标式流读 AI* = {roof:.4f} ÷ {bw_py_sub:.3f} = {ridge_sub:.3f} FLOP/B",
              f"           ——探针风格挪动屋脊 {ridge_sub/ridge:.1f}×，但 matmul 的 AI 仍在右侧"
              f" {min(shapes[s]['ai']/ridge_sub for s in ('S1','S2','S3')):.0f} 倍以上，判定不动",
              "",
              " 三、内核点定位（决赛 12 条；allowed = BW×AI，attainable = min(P, allowed)）",
              "   shape  AI(F/B)  allowed(GF)  P_int   attainable  实测GFLOPS  距屋顶×  瓶颈判定",
              "   " + "-" * 88]
    for sid in ("S1", "S2", "S3"):
        sh = shapes[sid]
        allowed = bw_py * sh["ai"]
        att = attainable(sh["ai"], roof, bw_py)
        for e in sh["passed"]:
            if e["stage"] != "final":
                continue
            tag = "解释受限" if sh["ai"] > ridge else "带宽受限"
            mark = " ←冠军" if e is champion(sh) else (" ←缺省" if e["name"].endswith("32³ ijk U=1") else "")
            lines.append(f"   {sid}   {sh['ai']:6.2f}   {allowed:8.3f}  {roof:.4f}   {att:.4f}"
                         f"    {e['gflops']:.4f}     {roof/e['gflops']:5.2f}   {tag}{mark}")
    lines += ["",
              f"   判定依据：三个 shape 的 AI（10.67/16.00/13.46）都在屋脊点右侧 {min(mult):.0f}~{max(mult):.0f} 倍 →",
              f"   全部落在算力（本环境＝解释执行）受限区；同时 allowed（BW×AI）比 P_int 高同样的"
              f" {min(mult):.0f}~{max(mult):.0f} 倍，",
              "   带宽屋顶根本不是约束——108 条通过记录无一例外，标记统一为『解释受限』。",
              "",
              f" 四、解释税：同样的名义搬运量，走 C 级通路要多久 vs 冠军内核实测多久（@{bw_c:.2f} GB/s）",
              "   shape  bytes_min(B)   C 级搬运耗时    冠军实测     解释税（倍）",
              "   " + "-" * 88]
    for sid in ("S1", "S2", "S3"):
        sh = shapes[sid]
        champ = champion(sh)
        t_c_us = sh["bytes_min"] / (bw_c * 1e3)        # bytes ÷ (GB/s) = ×1e-9 s → ×1e6 µs
        tax = champ["median_ms"] * 1e3 / t_c_us
        lines.append(f"   {sid}   {sh['bytes_min']:>10,}   {t_c_us:10.2f} µs"
                     f"  {champ['median_ms']*1e3:>10.0f} µs   {tax:8,.0f}×")
    lines += ["",
              "   注意口径：bytes_min 是名义单遍（tiled 内核实际重读，真实搬运更多），",
              "   所以解释税是按『理想搬运量』算的下界——真实解释税只高不低。",
              "",
              " 五、C 层 what-if（带宽用实测 BW_C；算力屋顶 P_hw 是假设参数——本环境无 BLAS，测不到）",
              f"   屋脊随假设移动：P_hw ∈ {{1, 5, 20}} GFLOPS → AI* ∈ "
              f"{{{1/bw_c:.2f}, {5/bw_c:.2f}, {20/bw_c:.2f}}} FLOP/B",
              "   matmul AI 10.67~16.00 在三种假设下都高于屋脊 → C 层上 matmul 是算力受限"
              "（compute-bound 算子的由来）",
              f"   S1 要翻成带宽受限需要 P_hw > BW_C×AI = {bw_c*shapes['S1']['ai']:.0f} GFLOPS"
              "——屋脊判定只由两个屋顶的比值决定",
              f"   对照：elementwise bias-add AI ≈ 1/8 = 0.125 FLOP/B，低于上述任一屋脊 → C 层上带宽受限",
              "   → 融合（D72）让低强度的 elementwise 搭 matmul 数据复用的便车——今天给 D110 cost model 备料",
              "",
              " 六、数据指纹：解释受限的独立证据（不依赖探针，只看记录）",
              "   冠军 GFLOPS：S1 33.2 / S2 34.3 / S3 34.5 MFLOPS——工作量差 3.4×，速率只差 4%；",
              "   若带宽受限：AI 更高的 S2（16.0）应该显著更快——实测没有；",
              "   若真硬件算力受限：GFLOPS 不该只有 0.03 量级（差假设算力屋顶 2~3 个数量级）；",
              "   平坦＋贴解释屋顶＝解释成本按 FLOP 计价的指纹，与探针屋脊点判定互相印证。",
              "",
              " 诚实边界：探针与 D108 测量不在同一进程，跨进程漂移 D107 实测 ~8.6%；",
              f" 屋脊余量 {min(mult):.0f}~{max(mult):.0f}×，屋顶利用率取值当 ±10% 看即可，判定不受影响。"]
    lines += [bar, ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- 环境与对照


def render_env(probes: dict) -> str:
    lines = ["=" * 78,
             " 环境：D109 性能分析（roofline/性能表）",
             "=" * 78,
             f" Python：{platform.python_version()}（{platform.python_implementation()}）",
             f" 系统：{platform.system()} / {platform.machine()}，逻辑核 {os.cpu_count()}",
             " 时钟：time.perf_counter（探针与 D108 同款）",
             " 依赖：零第三方（探针用 array/statistics，均为标准库）",
             f" 输入：inputs/results-d108.jsonl（110 条，sha256={D108_SHA256[:16]}…）",
             " 口径：kernel 时间 = D108 记录里的决赛/筛选中位数（不重测）；",
             "       屋顶 = 本机探针中位数（5 次重复）；两者不同进程，余量 ≫ 漂移",
             f" 运行日期：{time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
             "=" * 78, ""]
    return "\n".join(lines)


def render_mean_vs_median(shapes: dict) -> str:
    """对照 A：mean vs median 换口径重算 GFLOPS（零重跑，读记录里的两个统计量）。"""
    lines = ["=" * 78,
             " 对照 A：mean 口径 vs median 口径的有效 GFLOPS（读 D108 记录，零重跑）",
             "=" * 78]
    for sid in ("S1", "S2", "S3"):
        sh = shapes[sid]
        lines.append(f" [{sid}] 决赛 4 条：")
        finals = [e for e in sh["passed"] if e["stage"] == "final"]
        for e in sorted(finals, key=lambda x: x["median_ms"]):
            d = (e["gflops_mean"] / e["gflops"] - 1) * 100
            lines.append(f"   {e['name']:<30.30s} median={e['gflops']*1e3:6.1f} MF  "
                         f"mean={e['gflops_mean']*1e3:6.1f} MF  Δ={d:+.2f}%")
        med_rank = [e["name"] for e in sorted(finals, key=lambda x: x["median_ms"])]
        by_mean = [e["name"] for e in sorted(finals, key=lambda x: -x["gflops_mean"])]
        lines.append(f"   排名按 median 与按 mean 一致：{med_rank == by_mean}")
    lines += ["", " 结论：GFLOPS 排名对口径稳健（D107 稳定性实验的速率版）；",
              " 换算单位不改变排序，只改变每行的读数——口径必须写进表头，数值才能被复用。", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- 自检


def self_test() -> None:
    print("D109 自检（公式 / 口径 / 血统 / 屋顶合理性 / 判定余量）")
    ok = [0]

    def check(cond, msg):
        assert cond, msg
        ok[0] += 1
        print(f"  ✓ {msg}")

    # ① 输入血统
    recs = load_records()
    check(len(recs) == 110, "记录数 110 条（98 筛选 + 12 决赛）")
    c = Counter((r["tune"]["shape_id"], r["tune"]["stage"]) for r in recs)
    check(c == Counter({("S1", "screen"): 24, ("S1", "final"): 4,
                        ("S2", "screen"): 36, ("S2", "final"): 4,
                        ("S3", "screen"): 38, ("S3", "final"): 4}),
          "分段账 S1:24+4 / S2:36+4 / S3:38+4")
    # ② 工作量公式逐条验证（flops_nominal == 2MNK）
    check(all(r["workload"]["flops_nominal"] ==
              flops_matmul_bias(r["workload"]["M"], r["workload"]["N"], r["workload"]["K"])
              for r in recs), "全部 110 条 flops_nominal == 2·M·N·K")
    # ③ 搬运量与 AI
    check(bytes_min_fp32(96, 96, 96) == 110_592, "S2 bytes_min = 4×3×96² = 110,592 B")
    check(abs(arithmetic_intensity(96, 96, 96) - 16.0) < 1e-12, "S2 AI = 16.0 FLOP/B（96/6 精确）")
    check(abs(arithmetic_intensity(64, 64, 64) - 64 / 6) < 1e-12, "S1 AI = 64/6 = 10.67（立方捷径 n/6）")
    check(abs(arithmetic_intensity(90, 96, 64) - 1440 / 107) < 1e-9, "S3 AI = 1440/107 ≈ 13.458 FLOP/B")
    # ④ 有效 GFLOPS 的手算对照
    g = gflops(1_769_472, 51.535)
    check(abs(g - 0.03433) < 1e-4, f"S2 冠军 GFLOPS = 1,769,472 ÷ 51.535 ms = {g:.4f}（手算一致）")
    check(abs(gflops(524_288, 15.799) - 0.0331855) < 1e-6, "S1 冠军 GFLOPS = 0.03319（524,288 ÷ 15.799 ms）")
    check(abs(gflops(1_105_920, 32.057) - 0.0344985) < 1e-6, "S3 冠军 GFLOPS = 0.034499（1,105,920 ÷ 32.057 ms）")
    # ⑤ 屋脊与 attainable
    check(abs(ridge_ai(0.048, 0.383) - 0.12532) < 1e-4, "屋脊点 AI* = P ÷ BW = 0.048/0.383 ≈ 0.125")
    check(attainable(0.05, 10.0, 100.0) == 5.0, "AI 在屋脊左侧：attainable = BW×AI（带宽区）")
    check(attainable(0.5, 10.0, 100.0) == 10.0, "AI 在屋脊右侧：attainable = P（算力区）")
    # ⑥ 聚合与排名一致性
    shapes = analyze_records(recs)
    for sid, sh in shapes.items():
        check(len(sh["passed"]) + len(sh["rejected"]) ==
              {"S1": 28, "S2": 40, "S3": 42}[sid], f"{sid} 通过+被拒 = 记录数")
        gf = [e["gflops"] for e in sh["passed"]]
        med = [e["median_ms"] for e in sh["passed"]]
        check(gf == sorted(gf, reverse=True), f"{sid} GFLOPS 降序排列")
        check(med == sorted(med), f"{sid} GFLOPS 排名与 median 反序一一对应")
        check(sh["ai"] > 10.0, f"{sid} 名义 AI = {sh['ai']:.2f} > 10 FLOP/B（matmul 高强度算子）")
        champ = champion(sh)
        check(champ["stage"] == "final" and
              champ["median_ms"] == min(e["median_ms"] for e in sh["passed"] if e["stage"] == "final"),
              f"{sid} 冠军取决赛协议中位数最小的一条")
    check(all(len(s["rejected"]) == 0 for s in (shapes["S1"], shapes["S2"])) and
          len(shapes["S3"]["rejected"]) == 2, "被拒 2 条全部在 S3（投毒探针）")
    # ⑦ 探针合理性：屋顶必须高于所有内核点
    print("  （自检的探针为现场实测，与 probes.json 缓存读数可能差 ~10%——跨进程波动；")
    print("    断言全部用数量级余量，不受漂移影响）")
    a = probe_interp_roof()
    b = probe_py_stream()
    c2 = probe_c_stream()
    best = max(e["gflops"] for sh in shapes.values() for e in sh["passed"])
    check(a["value_gflops"] > best,
          f"解释屋顶 {a['value_gflops']*1e3:.1f} MFLOPS > 全部内核最高 {best*1e3:.1f} MFLOPS（是屋顶）")
    check(c2["value_gbps"] > b["value_gbps"],
          f"C 级带宽 {c2['value_gbps']:.2f} GB/s > Python 级 {b['value_gbps']:.3f} GB/s（分层正确）")
    check(b["sub_gbps"] < b["value_gbps"],
          f"下标式 {b['sub_gbps']:.3f} < 迭代式 {b['value_gbps']:.3f} GB/s（敏感性对照方向正确）")
    # ⑧ 解释受限指纹与判定余量
    champs = [champion(shapes[s])["gflops"] for s in ("S1", "S2", "S3")]
    spread = (max(champs) - min(champs)) / min(champs)
    check(spread < 0.05, f"冠军 GFLOPS 跨 shape 落差 {spread*100:.1f}% < 5%（解释受限指纹）")
    r = ridge_ai(a["value_gflops"], b["value_gbps"])
    check(all(shapes[s]["ai"] / r > 40 for s in ("S1", "S2", "S3")),
          f"三 shape AI 都在屋脊点右侧 >40 倍 → 判定『解释受限』余量充足")
    check(attainable(shapes["S2"]["ai"], a["value_gflops"], b["value_gbps"]) == a["value_gflops"],
          "S2 attainable = min(P, BW×16.0) = P（算力/解释侧生效）")
    print(f"  自检通过：{ok[0]} 项断言全部成立")


# ---------------------------------------------------------------- CLI


def main() -> int:
    ap = argparse.ArgumentParser(description="D109 GFLOPS/AI/Roofline 性能分析器")
    ap.add_argument("--exp", required=True,
                    choices=["all", "probes", "table", "roofline", "mean-vs-median", "env", "self-test"],
                    help="跑哪个实验")
    args = ap.parse_args()
    OUTDIR.mkdir(exist_ok=True)

    if args.exp == "self-test":
        self_test()
        return 0
    if args.exp == "env":
        probes = cached_probes()
        sys.stdout.write(render_env(probes))
        return 0
    if args.exp == "probes":
        if PROBES_JSON.is_file():
            PROBES_JSON.unlink()          # --exp probes 永远现场重测
        cached_probes()                   # 实测一次：打印的读数与落盘的缓存是同一份
        return 0

    recs = load_records()
    shapes = analyze_records(recs)
    if args.exp in ("all", "table"):
        probes = cached_probes()
        print(render_table(shapes, probes["A"]["value_gflops"], probes["B"]["value_gbps"]))
    if args.exp in ("all", "roofline"):
        probes = cached_probes()
        print(render_roofline(shapes, probes))
    if args.exp == "mean-vs-median":
        print(render_mean_vs_median(shapes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
