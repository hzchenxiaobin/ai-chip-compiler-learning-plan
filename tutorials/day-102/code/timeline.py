#!/usr/bin/env python3
"""第 102 天：单缓冲 Tiled MatMul 执行时间线模拟器。

模型说明
--------
把一个 Tiled MatMul kernel（C = A·B + bias，A/B/C 均在 HBM，Tile 在 SRAM）
在"单缓冲、单 DMA 引擎、单计算单元"假设下逐事件排时间线：

  每个输出块 (i0, j0)：
    bias load → [ A(k0) load → B(k0) load → S1:等搬运 → compute(k0) → S2:等计算 ] × Kt
              → S3:等累加完 → store C → S4:等写回完（C 槽才许给下一个块用）

同步点四类：
  S1  RAW  搬运 → 计算   ：算的是刚搬来的数据，必须等 DMA 写完 SRAM 槽
  S2  WAR  计算 → 搬运   ：下一块 load 要覆盖 A/B 槽，必须等计算读完
  S3  RAW  计算 → 写回   ：store 读的是最后一次累加的结果
  S4  WAR  写回 → 下块   ：store 还在读 C 槽时，不许复用/覆写它

硬件参数是"示例值"（不代表任何具体芯片），本程序的输出是这些参数下
确定性模型的真实计算结果，不是实测性能数据。
"""

from __future__ import annotations

import datetime
import platform
import sys
from dataclasses import dataclass, field

# ---------------- 示例硬件参数（µs / Byte / MAC 单位） ----------------
DMA_BW = 32_768.0        # DMA 带宽，Byte/µs（32.768 GB/s，示例值）
MAC_RATE = 262_144.0     # 计算吞吐，MAC/µs（0.262 TMAC/s，示例值）
SRAM_BUDGET = 262_144    # 片上 SRAM 预算，256 KiB（沿用第 101 天）
ALIGN = 32               # DMA 对齐，Byte
DTYPE_IN = 4             # FP32 输入，Byte/元素
DTYPE_ACC = 4             # FP32 累加（低精度输入也按 4B 记，D101 规则）


def align_up(x: int, a: int = ALIGN) -> int:
    return (x + a - 1) // a * a


# ---------------- 事件 ----------------
@dataclass
class Op:
    kind: str            # dma_load | dma_store | compute | sync
    name: str
    start: float = 0.0
    end: float = 0.0
    nbytes: int = 0
    macs: int = 0
    sync: str = ""       # S1 | S2 | S3 | S4
    deptype: str = ""    # RAW | WAR | ""
    waits: float = 0.0   # 同步等待时长（µs）
    note: str = ""


@dataclass
class Config:
    M: int = 512
    N: int = 512
    K: int = 512
    T: int = 64
    dma_bw: float = DMA_BW
    mac_rate: float = MAC_RATE

    @property
    def tiles_i(self) -> int:
        return self.M // self.T

    @property
    def tiles_j(self) -> int:
        return self.N // self.T

    @property
    def tiles_k(self) -> int:
        return self.K // self.T


def slots(cfg: Config) -> dict:
    """单缓冲下一个输出块的 SRAM 家当（逐项对齐，规则沿用 D101）。"""
    t = cfg.T
    return {
        "A[Tm×Tk]": align_up(t * t * DTYPE_IN),
        "B[Tk×Tn]": align_up(t * t * DTYPE_IN),
        "C[Tm×Tn]": align_up(t * t * DTYPE_ACC),
        "bias[Tn]": align_up(t * DTYPE_ACC),
    }


def simulate(cfg: Config, tiles_to_trace: int = 1):
    """按程序顺序排单缓冲时间线。返回（全部事件, 统计）。"""
    t = cfg.T
    a_bytes = align_up(t * t * DTYPE_IN)
    c_bytes = align_up(t * t * DTYPE_ACC)
    bias_bytes = align_up(t * DTYPE_ACC)
    load_t = a_bytes / cfg.dma_bw          # A、B 块各一次搬运
    compute_t = (t ** 3) / cfg.mac_rate
    store_t = c_bytes / cfg.dma_bw
    bias_t = bias_bytes / cfg.dma_bw

    ops: list[Op] = []
    now = 0.0
    dma_free = 0.0
    comp_free = 0.0
    sync_count = {"S1": 0, "S2": 0, "S3": 0, "S4": 0}
    trace_ops: list[list[Op]] = []

    for ti in range(cfg.tiles_i):
        for tj in range(cfg.tiles_j):
            tile_ops: list[Op] = []

            def emit(op: Op):
                ops.append(op)
                if len(trace_ops) < tiles_to_trace:
                    tile_ops.append(op)

            # bias 切片（写 bias 槽；上一块计算已读完，WAR 在程序顺序下已满足）
            s = max(now, dma_free)
            emit(Op("dma_load", f"bias[{tj}]", s, s + bias_t, bias_bytes))
            dma_free = s + bias_t
            now = dma_free

            for k in range(cfg.tiles_k):
                # S2：发起新的 A/B load 前，等计算读完上一个 A/B 槽（WAR）
                if k > 0 or (k == 0 and (ti, tj) != (0, 0)):
                    wait = max(0.0, comp_free - now)
                    emit(Op("sync", "S2: 等计算完成，才许覆盖 A/B 槽",
                            now, now, sync="S2", deptype="WAR", waits=wait))
                    sync_count["S2"] += 1
                    now = max(now, comp_free)
                s = max(now, dma_free)
                emit(Op("dma_load", f"A[{ti},{k}]", s, s + load_t, a_bytes))
                dma_free = s + load_t
                s = dma_free
                emit(Op("dma_load", f"B[{k},{tj}]", s, s + load_t, a_bytes))
                dma_free = s + load_t
                now = dma_free
                # S1：计算前等本圈两个 load 完成（RAW）
                wait = max(0.0, now - comp_free)
                emit(Op("sync", f"S1: 等搬运完成（k={k}）",
                        now, now, sync="S1", deptype="RAW", waits=wait))
                sync_count["S1"] += 1
                s = max(now, comp_free)
                label = f"compute k={k}" + ("（含 C←0 与加 bias）" if k == 0 else "")
                emit(Op("compute", label, s, s + compute_t, macs=t ** 3))
                comp_free = s + compute_t
                now = comp_free

            # S3：最后一次累加完成后才许发起写回（RAW，程序顺序天然满足）
            emit(Op("sync", "S3: 等累加完成，才许写回 C",
                    now, now, sync="S3", deptype="RAW", waits=0.0))
            sync_count["S3"] += 1
            s = max(now, dma_free)
            emit(Op("dma_store", f"C[{ti},{tj}]", s, s + store_t, c_bytes))
            dma_free = s + store_t
            now = dma_free
            # S4：等写回完成，C 槽才许交给下一个输出块（WAR）
            if (ti, tj) != (cfg.tiles_i - 1, cfg.tiles_j - 1):
                emit(Op("sync", "S4: 等写回完成，C 槽才许复用",
                        now, now, sync="S4", deptype="WAR", waits=0.0))
                sync_count["S4"] += 1
            if len(trace_ops) < tiles_to_trace or len(trace_ops) == tiles_to_trace:
                trace_ops.append(tile_ops) if tile_ops and len(trace_ops) < tiles_to_trace else None

    total = now
    dma_busy = sum(o.end - o.start for o in ops if o.kind in ("dma_load", "dma_store"))
    comp_busy = sum(o.end - o.start for o in ops if o.kind == "compute")
    stats = {
        "total": total,
        "dma_busy": dma_busy,
        "comp_busy": comp_busy,
        "comp_util": comp_busy / total,
        "dma_util": dma_busy / total,
        "bubble": total - comp_busy,
        "syncs": sync_count,
        "load_bytes": sum(o.nbytes for o in ops if o.kind == "dma_load"),
        "store_bytes": sum(o.nbytes for o in ops if o.kind == "dma_store"),
        "macs_total": sum(o.macs for o in ops if o.kind == "compute"),
        "load_t": load_t, "compute_t": compute_t,
        "store_t": store_t, "bias_t": bias_t,
        "ideal_overlap_lb": max(dma_busy, comp_busy),
    }
    return ops, stats, trace_ops


# ---------------- 报告 ----------------
def fmt(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def report_tile(trace_ops, stats) -> str:
    lines = []
    lines.append("单个输出块 (i0=0, j0=0) 的单缓冲时间线（时间单位 µs）")
    lines.append("=" * 78)
    lines.append(f"{'时间':>16}  {'类型':<9} {'事件':<34} {'说明'}")
    lines.append("-" * 78)
    for o in trace_ops[0]:
        if o.kind == "sync":
            lines.append(f"[{fmt(o.start):>7}]  {o.sync:<4} {o.deptype:<3} {o.name:<36}"
                         f"等待 {fmt(o.waits)} µs")
        elif o.kind == "compute":
            lines.append(f"{fmt(o.start):>8}–{fmt(o.end):<7}  {'计算':<6} {o.name:<34}"
                         f"{o.macs:,} MAC")
        else:
            tag = "Load" if o.kind == "dma_load" else "Store"
            lines.append(f"{fmt(o.start):>8}–{fmt(o.end):<7}  {tag:<6} {o.name:<34}"
                         f"{o.nbytes:,} B")
    lines.append("-" * 78)
    lines.append(f"块合计：{fmt(stats['load_t'] * 16 + stats['bias_t'] + stats['store_t'] + stats['compute_t'] * 8)}"
                 f" µs = bias {fmt(stats['bias_t'])} + 8×(Load {fmt(stats['load_t'] * 2)}"
                 f" + Compute {fmt(stats['compute_t'])}) + Store {fmt(stats['store_t'])}")
    return "\n".join(lines)


def report_kernel(stats, cfg) -> str:
    s = stats
    lines = []
    lines.append(f"整个 kernel（{cfg.M}×{cfg.N}×{cfg.K}，tile {cfg.T}³，FP32）单缓冲执行统计")
    lines.append("=" * 78)
    lines.append(f"输出块数：{cfg.tiles_i}×{cfg.tiles_j} = {cfg.tiles_i * cfg.tiles_j}"
                 f"，k 块循环总圈数：{cfg.tiles_i * cfg.tiles_j * cfg.tiles_k}")
    lines.append(f"总时长        ：{fmt(s['total'])} µs")
    lines.append(f"DMA 忙        ：{fmt(s['dma_busy'])} µs（利用率 {s['dma_util'] * 100:.2f}%）")
    lines.append(f"计算忙        ：{fmt(s['comp_busy'])} µs（利用率 {s['comp_util'] * 100:.2f}%）")
    lines.append(f"计算空等气泡  ：{fmt(s['bubble'])} µs（占总时长 {s['bubble'] / s['total'] * 100:.2f}%）")
    lines.append(f"Load 总字节   ：{s['load_bytes']:,} B（{s['load_bytes'] / 1048576:.1f} MiB）")
    lines.append(f"Store 总字节  ：{s['store_bytes']:,} B（{s['store_bytes'] / 1048576:.1f} MiB）")
    lines.append(f"总 MAC 数     ：{s['macs_total']:,}")
    lines.append("")
    lines.append("同步点统计（单缓冲时间线上必须插入的等待）：")
    sc = s["syncs"]
    lines.append(f"  S1 RAW  搬运→计算 ：{sc['S1']:>5} 次（每圈 k 各一次）")
    lines.append(f"  S2 WAR  计算→搬运 ：{sc['S2']:>5} 次（覆盖 A/B 槽之前）")
    lines.append(f"  S3 RAW  计算→写回 ：{sc['S3']:>5} 次（每块一次）")
    lines.append(f"  S4 WAR  写回→复用 ：{sc['S4']:>5} 次（C 槽交给下一块前）")
    lines.append(f"  合计           ：{sum(sc.values()):>5} 次")
    lines.append("")
    lines.append("串行化代价与重叠下界（D103 的账，今天先量出来）：")
    lines.append(f"  理想重叠下界 = max(DMA忙, 计算忙) = max({fmt(s['dma_busy'])},"
                 f" {fmt(s['comp_busy'])}) = {fmt(s['ideal_overlap_lb'])} µs")
    lines.append(f"  单缓冲多花 = {fmt(s['total'] - s['ideal_overlap_lb'])} µs；"
                 f"潜在加速比 ≈ {s['total'] / s['ideal_overlap_lb']:.2f}×")
    return "\n".join(lines)


def report_deps() -> str:
    lines = []
    lines.append("依赖与同步对照表：谁依赖谁、为什么、靠什么同步")
    lines.append("=" * 96)
    lines.append(f"{'依赖类型':<10}{'发生在':<26}{'资源':<14}{'原因':<30}{'同步手段'}")
    lines.append("-" * 96)
    rows = [
        ("RAW 真依赖", "Load A/B(k) → Compute(k)", "A/B 槽(SRAM)", "算的是刚搬来的数据", "S1：等 DMA 完成通知"),
        ("RAW 真依赖", "Compute(k) → Compute(k+1)", "C 槽(SRAM)", "部分和逐圈累加，读上一圈写的 C", "S1 之后程序顺序（同一单元）"),
        ("WAR 反依赖", "Compute(k) → Load A/B(k+1)", "A/B 槽(SRAM)", "新搬运会覆盖还没读完的块", "S2：等计算完成再发起"),
        ("RAW 真依赖", "Compute(末圈) → Store C", "C 槽(SRAM)", "写回的是最终累加结果", "S3：等累加完成"),
        ("WAR 反依赖", "Store C(本块) → C←0(下块)", "C 槽(SRAM)", "下块初始化会覆盖待写回数据", "S4：等写回完成"),
        ("WAW 输出依赖", "Store X → 写 Y（同一段 HBM）", "HBM workspace", "D100 复用：两个写必须有序", "DMA 引擎按提交顺序执行"),
    ]
    for r in rows:
        lines.append(f"{r[0]:<12}{r[1]:<28}{r[2]:<14}{r[3]:<32}{r[4]}")
    lines.append("-" * 96)
    lines.append("关键结论：单缓冲把 S2（WAR）变成硬等待，Load 与 Compute 只能轮流做，")
    lines.append("这是时间线上一半时间在空等的根源；解法是给槽位×2（D103 双缓冲）。")
    return "\n".join(lines)


def sweep_dma(cfg: Config) -> str:
    lines = []
    lines.append("对照实验一：把 DMA 带宽翻倍再翻倍，单缓冲时间线会怎样？")
    lines.append("=" * 84)
    lines.append(f"{'DMA 带宽':>14} {'每圈 Load':>10} {'每圈 Compute':>12}"
                 f" {'总时长 µs':>12} {'计算利用率':>12} {'气泡占比':>10}")
    lines.append("-" * 84)
    for mult in (0.5, 1, 2, 4, 8):
        c = Config(**{**cfg.__dict__, "dma_bw": DMA_BW * mult})
        _, s, _ = simulate(c)
        lines.append(f"{'×' + str(mult) + '（' + fmt(c.dma_bw) + ' B/µs）':>16}"
                     f"{fmt(s['load_t'] * 2):>10}{fmt(s['compute_t']):>12}"
                     f"{fmt(s['total']):>12}{s['comp_util'] * 100:>11.2f}%"
                     f"{s['bubble'] / s['total'] * 100:>9.2f}%")
    lines.append("-" * 84)
    lines.append("读法：带宽越大气泡越小，但利用率永远到不了 100%——")
    lines.append("只要 Load 和 Compute 共用一个槽，S2（WAR）就强迫它们串行。")
    return "\n".join(lines)


def sweep_tile() -> str:
    lines = []
    lines.append("对照实验二：换 Tile 尺寸——搬运字节、利用率与 SRAM 预算（D101）")
    lines.append("=" * 100)
    lines.append(f"{'Tile':>6} {'空间(单缓冲)':>14} {'256KiB?':>9} {'Load MiB':>10}"
                 f" {'计算利用率':>11} {'总时长 µs':>12} {'算术强度 MAC/B':>16}")
    lines.append("-" * 100)
    for t in (32, 64, 128, 256):
        c = Config(T=t)
        sp = sum(slots(c).values())
        _, s, _ = simulate(c)
        fits = "✓ 住得下" if sp <= SRAM_BUDGET else "✗ 被拒绝"
        lines.append(f"{t:>6}³ {sp:>12,} B {fits:>10}{s['load_bytes'] / 1048576:>10.1f}"
                     f"{s['comp_util'] * 100:>10.2f}%{fmt(s['total']):>13}"
                     f"{t / 8:>14.0f}")
    lines.append("-" * 100)
    lines.append("读法：Tile 每翻一倍，算术强度翻倍（T³ MAC 摊到 8T² B 上），利用率明显上升，")
    lines.append("但 SRAM 预算（D101）把 256³ 直接拒之门外——空间和时间在这里握手。")
    return "\n".join(lines)


def ascii_timeline(trace_ops, stats) -> str:
    """把第一个输出块画成 ASCII 甘特图：上排 DMA，下排计算。"""
    s = stats
    total = trace_ops[0][-1].end
    width = 76
    dma = [" "] * width
    comp = [" "] * width
    marks = [" "] * width

    def x(t_: float) -> int:
        return int(t_ / total * width)

    for o in trace_ops[0]:
        if o.kind == "dma_load" or o.kind == "dma_store":
            row = dma
            ch = "L"
            if "bias" in o.name:
                ch = "b"
            if o.kind == "dma_store":
                ch = "S"
            for i in range(x(o.start), max(x(o.start) + 1, x(o.end))):
                row[i] = ch
        elif o.kind == "compute":
            for i in range(x(o.start), max(x(o.start) + 1, x(o.end))):
                comp[i] = "C"
        elif o.kind == "sync":
            i = x(o.start)
            if 0 <= i < width:
                marks[i] = "!"
    lines = []
    lines.append("单缓冲时间线（一个输出块，! = 必须同步的位置）")
    lines.append("")
    lines.append(f"DMA  引擎 |{''.join(dma)}|  L=Load b=bias S=Store")
    lines.append(f"计算单元 |{''.join(comp)}|  C=Compute")
    lines.append(f"同步点   |{''.join(marks)}|")
    lines.append(f"{' ' * 10}0{' ' * (width - 12)}{fmt(total)} µs")
    lines.append("")
    lines.append("DMA 与计算完全错开：一排搬运时另一排在等——每圈 Load "
                 f"{fmt(s['load_t'] * 2)} µs + Compute {fmt(s['compute_t'])} µs，"
                 "没有任何重叠。")
    return "\n".join(lines)


def self_test() -> list:
    """断言式自检，返回 (名称, 是否通过) 列表。"""
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))

    cfg = Config()
    ops, s, _ = simulate(cfg)
    sc = s["syncs"]

    check("串行不变式：总时长 = DMA忙 + 计算忙（单缓冲无重叠）",
          abs(s["total"] - (s["dma_busy"] + s["comp_busy"])) < 1e-9)
    check("利用率公式：计算利用率 = 计算忙 / 总时长",
          abs(s["comp_util"] - s["comp_busy"] / s["total"]) < 1e-12)
    check("主例总时长 = 1056.5 µs（64 块 × 16.5078125）",
          abs(s["total"] - 1056.5) < 1e-9)
    check("S1（RAW 搬运→计算）次数 = 每圈一次 = 512",
          sc["S1"] == 512)
    check("S2（WAR 计算→搬运）次数 = 511（相邻 k 圈 + 跨块首圈）",
          sc["S2"] == 511)
    check("S3（RAW 计算→写回）次数 = 每块一次 = 64", sc["S3"] == 64)
    check("S4（WAR 写回→复用）次数 = 块间 = 63", sc["S4"] == 63)
    check("理想重叠下界严格小于单缓冲总时长",
          s["ideal_overlap_lb"] < s["total"] - 1)
    check("稳态节拍：每圈 = Load 1.0 + Compute 1.0 = 2.0 µs",
          abs(s["load_t"] * 2 + s["compute_t"] - 2.0) < 1e-9)
    check("总 MAC 数 = 512³ = 134,217,728", s["macs_total"] == 512 ** 3)

    # DMA 倍速：总时长单调下降，利用率单调上升但 < 100%
    utils = []
    for mult in (0.5, 1, 2, 4, 8):
        _, s2, _ = simulate(Config(dma_bw=DMA_BW * mult))
        utils.append(s2["comp_util"])
    check("DMA 倍速扫描：利用率单调上升", all(a < b for a, b in zip(utils, utils[1:])))
    check("DMA 带宽×8 后计算利用率仍 < 100%（单缓冲天花板）", utils[-1] < 1.0)
    check("每圈时长与带宽无关地等于 Load+Compute（串行）",
          abs(utils[0] - 512 / (512 + 1024 + 64 + 1)) < 1e-9)

    # Tile 扫描：空间与利用率
    sp128 = sum(slots(Config(T=128)).values())
    sp256 = sum(slots(Config(T=256)).values())
    check("128³ 单缓冲空间 = 197,120 B ≤ 256 KiB（D101 结论）", sp128 == 197_120)
    check("256³ 单缓冲空间 = 787,456 B > 256 KiB，被预算拒绝", sp256 == 787_456)
    _, s32, _ = simulate(Config(T=32))
    _, s128, _ = simulate(Config(T=128))
    check("Tile 越大利用率越高：32³ < 64³ < 128³",
          s32["comp_util"] < s["comp_util"] < s128["comp_util"])
    check("A/B 块搬运字节随 Tile 翻倍减半（含 bias 切片）："
          "33,587,200 → 16,793,600 → 8,396,800",
          (s32["load_bytes"], s["load_bytes"], s128["load_bytes"])
          == (33_587_200, 16_793_600, 8_396_800))

    return results


def main() -> int:
    outdir = __file__.rsplit("/", 1)[0] + "/outputs"
    import os
    os.makedirs(outdir, exist_ok=True)
    cfg = Config()

    ops, s, trace = simulate(cfg, tiles_to_trace=1)

    def save(name, text):
        with open(f"{outdir}/{name}", "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"  已写入 outputs/{name}")

    print("第 102 天：单缓冲时间线模拟器")
    save("main-tile.txt", report_tile(trace, s))
    save("kernel-totals.txt", report_kernel(s, cfg))
    save("deps.txt", report_deps())
    save("ascii-timeline.txt", ascii_timeline(trace, s))
    save("sweep-dma.txt", sweep_dma(cfg))
    save("sweep-tile.txt", sweep_tile())

    results = self_test()
    lines = [f"自检：{sum(1 for _, ok in results if ok)}/{len(results)} 项通过", "=" * 70]
    for name, ok in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
    save("test-all.txt", "\n".join(lines))

    env = (f"Python {platform.python_version()}，{platform.machine()}，"
           f"{datetime.date.today().isoformat()}；模型参数为示例值，"
           f"输出为确定性模型在本次运行中的真实计算结果。")
    save("env.txt", env)

    failed = [name for name, ok in results if not ok]
    if failed:
        print("自检失败：", failed)
        return 1
    print(f"自检 {len(results)}/{len(results)} 全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
