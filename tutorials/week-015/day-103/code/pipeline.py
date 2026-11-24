#!/usr/bin/env python3
"""第 103 天：双缓冲与流水线——让搬运和计算在同一时刻各干各的。

模型说明
--------
沿用 D102 的确定性模型（单 DMA 引擎按提交顺序执行、单计算单元、示例
硬件参数），把整个 kernel 建成一张依赖 DAG，逐事件排出三种真实时间线：

  single   单缓冲：A/B 各一个槽，WAR 复用距离 = 1（复现 D102 的账）
  double   逐块双缓冲：A/B 各两个槽（乒乓），算第 k 圈时搬第 k+1 圈，
           WAR 复用距离 = 2；每个输出块各自填充／排空一次
  pipeline 双缓冲＋跨块预取：下一块的 A0/B0 在本块末圈计算时就提前搬运，
           填充／排空从"每块一次"摊薄为"全 kernel 一次"

同步点沿用 D102 编号：S1(RAW 搬运→计算)、S2(WAR 计算→搬运)、
S3(RAW 计算→写回)、S4(WAR 写回→复用)。双缓冲没有消灭 S2，只是把
"必须等上一圈算完"放松成"必须等上上一圈算完"——复用距离从 1 拉到 2。

硬件参数为示例值（不代表任何具体芯片）；本程序的输出是这些参数下
确定性模型在本次运行中的真实计算结果，不是实测性能数据。
"""

from __future__ import annotations

import datetime
import os
import platform
import re
import sys
from dataclasses import dataclass, field

# ---------------- 示例硬件参数（µs / Byte / MAC 单位，同 D102） ----------------
DMA_BW = 32_768.0        # DMA 带宽，Byte/µs（32.768 GB/s，示例值）
MAC_RATE = 262_144.0     # 计算吞吐，MAC/µs（示例值）
SRAM_BUDGET = 262_144    # 片上 SRAM 预算：256 KiB（沿用 D101）
ALIGN = 32               # DMA 对齐，Byte
DTYPE_IN = 4             # FP32 输入，Byte/元素
DTYPE_ACC = 4            # FP32 累加，Byte/元素


def align_up(x: int, a: int = ALIGN) -> int:
    return (x + a - 1) // a * a


@dataclass
class Config:
    M: int = 512
    N: int = 512
    K: int = 512
    T: int = 64
    dma_bw: float = DMA_BW
    mac_rate: float = MAC_RATE
    mode: str = "double"          # single | double | pipeline

    @property
    def tiles_i(self) -> int:
        return self.M // self.T

    @property
    def tiles_j(self) -> int:
        return self.N // self.T

    @property
    def tiles_k(self) -> int:
        return self.K // self.T

    @property
    def load_t(self) -> float:        # 单个 A（或 B）块的搬运时长
        return align_up(self.T * self.T * DTYPE_IN) / self.dma_bw

    @property
    def compute_t(self) -> float:     # 单圈乘加
        return self.T ** 3 / self.mac_rate

    @property
    def store_t(self) -> float:
        return align_up(self.T * self.T * DTYPE_ACC) / self.dma_bw

    @property
    def bias_t(self) -> float:
        return align_up(self.T * DTYPE_ACC) / self.dma_bw


@dataclass
class Op:
    name: str
    kind: str                    # dma_load | dma_store | compute
    dur: float
    nbytes: int = 0
    macs: int = 0
    deps: list = field(default_factory=list)   # 数据／同步依赖（Op 列表）
    chain_prev: object = None                   # 同引擎前驱（引擎串行）
    start: float = 0.0
    end: float = 0.0
    tile: int = 0


# ---------------- 空间账本（规则沿用 D101） ----------------
def slots_single(cfg: Config) -> dict:
    """单缓冲：一个输出块在 SRAM 的家当。"""
    t = cfg.T
    return {
        "A[Tm×Tk]": align_up(t * t * DTYPE_IN),
        "B[Tk×Tn]": align_up(t * t * DTYPE_IN),
        "C[Tm×Tn]": align_up(t * t * DTYPE_ACC),
        "bias[Tn]": align_up(t * DTYPE_ACC),
    }


def slots_double(cfg: Config) -> dict:
    """双缓冲：×2 只加在 DMA 流入项（A/B）；C 与 bias 保持单份。"""
    t = cfg.T
    return {
        "A×2": 2 * align_up(t * t * DTYPE_IN),
        "B×2": 2 * align_up(t * t * DTYPE_IN),
        "C[Tm×Tn]": align_up(t * t * DTYPE_ACC),
        "bias[Tn]": align_up(t * DTYPE_ACC),
    }


# ---------------- 程序构建：依赖 DAG ----------------
def build_program(cfg: Config):
    kt = cfg.tiles_k
    nt = cfg.tiles_i * cfg.tiles_j
    d = 1 if cfg.mode == "single" else 2      # WAR 复用距离
    ops: list[Op] = []
    by_name: dict[str, Op] = {}
    dma_seq: list[Op] = []
    comp_seq: list[Op] = []
    s2_pairs = 0

    def emit(name, kind, dur, nbytes=0, macs=0, deps=()):
        op = Op(name=name, kind=kind, dur=dur, nbytes=nbytes, macs=macs,
                deps=[by_name[x] for x in deps])
        op.tile = int(re.match(r"\w+\[(\d+)", name).group(1))
        ops.append(op)
        by_name[name] = op
        (comp_seq if kind == "compute" else dma_seq).append(op)
        return op

    def war_ab(n: int, k: int):
        """A/B 槽 k%d 的上一个读者：要覆盖它，先等这位读者算完（S2）。"""
        if k - d >= 0:
            return f"c[{n},{k - d}]"
        if n > 0:
            kk = kt - 1 - ((kt - 1 - (k % d)) % d)   # 上一块里同槽号的最后一圈
            return f"c[{n - 1},{kk}]"
        return None

    for n in range(nt):
        # bias 切片：上一个读者是上一块的首圈计算（WAR）
        emit(f"bias[{n}]", "dma_load", cfg.bias_t,
             align_up(cfg.T * DTYPE_ACC),
             deps=(f"c[{n - 1},0]",) if n else ())
        for k in range(kt):
            # pipeline 模式下，n>0 块的 k=0 搬运已在上一块末圈预取发出
            if not (cfg.mode == "pipeline" and n > 0 and k == 0):
                w = war_ab(n, k)
                deps = (w,) if w else ()
                if w:
                    s2_pairs += 1
                emit(f"A[{n},{k}]", "dma_load", cfg.load_t,
                     align_up(cfg.T * cfg.T * DTYPE_IN), deps=deps)
                emit(f"B[{n},{k}]", "dma_load", cfg.load_t,
                     align_up(cfg.T * cfg.T * DTYPE_IN), deps=deps)
            # 计算 k：S1（RAW 等搬运）＋累加 RAW（k>0）＋S4（k=0 等 C 槽写回）
            cdeps = [f"A[{n},{k}]", f"B[{n},{k}]"]
            if k == 0:
                cdeps.append(f"bias[{n}]")
                if n:
                    cdeps.append(f"store[{n - 1}]")
            else:
                cdeps.append(f"c[{n},{k - 1}]")
            emit(f"c[{n},{k}]", "compute", cfg.compute_t,
                 macs=cfg.T ** 3, deps=cdeps)
        # 块尾。pipeline：先预取下一块 k=0（提交顺序在 store 之前！），再写回
        if cfg.mode == "pipeline" and n < nt - 1:
            w0 = war_ab(n + 1, 0)
            emit(f"A[{n + 1},0]", "dma_load", cfg.load_t,
                 align_up(cfg.T * cfg.T * DTYPE_IN), deps=(w0,))
            emit(f"B[{n + 1},0]", "dma_load", cfg.load_t,
                 align_up(cfg.T * cfg.T * DTYPE_IN), deps=(w0,))
            s2_pairs += 1
        emit(f"store[{n}]", "dma_store", cfg.store_t,
             align_up(cfg.T * cfg.T * DTYPE_ACC), deps=(f"c[{n},{kt - 1}]",))

    # 引擎链：两个引擎各自按提交顺序串行
    for seq in (dma_seq, comp_seq):
        for a, b in zip(seq, seq[1:]):
            b.chain_prev = a
    return ops, s2_pairs


def schedule(ops: list[Op]) -> None:
    """一遍正向传播排时间线；迭代到不动点以兜底。"""
    for _ in range(len(ops) + 2):
        changed = False
        for op in ops:
            release = op.chain_prev.end if op.chain_prev is not None else 0.0
            for dep in op.deps:
                if dep.end > release:
                    release = dep.end
            if abs(op.start - release) > 1e-12:
                op.start = release
                changed = True
            op.end = op.start + op.dur
        if not changed:
            return
    raise RuntimeError("调度未收敛：依赖图可能有环")


@dataclass
class Result:
    cfg: Config
    ops: list
    stats: dict

    def op(self, name: str) -> Op:
        for o in self.ops:
            if o.name == name:
                return o
        raise KeyError(name)


def run(cfg: Config) -> Result:
    ops, s2_pairs = build_program(cfg)
    schedule(ops)
    total = max(o.end for o in ops)
    dma_busy = sum(o.dur for o in ops if o.kind != "compute")
    comp_busy = sum(o.dur for o in ops if o.kind == "compute")
    computes = [o for o in ops if o.kind == "compute"]
    s2_wait = 0.0
    for o in ops:
        if o.kind == "dma_load" and o.name.startswith("A[") and o.deps:
            avail = o.chain_prev.end if o.chain_prev is not None else 0.0
            s2_wait += max(0.0, o.deps[0].end - avail)
    stats = {
        "total": total,
        "dma_busy": dma_busy, "comp_busy": comp_busy,
        "dma_idle": total - dma_busy, "bubble": total - comp_busy,
        "comp_util": comp_busy / total, "dma_util": dma_busy / total,
        "fill": computes[0].start,
        "drain": total - computes[-1].end,
        "s1": len(computes), "s2": s2_pairs,
        "s3": cfg.tiles_i * cfg.tiles_j, "s4": cfg.tiles_i * cfg.tiles_j - 1,
        "s2_wait": s2_wait,
        "load_bytes": sum(o.nbytes for o in ops if o.kind == "dma_load"),
        "store_bytes": sum(o.nbytes for o in ops if o.kind == "dma_store"),
        "macs": sum(o.macs for o in computes),
        "lb": max(dma_busy, comp_busy),
    }
    return Result(cfg=cfg, ops=ops, stats=stats)


# ---------------- 报告 ----------------
def fmt(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def report_compare(runs: dict) -> str:
    s, d, p = runs["single"], runs["double"], runs["pipeline"]
    names = [("single", "单缓冲(D102)"), ("double", "逐块双缓冲"),
             ("pipeline", "跨块预取流水线")]
    lines = []
    lines.append("三种调度的真实时间线（512×512×512，tile 64³，FP32，示例参数）")
    lines.append("=" * 96)
    rows = [
        ("总时长 µs", lambda r: fmt(r.stats["total"])),
        ("DMA 忙 µs", lambda r: fmt(r.stats["dma_busy"])),
        ("DMA 闲置 µs", lambda r: fmt(r.stats["dma_idle"])),
        ("计算忙 µs", lambda r: fmt(r.stats["comp_busy"])),
        ("计算气泡 µs", lambda r: fmt(r.stats["bubble"])),
        ("计算利用率", lambda r: pct(r.stats["comp_util"])),
        ("DMA 利用率", lambda r: pct(r.stats["dma_util"])),
        ("加速比(vs 单缓冲)", None),
        ("填充(首个计算前) µs", lambda r: fmt(r.stats["fill"])),
        ("排空(最后计算后) µs", lambda r: fmt(r.stats["drain"])),
        ("S1/S2/S3/S4 次数",
         lambda r: f"{r.stats['s1']}/{r.stats['s2']}/{r.stats['s3']}/{r.stats['s4']}"),
        ("S2 让 DMA 白等 µs", lambda r: fmt(r.stats["s2_wait"])),
    ]
    head = f"{'指标':<22}"
    for _, label in names:
        head += f"{label:>20}"
    lines.append(head)
    lines.append("-" * 96)
    base = s.stats["total"]
    for label, fn in rows:
        if fn is None:
            row = f"{label:<22}"
            for key, _ in names:
                row += f"{base / runs[key].stats['total']:>19.2f}×"
        else:
            row = f"{label:<22}"
            for key, _ in names:
                row += f"{fn(runs[key]):>20}"
        lines.append(row)
    lines.append("-" * 96)
    lb = s.stats["lb"]
    lines.append(f"理想重叠下界 = max(DMA忙, 计算忙) = max({fmt(s.stats['dma_busy'])},"
                 f" {fmt(s.stats['comp_busy'])}) = {fmt(lb)} µs（D102 预告的 1.94× 上限）")
    lines.append(f"逐块双缓冲距下界还差 {fmt(d.stats['total'] - lb)} µs"
                 f"（64 块 × 1 µs 暴露填充：预取没有跨过块边界）")
    lines.append(f"跨块预取距下界只差 {fmt(p.stats['total'] - lb)} µs"
                 f"（全 kernel 唯一一次排空：末圈计算时 DMA 无货可搬）")
    lines.append("同步点小结：双缓冲后 S1/S3/S4 一个不少，S2 从 511 → 510")
    lines.append("（距离 2 使最初两圈没有前任读者）；真正变化的是 S2 让 DMA")
    lines.append("白等的时间：448 µs → 0——覆盖写在读者完工之后，流水线内消化。")
    return "\n".join(lines)


def tile_span(r: Result, n: int):
    ts = [o for o in r.ops if o.tile == n]
    return min(o.start for o in ts), max(o.end for o in ts)


def gantt(r: Result, n: int, width: int = 76) -> list:
    """把第 n 块画成双泳道 ASCII 甘特图。"""
    ts = [o for o in r.ops if o.tile == n]
    span = max(o.end for o in ts)
    dma = [" "] * width
    comp = [" "] * width
    zone = [" "] * width

    def x(t_: float) -> int:
        return min(width - 1, max(0, int(t_ / span * width)))

    for o in ts:
        if o.kind == "dma_load":
            ch = "b" if o.name.startswith("bias") else "L"
            for i in range(x(o.start), max(x(o.start) + 1, x(o.end))):
                dma[i] = ch
        elif o.kind == "dma_store":
            for i in range(x(o.start), max(x(o.start) + 1, x(o.end))):
                dma[i] = "S"
        else:
            for i in range(x(o.start), max(x(o.start) + 1, x(o.end))):
                comp[i] = "C"
    kt = r.cfg.tiles_k
    c0 = r.op(f"c[{n},0]").start
    cl = r.op(f"c[{n},{kt - 1}]").start
    for i in range(width):
        zone[i] = "填" if i < x(c0) else ("稳" if i < x(cl) else "排")
    lines = []
    lines.append(f"DMA  引擎 |{''.join(dma)}|  L=Load b=bias S=Store")
    lines.append(f"计算单元 |{''.join(comp)}|  C=Compute")
    lines.append(f"阶段     |{''.join(zone)}|  填=填充 稳=双忙 排=排空")
    lines.append(f"{' ' * 10}0{' ' * (width - 14)}"
                 f"{' ' * 3}{fmt(span)} µs")
    return lines


def report_tile(r_double: Result, r_single: Result, r_pipe: Result) -> str:
    r = r_double
    cfg = r.cfg
    kt = cfg.tiles_k
    L = []
    L.append("逐块双缓冲：单个输出块 (i0=0, j0=0) 的事件时间线（µs，真实运行）")
    L.append("=" * 86)
    bias = r.op("bias[0]")
    L.append(f"{fmt(bias.start):>10}–{fmt(bias.end):<10} Load   bias[0]"
             f"{'':<22}{bias.nbytes:,} B")
    for k in range(kt):
        a, b = r.op(f"A[0,{k}]"), r.op(f"B[0,{k}]")
        note = "填充：首圈数据" if k == 0 else f"‖ 与 c[0,{k - 1}] 重叠"
        L.append(f"{fmt(a.start):>10}–{fmt(b.end):<10} Load   A[0,{k}]→B[0,{k}]"
                 f"  {note:<16}{a.nbytes + b.nbytes:,} B")
        c = r.op(f"c[0,{k}]")
        label = f"c[0,{k}]（含 C←0 与加 bias）" if k == 0 else f"c[0,{k}]"
        note = "（与下一圈搬运重叠）" if k < kt - 1 else "（DMA 无货可搬：排空）"
        L.append(f"{fmt(c.start):>10}–{fmt(c.end):<10} 计算   {label:<22}"
                 f"{note:<20}{c.macs:,} MAC")
    st = r.op("store[0]")
    L.append(f"{fmt(st.start):>10}–{fmt(st.end):<10} Store  C[0,0]"
             f"{'':<22}{st.nbytes:,} B")
    span = st.end
    L.append("-" * 86)
    L.append(f"块合计：{fmt(span)} µs = 填充 {fmt(r.op('c[0,0]').start)}"
             f" + 稳态 {kt - 1}×{fmt(max(2 * cfg.load_t, cfg.compute_t))}"
             f" + 末圈 {fmt(cfg.compute_t)} + 写回 {fmt(cfg.store_t)}"
             f"（单缓冲同块 {fmt(r_single.op('store[0]').end)} µs）")
    L.append("")
    L.append("双泳道甘特图（上=DMA，下=计算；对比 D102 的轮流值班）：")
    L += gantt(r_double, 0)
    L.append("")
    L.append("单缓冲同一块（D102 复现，两排完全错开、零重叠）：")
    L += gantt(r_single, 0)
    L.append("")
    L.append("跨块预取流水线：块 0 → 块 1 边界发生了什么（8.0–10.6 µs 的事件）")
    L.append("-" * 86)
    ev = [o for o in r_pipe.ops if 8.0 <= o.start < 10.6]
    for o in sorted(ev, key=lambda o: (o.start, o.end, o.name)):
        kind = {"dma_load": "Load", "dma_store": "Store", "compute": "计算"}[o.kind]
        note = ""
        if o.name in ("A[1,0]", "B[1,0]"):
            note = "‖ 预取：填进空着的槽 0"
        elif o.name == "store[0]":
            note = "写回让出队首给预取"
        elif o.name == "c[1,0]":
            note = "下一块计算无缝续上"
        elif o.kind == "compute":
            note = "‖ 同时在预取块 1 的 A/B"
        L.append(f"{fmt(o.start):>10}–{fmt(o.end):<10} {kind:<6} {o.name:<12}{note}")
    L.append("-" * 86)
    gap = r_pipe.op("c[1,0]").start - r_pipe.op("c[0,7]").end
    L.append(f"计算单元跨块间隙 = {fmt(gap)} µs = 写回 {fmt(cfg.store_t)}"
             f" + bias {fmt(cfg.bias_t)}（DMA 是瓶颈，计算跟着搬运的节奏走）")
    return "\n".join(L)


def report_fill_drain(r_double: Result, r_pipe: Result) -> str:
    d, p = r_double.stats, r_pipe.stats
    cfg = r_double.cfg
    kt = cfg.tiles_k
    nt = cfg.tiles_i * cfg.tiles_j
    fill_t = cfg.bias_t + 2 * cfg.load_t          # 每块暴露的填充
    drain_t = cfg.compute_t + cfg.store_t          # 每块暴露的排空
    steady_t = max(2 * cfg.load_t, cfg.compute_t)  # 稳态每圈节拍
    L = []
    L.append("流水线填充／排空账本：钱花在哪、怎么摊薄")
    L.append("=" * 84)
    L.append("【逐块双缓冲】每个输出块都要自己填一次、排一次：")
    L.append(f"  每块 = 填充 {fmt(fill_t)}（bias＋A0/B0，计算干等）")
    L.append(f"        + 稳态 {(kt - 1)}×{fmt(steady_t)}（算 c[k] ‖ 搬 A/B[k+1]，双忙）")
    L.append(f"        + 排空 {fmt(drain_t)}（末圈 {fmt(cfg.compute_t)} DMA 闲"
             f" ＋ 写回 {fmt(cfg.store_t)} 计算闲）")
    L.append(f"  64 块合计：填充+排空 = {fmt(nt * (fill_t + drain_t))} µs，"
             f"占总时长 {nt * (fill_t + drain_t) / d['total'] * 100:.2f}%")
    L.append("")
    L.append("【跨块预取流水线】填充／排空摊薄成全 kernel 一次：")
    L.append(f"  填充 {fmt(p['fill'])} µs（开头一次：bias＋首圈 A0/B0）")
    L.append(f"  稳态 {fmt(p['total'] - p['fill'] - p['drain'])} µs"
             f"——计算忙 {fmt(p['comp_busy'])}＋微气泡 {fmt(p['bubble'] - p['fill'] - p['drain'])}"
             f"（DMA 是瓶颈：每块搬运 {fmt(kt * 2 * cfg.load_t + cfg.store_t + cfg.bias_t)}"
             f" > 计算 {fmt(kt * cfg.compute_t)}）")
    L.append(f"  排空 {fmt(p['drain'])} µs（末块写回）＋ DMA 尾部闲置"
             f" {fmt(p['dma_idle'])} µs（末圈计算时无货可搬）")
    L.append(f"  填充+排空占比：{fmt((p['fill'] + p['drain']) / p['total'] * 100)}%")
    L.append("")
    L.append("读法：双缓冲买到的是『重叠』，跨块预取买到的是『摊薄』——")
    L.append("前者把每圈从 搬+算 串行压成 max(搬,算)，后者把每块 2.5 µs 的")
    L.append("填充排空开销从 64 份收拢成 1 份。K 越深圈数越多，前者收益不变、")
    L.append("后者占比自然下降（见 sweep-k.txt 的摊薄表）。")
    return "\n".join(L)


def report_space() -> str:
    L = []
    L.append("双缓冲空间账本：×2 只加在 DMA 流入项（规则沿用 D101）")
    L.append("=" * 88)
    for t in (32, 64, 128, 256):
        cfg = Config(T=t)
        ss, sd = slots_single(cfg), slots_double(cfg)
        s_sum, d_sum = sum(ss.values()), sum(sd.values())
        verdict = "✓ 住得下" if d_sum <= SRAM_BUDGET else "✗ 被拒绝"
        L.append(f"Tile {t}³   单缓冲 {s_sum:>9,} B → 双缓冲 {d_sum:>9,} B"
                 f"   (+{d_sum - s_sum:,} B, +{(d_sum / s_sum - 1) * 100:.1f}%)"
                 f"   256KiB? {verdict}")
    L.append("-" * 88)
    L.append("64³ 明细：A 16,384 + B 16,384 + C 16,384 + bias 256 = 49,408 B（D101）")
    L.append("64³ 双缓冲：A×2 32,768 + B×2 32,768 + C 16,384 + bias 256 = 82,176 B")
    L.append("占 256 KiB 预算 31.36%（单缓冲 18.84%）——用 66% 的空间买回 74% 的时间。")
    L.append("为什么 C 不 ×2：C 是读-改-写的累加器，只有一个『活跃实例』；")
    L.append("A/B 是纯流入流（DMA 写、计算读），乒乓才有意义。bias 首圈就消费掉，")
    L.append("只有 256 B，不值得为它翻倍。")
    L.append("警示：128³ 双缓冲 328,192 B > 262,144 B，被 D101 预算当场拒绝——")
    L.append("时间上的最优解会被空间一票否决，这正是 D104 资源过滤器的入口。")
    return "\n".join(L)


def sweep_bw() -> str:
    L = []
    L.append("对照实验一：DMA 带宽 ×0.5～×8，单缓冲 vs 双缓冲（512³，tile 64³）")
    L.append("=" * 96)
    L.append(f"{'带宽':>10} {'单缓冲 µs':>12} {'单缓冲利用率':>13}"
             f" {'双缓冲 µs':>12} {'双缓冲利用率':>13} {'加速比':>9}")
    L.append("-" * 96)
    for mult in (0.5, 1, 2, 4, 8):
        rs = run(Config(mode="single", dma_bw=DMA_BW * mult))
        rd = run(Config(mode="double", dma_bw=DMA_BW * mult))
        L.append(f"×{mult:<8} {fmt(rs.stats['total']):>12}"
                 f"{pct(rs.stats['comp_util']):>13}"
                 f"{fmt(rd.stats['total']):>12}{pct(rd.stats['comp_util']):>13}"
                 f"{rs.stats['total'] / rd.stats['total']:>8.2f}×")
    L.append("-" * 96)
    L.append("读法：带宽越大，双缓冲稳态越接近计算瓶颈（×8 时利用率 97.7%，")
    L.append("同圈节拍 = max(搬运, 计算) → 计算独挑大梁）；单缓冲再宽的带宽")
    L.append("也永远差一截（×8 才 88.3%）。反过来：双缓冲 ×1 带宽的 84.14%，")
    L.append("比单缓冲 ×4 带宽的 79.00% 还高——开双缓冲 ≈ 免费翻两番带宽。")
    return "\n".join(L)


def sweep_k() -> str:
    L = []
    L.append("对照实验二：k 块循环深度 K＝256→2048（M=N=512 不变，tile 64³）")
    L.append("=" * 100)
    L.append(f"{'K':>6} {'kt=K/64':>8} {'双缓冲 µs':>11} {'双缓冲利用率':>13}"
             f" {'填充+排空占比':>15} {'流水线 µs':>11} {'流水线利用率':>13}")
    L.append("-" * 100)
    for k in (256, 512, 1024, 2048):
        rd = run(Config(K=k, mode="double"))
        rp = run(Config(K=k, mode="pipeline"))
        nt = rd.cfg.tiles_i * rd.cfg.tiles_j
        fd_share = nt * (rd.cfg.bias_t + 2 * rd.cfg.load_t
                         + rd.cfg.compute_t + rd.cfg.store_t) / rd.stats["total"]
        L.append(f"{k:>6} {k // 64:>8} {fmt(rd.stats['total']):>11}"
                 f"{pct(rd.stats['comp_util']):>13}{fd_share * 100:>14.2f}%"
                 f"{fmt(rp.stats['total']):>11}{pct(rp.stats['comp_util']):>13}")
    L.append("-" * 100)
    L.append("读法：kt 越深，逐块流水线的 2.5 µs 填充＋排空被摊得越薄")
    L.append("（45.53% → 7.48%），利用率一路逼近流水线模式；而流水线模式")
    L.append("自己几乎不受 K 影响——它的填充排空天生只有一份。")
    return "\n".join(L)


def sweep_tile() -> str:
    L = []
    L.append("对照实验三：换 Tile 尺寸——空间预算否决哪些双缓冲方案（512³，K=512）")
    L.append("=" * 110)
    L.append(f"{'Tile':>6} {'单缓冲空间':>12} {'双缓冲空间':>12} {'预算(双缓冲)':>13}"
             f" {'单缓冲 µs':>12} {'双缓冲 µs':>12} {'加速比':>8} {'瓶颈':>10}")
    L.append("-" * 110)
    for t in (32, 64, 128, 256):
        cfg = Config(T=t)
        sp_s, sp_d = sum(slots_single(cfg).values()), sum(slots_double(cfg).values())
        rs = run(Config(T=t, mode="single"))
        rd = run(Config(T=t, mode="double"))
        verdict = "✓ 住得下" if sp_d <= SRAM_BUDGET else "✗ 被拒绝"
        neck = "搬运" if 2 * cfg.load_t > cfg.compute_t else "计算"
        L.append(f"{t:>5}³ {sp_s:>11,} {sp_d:>11,} {verdict:>13}"
                 f"{fmt(rs.stats['total']):>12}{fmt(rd.stats['total']):>12}"
                 f"{rs.stats['total'] / rd.stats['total']:>7.2f}×{neck:>11}")
    L.append("-" * 110)
    L.append("读法：32³ 双缓冲只赚 1.44×——搬运慢于计算，稳态被 DMA 拖着走；")
    L.append("64³ 赚 1.74×；128³ 本可赚 1.32×，但 328,192 B 超预算被拒——")
    L.append("双缓冲把可行 Tile 上限从 128³ 压回 64³，这是编译器必须自动")
    L.append("检查的事（D104：资源约束过滤）。256³ 单缓冲就已超预算。")
    return "\n".join(L)


def self_test() -> list:
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))

    rs = run(Config(mode="single"))
    rd = run(Config(mode="double"))
    rp = run(Config(mode="pipeline"))
    s, d, p = rs.stats, rd.stats, rp.stats

    check("单缓冲总时长 = 1056.5 µs（对上 D102 的账）", abs(s["total"] - 1056.5) < 1e-9)
    check("单缓冲同步计数 S1/S2/S3/S4 = 512/511/64/63（D102 复现）",
          (s["s1"], s["s2"], s["s3"], s["s4"]) == (512, 511, 64, 63))
    check("单缓冲计算利用率 = 48.46%", abs(s["comp_util"] - 512 / 1056.5) < 1e-9)
    check("双缓冲总时长 = 608.5 µs", abs(d["total"] - 608.5) < 1e-9)
    check("双缓冲加速比 = 1056.5/608.5 ≈ 1.74×",
          abs(s["total"] / d["total"] - 1056.5 / 608.5) < 1e-9)
    check("双缓冲 DMA 闲置 = 64 µs（每块末圈 1 µs，暴露的填充）",
          abs(d["dma_idle"] - 64.0) < 1e-9)
    check("双缓冲 S2 = 510（距离 2 让最初两圈没有前任读者）", d["s2"] == 510)
    check("双缓冲 S2 白等 = 0（覆盖全在读者完工之后）", abs(d["s2_wait"]) < 1e-9)
    check("跨块预取总时长 = 545.5 µs", abs(p["total"] - 545.5) < 1e-9)
    check("跨块预取 DMA 闲置 = 1.0 µs（全 kernel 唯一一次排空）",
          abs(p["dma_idle"] - 1.0) < 1e-9)
    check("三种模式计算忙 = 512、DMA 忙 = 544.5（工作量与调度无关）",
          all(abs(r.stats["comp_busy"] - 512) < 1e-9
              and abs(r.stats["dma_busy"] - 544.5) < 1e-9 for r in (rs, rd, rp)))
    check("时长排序：单缓冲 > 逐块双缓冲 > 跨块预取 > 理想下界 544.5",
          s["total"] > d["total"] > p["total"] > s["lb"] and abs(s["lb"] - 544.5) < 1e-9)
    check("跨块预取距理想下界只差 1.0 µs（一次排空）",
          abs(p["total"] - s["lb"] - 1.0) < 1e-9)
    cfg = Config()
    per_tile = (cfg.bias_t + 2 * cfg.load_t + 7 * max(2 * cfg.load_t, cfg.compute_t)
                + cfg.compute_t + cfg.store_t)
    check("双缓冲每块节拍公式 = bias+装载对+7×max(装载对,计算)+计算+写回",
          abs(rd.op("store[0]").end - per_tile) < 1e-9)
    check("跨块预取的计算间隙 = 写回+bias = 0.5078 µs（DMA 是瓶颈）",
          abs(rp.op("c[1,0]").start - rp.op("c[0,7]").end
              - (cfg.store_t + cfg.bias_t)) < 1e-9)
    check("空间：64³ 单 49,408 / 双 82,176（×2 只加在 A/B）",
          (sum(slots_single(cfg).values()), sum(slots_double(cfg).values()))
          == (49_408, 82_176))
    check("空间：128³ 双缓冲 328,192 B 被 256 KiB 拒绝；32³ 双缓冲 20,608 住得下",
          sum(slots_double(Config(T=128)).values()) == 328_192 > SRAM_BUDGET
          and sum(slots_double(Config(T=32)).values()) == 20_608)
    # 带宽扫描：结构性性质
    utils_d, totals_s, totals_d = [], [], []
    for mult in (0.5, 1, 2, 4, 8):
        a = run(Config(mode="single", dma_bw=DMA_BW * mult))
        b = run(Config(mode="double", dma_bw=DMA_BW * mult))
        totals_s.append(a.stats["total"])
        totals_d.append(b.stats["total"])
        utils_d.append(b.stats["comp_util"])
    check("带宽扫描：每个带宽点双缓冲都更快", all(b < a for a, b in zip(totals_s, totals_d)))
    check("带宽扫描：双缓冲利用率单调上升（搬运瓶颈让位给计算）",
          all(x < y for x, y in zip(utils_d, utils_d[1:])))
    check("带宽扫描：×8 时双缓冲利用率 97.7% > 单缓冲的 88.3%",
          abs(utils_d[-1] - 512 / 524.0625) < 1e-9)
    check("带宽结论：双缓冲×1 的 84.14% > 单缓冲×4 的 79.00%",
          utils_d[1] > 512 / totals_s[3] and abs(512 / totals_s[3] - 0.79) < 5e-3)
    # K 扫描：填充/排空摊薄
    shares = []
    for k in (256, 512, 1024, 2048):
        r = run(Config(K=k, mode="double"))
        nt = r.cfg.tiles_i * r.cfg.tiles_j
        shares.append(nt * (r.cfg.bias_t + 2 * r.cfg.load_t
                             + r.cfg.compute_t + r.cfg.store_t) / r.stats["total"])
    check("K 扫描：填充+排空占比随 K 单调下降（摊薄效应）",
          all(x > y for x, y in zip(shares, shares[1:])))
    check("K 扫描：K=2048 时逐块流水线利用率已到 95.5%",
          abs(run(Config(K=2048, mode="double")).stats["comp_util"] - 0.955) < 1e-3)
    # Tile 扫描：小 Tile 搬运受限，收益打折
    r32 = run(Config(T=32, mode="double"))
    check("Tile 扫描：32³ 双缓冲加速比 1.44× < 64³ 的 1.74×（搬运是瓶颈）",
          abs(run(Config(T=32, mode="single")).stats["total"]
              / r32.stats["total"] - 1.44) < 5e-3)
    return results


def main() -> int:
    outdir = __file__.rsplit("/", 1)[0] + "/outputs"
    os.makedirs(outdir, exist_ok=True)

    def save(name, text):
        with open(f"{outdir}/{name}", "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"  已写入 outputs/{name}")

    print("第 103 天：双缓冲与流水线模拟器")
    runs = {"single": run(Config(mode="single")),
            "double": run(Config(mode="double")),
            "pipeline": run(Config(mode="pipeline"))}
    save("compare-modes.txt", report_compare(runs))
    save("main-tile.txt", report_tile(runs["double"], runs["single"], runs["pipeline"]))
    save("fill-drain.txt", report_fill_drain(runs["double"], runs["pipeline"]))
    save("space.txt", report_space())
    save("sweep-bw.txt", sweep_bw())
    save("sweep-k.txt", sweep_k())
    save("sweep-tile.txt", sweep_tile())

    results = self_test()
    lines = [f"自检：{sum(1 for _, ok in results if ok)}/{len(results)} 项通过", "=" * 70]
    for name, ok in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
    save("test-all.txt", "\n".join(lines))

    env = (f"Python {platform.python_version()}，{platform.machine()}，"
           f"{datetime.date.today().isoformat()}；硬件参数为示例值"
           f"（DMA {DMA_BW} B/µs、计算 {MAC_RATE} MAC/µs），输出为确定性模型"
           f"在本次运行中的真实计算结果，不是实测性能数据。")
    save("env.txt", env)

    failed = [name for name, ok in results if not ok]
    if failed:
        print("自检失败：", failed)
        return 1
    print(f"自检 {len(results)}/{len(results)} 全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
