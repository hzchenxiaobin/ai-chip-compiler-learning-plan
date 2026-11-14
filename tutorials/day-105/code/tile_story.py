#!/usr/bin/env python3
"""第 105 天（第 15 周复盘）：一个 Tile 的一生——从片外加载到结果写回。

把第 15 周的六件工具串成一条线，完整讲述输出块 C[0,0] 的旅程：
  第一幕（编译期·图级）  D99 活跃区间 → D100 片外工作区（t 的房间在哪）
  第二幕（编译期·闸门）  D101 空间账本 → D104 资源过滤（64³ 过闸，128³ 被拒）
  第三幕（运行期·块级）  D102 搬运与依赖 → D103 双缓冲流水线（事件级时间线）
  第四幕（汇总）          三种模式的内核总账，并与 D103 已发布数字对账

模型与参数沿用本周约定：512³ fp32 MatMul（bias 融合进 k=0 圈），
tile 64³，DMA 32,768 B/µs，计算 262,144 MAC/µs，SRAM 预算 256 KiB，
DMA 对齐 32 B。硬件参数为示例值（不代表任何具体芯片）；本程序的输出
是确定性模型在本次运行中的真实计算结果，不是实测性能数据。

示例模型每个输出块都完整搬运自己的 A/B 切片（相邻块之间不复用行/列
块——那正是 D101 reuse 账里"缩 tile → HBM 流量上升"的根源）。
"""

from __future__ import annotations

import argparse
import datetime
import os
import platform
import sys
from dataclasses import dataclass, field

# ---------------- 示例硬件参数（µs / Byte / MAC，同 D102/D103） ----------------
DMA_BW = 32_768.0        # DMA 带宽，Byte/µs（32.768 GB/s，示例值）
MAC_RATE = 262_144.0     # 计算吞吐，MAC/µs（示例值）
SRAM_BUDGET = 262_144    # 片上 SRAM 预算：256 KiB（沿用 D101/D104）
ALIGN = 32               # DMA 对齐，Byte
DTYPE_IN = 4             # fp32 输入，Byte/元素
DTYPE_ACC = 4            # fp32 累加，Byte/元素

M = N = K = 512          # 问题规模（沿用本周的 512³ MatMul）


def align_up(n: int, a: int = ALIGN) -> int:
    return (n + a - 1) // a * a


def fmt_b(n: int) -> str:
    return f"{n:,} B"


# ================================================================
# 第一幕：编译期·图级——D99 活跃区间 + D100 片外工作区
# ================================================================
# 迷你计算图（把本周的 kernel 放进图里看它的位置）：
#   步骤 1: t = MatMul(x, w)      ← 本周的主角 kernel（内部再切 64 个输出块）
#   步骤 2: y = ReLU(t)           ← 逐元素
GRAPH_OPS = [
    ("t", "MatMul(x,w)", ["x", "w"]),
    ("y", "ReLU(t)", ["t"]),
]
GRAPH_TENSORS = {
    # name: (类别, 形状, 元素大小)   参数常驻权重区，不进动态工作区
    "x": ("input", (M, K), DTYPE_IN),
    "w": ("param", (K, N), DTYPE_IN),
    "t": ("mid", (M, N), DTYPE_ACC),
    "y": ("output", (M, N), DTYPE_ACC),
}


def graph_level_ledger() -> dict:
    """D99/D100 的图级账本：活跃区间 → 每步活跃 → 工作区复用规划。"""
    # --- D99 活跃区间（闭区间 [def, last_use]，步骤 1..2，0=图前，3=图后）---
    steps = {name: [] for name in GRAPH_TENSORS}
    for step, (out, expr, ins) in enumerate(GRAPH_OPS, start=1):
        steps[out].append(step)            # 定义即使用（写出）
        for i in ins:
            if i in steps:
                steps[i].append(step)      # 读
    live = {}
    for name, (cat, shape, dt) in GRAPH_TENSORS.items():
        uses = steps[name]
        d, lu = min(uses), max(uses)
        if cat == "input":
            d = 0                        # 图输入在图前就存在
        if cat == "output":
            lu = len(GRAPH_OPS) + 1        # 图输出活到图后（步骤 3）
        live[name] = (d, lu)

    sizes = {n: shape[0] * shape[1] * dt
             for n, (cat, shape, dt) in GRAPH_TENSORS.items()}

    # --- 每步活跃（动态：input + mid + output；param 常驻不计）---
    per_step = {}
    for s in range(0, len(GRAPH_OPS) + 2):  # 0=图前,1,2=步骤,3=图后
        alive = [n for n in GRAPH_TENSORS
                 if GRAPH_TENSORS[n][0] != "param"
                 and live[n][0] <= s <= live[n][1]]
        per_step[s] = alive
    peak_step_bytes = max(sum(sizes[n] for n in per_step[s])
                          for s in per_step)

    # --- D100 工作区规划：按最后使用点排序（早退房优先）+ 首次适应 ---
    order = sorted([n for n in GRAPH_TENSORS if GRAPH_TENSORS[n][0] != "param"],
                   key=lambda n: (live[n][1], live[n][0]))
    regions = []                            # (offset, size, tenant, interval)
    plan = {}
    for n in order:
        d, lu = live[n]
        sz = align_up(sizes[n])
        placed = False
        for r in regions:                  # 首次适应：找一块时间错开的
            ro, rsz, rten, (rd, rlu) = r
            if not (d <= rlu and rd <= lu):  # 区间不重叠
                plan[n] = ro
                r[3] = (min(rd, d), max(rlu, lu))
                r[2] = f"{rten}→{n}"
                placed = True
                break
        if not placed:
            off = max((r[0] + r[1] for r in regions), default=0)
            off = align_up(off)
            regions.append([off, sz, n, (d, lu)])
            plan[n] = off
    workspace = max(r[0] + r[1] for r in regions) if regions else 0
    no_reuse = sum(align_up(sizes[n]) for n in order)
    return {"live": live, "sizes": sizes, "per_step": per_step,
            "peak_step_bytes": peak_step_bytes, "plan": plan,
            "regions": regions, "workspace": workspace,
            "no_reuse": no_reuse, "param_bytes":
            sum(sizes[n] for n in GRAPH_TENSORS if GRAPH_TENSORS[n][0] == "param")}


def act1_print(g: dict, out):
    w = out.write
    w("=" * 78 + "\n")
    w("第一幕（编译期·图级）：t 的活跃区间与片外房间   [D99/D100]\n")
    w("=" * 78 + "\n")
    w("迷你图：" + " → ".join(f"{o}={e}" for o, e, _ in GRAPH_OPS)
      + "   （w 为参数，常驻权重区，不进动态工作区）\n\n")
    w("-- 生命周期表（闭区间 [def, last_use]，步骤 1..2，0=图前，3=图后）--\n")
    w(f"{'张量':<6}{'类别':<8}{'字节':>12}   {'活跃区间':>10}\n")
    for n in ("x", "w", "t", "y"):
        cat = GRAPH_TENSORS[n][0]
        d, lu = g["live"][n]
        w(f"{n:<6}{cat:<8}{fmt_b(g['sizes'][n]):>12}   [{d}, {lu}]\n")
    w(f"参数 w 合计 {fmt_b(g['param_bytes'])} 常驻权重区，不计入下面的动态峰值。\n\n")
    w("-- 每步活跃（动态张量：输入+中间+输出）--\n")
    for s in sorted(g["per_step"]):
        names = g["per_step"][s]
        w(f"步骤 {s}   存活：{', '.join(names) if names else '（无）':<12}"
          f"   {fmt_b(sum(g['sizes'][n] for n in names))}\n")
    w(f"\n峰值动态内存 = {fmt_b(g['peak_step_bytes'])}（步骤 1 和 2 打平）\n\n")
    w("-- 工作区规划（D100：按最后使用点排序＋首次适应，对齐 32 B）--\n")
    for r in sorted(g["regions"], key=lambda r: r[0]):
        off, sz, tenants, (d, lu) = r
        w(f"  偏移 {fmt_b(off):>12}   大小 {fmt_b(sz):>12}   先后住客：{tenants}\n")
    w(f"\n无复用（每张量独占）      {fmt_b(g['no_reuse'])}\n")
    w(f"共享工作区（本次规划）    {fmt_b(g['workspace'])}"
      f"   省 {fmt_b(g['no_reuse'] - g['workspace'])}"
      f"（{(1 - g['workspace'] / g['no_reuse']) * 100:.1f}%）\n")
    w(f"峰值活跃集合（理论下界）  {fmt_b(g['peak_step_bytes'])}"
      f"   工作区已达下界：{'是' if g['workspace'] <= g['peak_step_bytes'] else '否'}\n\n")
    t_off = g["plan"]["t"]
    w(f">> 主角就位：t 的片外房间在 workspace 偏移 {fmt_b(t_off)} 处，"
      f"大小 {fmt_b(g['sizes']['t'])}。\n")
    w(f">> MatMul kernel 的 64 个输出块将轮流把结果写进这 1 MiB——\n")
    w(f">> C[0,0]（第一个输出块）写进它的开头 {fmt_b(64 * 64 * DTYPE_ACC)}。\n\n")


# ================================================================
# 第二幕：编译期·闸门——D101 空间账本 + D104 资源过滤
# ================================================================
@dataclass(frozen=True)
class TileConfig:
    tm: int = 64
    tn: int = 64
    tk: int = 64
    dtype_in: str = "fp32"
    buffering: str = "double"
    bias: bool = True


def estimate(cfg: TileConfig) -> dict:
    """D101 五项家当：×2 只加在 DMA 流入项（A/B）；C 恒按累加精度；逐项对齐。"""
    a = align_up(cfg.tm * cfg.tk * DTYPE_IN)
    b = align_up(cfg.tk * cfg.tn * DTYPE_IN)
    c = align_up(cfg.tm * cfg.tn * DTYPE_ACC)
    bias = align_up(cfg.tn * DTYPE_ACC) if cfg.bias else 0
    f = 2 if cfg.buffering == "double" else 1
    total = f * a + f * b + c + bias
    return {"a": a, "b": b, "c": c, "bias": bias, "factor": f, "total": total}


def gate_check(cfg: TileConfig, budget: int = SRAM_BUDGET) -> dict:
    """D104 闸门：fail-closed 参数校验 → 空间估算 → 预算判定。"""
    if cfg.dtype_in not in ("fp32", "fp16", "bf16", "int8", "int32"):
        return {"ok": False, "code": "BAD_PARAM",
                "msg": f"未知 dtype_in = {cfg.dtype_in!r}"
                       f"（可选 fp32/fp16/bf16/int8/int32）"}
    if cfg.buffering not in ("single", "double"):
        return {"ok": False, "code": "BAD_PARAM",
                "msg": f"未知缓冲策略 = {cfg.buffering!r}（可选 single/double）"}
    for name in ("tm", "tn", "tk"):
        if getattr(cfg, name) <= 0:
            return {"ok": False, "code": "BAD_PARAM",
                    "msg": f"tile.{name} = {getattr(cfg, name)} 不是正整数"}
    bd = estimate(cfg)
    if bd["total"] <= budget:
        return {"ok": True, "code": "OK", "bd": bd,
                "util": bd["total"] / budget}
    return {"ok": False, "code": "SRAM_OVERFLOW", "bd": bd,
            "over": bd["total"] - budget,
            "msg": f"合计 {fmt_b(bd['total'])} 超出预算 {fmt_b(budget)} "
                   f"{fmt_b(bd['total'] - budget)}"}


def act2_print(cfg: TileConfig, out):
    w = out.write
    w("=" * 78 + "\n")
    w("第二幕（编译期·闸门）：主角的配置过不过资源关   [D101/D104]\n")
    w("=" * 78 + "\n")
    w(f"预算 {fmt_b(SRAM_BUDGET)}（256 KiB，示例值）    DMA 对齐 {ALIGN} B\n")
    v = gate_check(cfg)
    bd = v.get("bd", {})
    f = bd.get("factor", 1)
    detail = " + ".join(x for x in [
        f"A {fmt_b(bd.get('a', 0))}" + (f"×{f}" if f > 1 else ""),
        f"B {fmt_b(bd.get('b', 0))}" + (f"×{f}" if f > 1 else ""),
        f"C {fmt_b(bd.get('c', 0))}",
        f"bias {fmt_b(bd.get('bias', 0))}" if bd.get("bias") else None] if x)
    if v["ok"]:
        w(f"\n候选 {cfg.tm}×{cfg.tn}×{cfg.tk} {cfg.dtype_in}·{cfg.buffering}"
          f"{' +bias' if cfg.bias else ''}\n")
        w(f"  空间明细 : {detail} = {fmt_b(bd['total'])}\n")
        w(f"  判定     : ✓ 放行（利用率 {v['util'] * 100:.1f}%）"
          f"——旅程获准开始\n")
    else:
        w(f"\n候选 {cfg.tm}×{cfg.tn}×{cfg.tk} {cfg.dtype_in}·{cfg.buffering}"
          f"{' +bias' if cfg.bias else ''}\n")
        if "bd" in v:
            w(f"  空间明细 : {detail} = {fmt_b(bd['total'])}\n")
        w(f"  判定     : ✗ {v['code']}  {v['msg']}\n")
        if v["code"] == "SRAM_OVERFLOW":
            w("  出路     : a) 退单缓冲（时间轴）  b) 缩 tile（空间轴）"
              "  c) 降 dtype（精度轴）——每条都要重新过闸\n")
        w("  ——旅程在出发前就被拦下，一次 DMA 都不会发生。\n")

    # 反面教材：128³ 双缓冲（D104 已拒过的纸面最优）
    if (cfg.tm, cfg.tn, cfg.tk, cfg.dtype_in, cfg.buffering) != (128, 128, 128, "fp32", "double"):
        bad = gate_check(TileConfig(128, 128, 128))
        w(f"\n对照组：128³ fp32·double +bias 合计 {fmt_b(bad['bd']['total'])}"
          f" → ✗ {bad['code']}（超 {fmt_b(bad['over'])}）\n")
        w("  ——D103 量出它有 1.32× 纸面加速，D104 一票否决：住不下就是住不下。\n")
    w("\n")


# ================================================================
# 第三幕：运行期·块级——D102/D103 事件级时间线
# ================================================================
@dataclass
class Op:
    name: str
    kind: str                      # load | compute | store
    dur: float
    nbytes: int = 0
    macs: int = 0
    deps: list = field(default_factory=list)   # RAW/WAR 依赖（Op 列表）
    engine_prev: object = None                  # 同引擎前驱（引擎串行）
    start: float = -1.0
    end: float = -1.0
    block: int = -1
    k: int = -1
    slot: int = -1
    sync_in: str = ""               # 本事件进门时要等的同步点


def build_ops(mode: str, t: int = 64, nblocks: int = None) -> list:
    """为整个 kernel 建事件 DAG。块序 b = 0..63（b = i*8+j，j 走得最快）。

    依赖（沿用 D102 编号）：
      S1 RAW 搬运→计算    c[b,k] 等它的 A/B（k=0 还等 bias）
      S2 WAR 计算→搬运    覆盖槽位前，等槽位的上一批读者完工
      S3 RAW 计算→写回    store[b] 等 c[b,7]
      S4 WAR 写回→复用    下一块的 C←0 等上一块的写回完工
    """
    if nblocks is None:
        nblocks = (M // t) * (N // t)
    n_k = K // t
    load_t = align_up(t * t * DTYPE_IN) / DMA_BW
    comp_t = t * t * t / MAC_RATE
    store_t = align_up(t * t * DTYPE_ACC) / DMA_BW
    bias_t = align_up(t * DTYPE_ACC) / DMA_BW

    dma: list[Op] = []
    comp: list[Op] = []
    loads = {}          # (b, k) -> (Op, Op)   A 与 B
    biases = {}         # b -> Op
    stores = {}         # b -> Op
    computes = {}       # (b, k) -> Op

    def new_load(b, k, slot, name):
        o = Op(name, "load", load_t, align_up(t * t * DTYPE_IN), block=b, k=k, slot=slot)
        dma.append(o)
        return o

    for b in range(nblocks):
        biases[b] = Op(f"bias[{b}]", "load", bias_t, align_up(t * DTYPE_ACC), block=b)
        dma.append(biases[b])
        for k in range(n_k):
            slot = k % 2 if mode in ("double", "pipeline") else 0
            loads[(b, k)] = (new_load(b, k, slot, f"A[{b},{k}]→槽{slot}"),
                             new_load(b, k, slot, f"B[{b},{k}]→槽{slot}"))
        stores[b] = Op(f"store[{b}]", "store", store_t,
                       align_up(t * t * DTYPE_ACC), block=b)
        dma.append(stores[b])
    for b in range(nblocks):
        for k in range(n_k):
            computes[(b, k)] = Op(f"c[{b},{k}]", "compute", comp_t,
                                 macs=t * t * t, block=b, k=k)
            comp.append(computes[(b, k)])

    # ---- DMA 提交顺序（单引擎 FIFO，决定 engine_prev 链）----
    order = []
    for b in range(nblocks):
        order.append(biases[b])
        # pipeline：块 b≥1 的 k=0 已在上一块末尾预取过，不再重复提交
        k0 = 1 if (mode == "pipeline" and b >= 1) else 0
        for k in range(k0, n_k):
            order += list(loads[(b, k)])
        if mode == "pipeline" and b + 1 < nblocks:
            order += list(loads[(b + 1, 0)])      # 跨块预取：先搬下一块 k=0
        order.append(stores[b])
    for prev, cur in zip(order, order[1:]):
        cur.engine_prev = prev
    for prev, cur in zip(comp, comp[1:]):
        cur.engine_prev = prev

    # ---- 依赖边 ----
    for b in range(nblocks):
        for k in range(n_k):
            c = computes[(b, k)]
            a, bb = loads[(b, k)]
            c.deps += [a, bb]                    # S1 RAW
            c.sync_in = "S1"
            if k == 0:
                c.deps.append(biases[b])          # k=0 圈加 bias
            # S2 WAR：本对 load 要等槽位上一批读者
            if mode == "single":
                reader = computes[(b, k - 1)] if k >= 1 else (
                    computes[(b - 1, n_k - 1)] if b >= 1 else None)
            else:                                  # double / pipeline：距离 2
                reader = computes[(b, k - 2)] if k >= 2 else (
                    computes[(b - 1, n_k - 2 + k)] if b >= 1 else None)
            if reader is not None:
                a.deps.append(reader)
                bb.deps.append(reader)
                a.sync_in = bb.sync_in = "S2"
        stores[b].deps.append(computes[(b, n_k - 1)])   # S3 RAW
        stores[b].sync_in = "S3"
        if b + 1 < nblocks:                            # S4 WAR：C 槽复用
            computes[(b + 1, 0)].deps.append(stores[b])
            if not computes[(b + 1, 0)].sync_in:
                computes[(b + 1, 0)].sync_in = "S4"
    return dma + comp


def simulate(ops: list) -> None:
    """两台引擎（DMA 串行、计算串行）事件驱动排程；start=max(前驱,依赖)。"""
    pending = {id(o): o for o in ops}
    done = {}
    while pending:
        progressed = False
        for oid in list(pending):
            o = pending[oid]
            deps = o.deps + ([o.engine_prev] if o.engine_prev is not None else [])
            if any(id(d) not in done for d in deps):
                continue
            start = max((done[id(d)] for d in deps), default=0.0)
            o.start = start
            o.end = start + o.dur
            done[oid] = o.end
            del pending[oid]
            progressed = True
        if not progressed:
            raise RuntimeError("依赖图存在环")


def kernel_stats(ops: list, t: int = 64, nblocks: int = 64) -> dict:
    total = max(o.end for o in ops)
    dma = [o for o in ops if o.kind in ("load", "store")]
    comp = [o for o in ops if o.kind == "compute"]
    dma_busy = sum(o.dur for o in dma)
    comp_busy = sum(o.dur for o in comp)
    return {"total": total, "dma_busy": dma_busy, "dma_idle": total - dma_busy,
            "comp_busy": comp_busy, "comp_bubble": total - comp_busy,
            "comp_util": comp_busy / total, "dma_util": dma_busy / total,
            "n_ops": len(ops)}


def act3_print(cfg: TileConfig, out):
    w = out.write
    t = cfg.tm
    n_k = K // t
    w("=" * 78 + "\n")
    w("第三幕（运行期·块级）：块 C[0,0] 的旅程事件日志   [D102/D103]\n")
    w("=" * 78 + "\n")
    w(f"配置：{cfg.buffering} 缓冲，tile {t}³，fp32；"
      f"DMA {DMA_BW:,.0f} B/µs，计算 {MAC_RATE:,.0f} MAC/µs\n")
    w(f"kernel = 512³ MatMul → 64 个输出块（块 b=(i,j)={t}×{t}，"
      f"每块 {n_k} 圈 k 循环）\n")
    bias_b = align_up(t * DTYPE_ACC)
    tile_b = align_up(t * t * DTYPE_IN)
    w(f"\n① 出生——块 (0,0) 的数据清单（编译期已排好）：\n")
    w(f"   要读 : bias[0] {fmt_b(bias_b)} + A 切片 {n_k}×{fmt_b(tile_b)}"
      f" + B 切片 {n_k}×{fmt_b(tile_b)}\n")
    w(f"   要写 : C 槽 {fmt_b(align_up(t * t * DTYPE_ACC))}"
      f"（片上累加完再写回 t 房间）\n")
    w(f"   要算 : {n_k} × {t}³ = {n_k * t ** 3:,} MAC\n")

    mode = cfg.buffering
    ops = build_ops(mode, t)
    simulate(ops)

    w(f"\n②③④ 入住→成长→写回：{mode} 缓冲下块 (0,0) 的完整时间线（µs，真实运行）\n")
    w("-" * 78 + "\n")
    events = [o for o in ops if o.block == 0]
    events.sort(key=lambda o: (o.start, o.kind != "compute"))
    for o in events:
        stage = ""
        if o.kind == "load" and o.name.startswith("bias"):
            stage = "② 入住"
        elif o.kind == "compute":
            stage = "③ 成长"
            if o.k == 0:
                stage += "（C←0＋bias）"
            elif o.k == n_k - 1:
                stage += "（末圈）"
        elif o.kind == "store":
            stage = "④ 写回"
        overlap = ""
        if o.kind == "load" and o.k >= 1:
            overlap = "‖ 与计算重叠" if mode != "single" else "（等上一圈算完）"
        if o.kind == "compute" and 0 < o.k < n_k - 1:
            overlap = "‖ 与搬运重叠" if mode != "single" else "（等下一圈搬完）"
        qty = f"{fmt_b(o.nbytes)}" if o.nbytes else f"{o.macs:,} MAC"
        w(f"{o.start:9.4f}–{o.end:9.4f} "
          f"{'DMA' if o.kind != 'compute' else '计算'}  {o.name:<22}{qty:>13}"
          f"  {stage}{(' ' + overlap) if overlap else ''}\n")
    st = [o for o in ops if o.kind == "store" and o.block == 0][0]
    c0 = [o for o in ops if o.kind == "compute" and o.block == 0 and o.k == 0][0]
    comp = t ** 3 / MAC_RATE
    w("-" * 78 + "\n")
    if mode == "single":
        load_t = align_up(t * t * DTYPE_IN) / DMA_BW
        w(f"块合计 {st.end:.4f} µs = 填充 {c0.start:.4f}（②）"
          f" + {n_k}×(搬 {2 * load_t:.4g}＋算 {comp:.4g}) 轮流值班（③）"
          f" + 写回 {st.dur:.4g}（④）\n")
    else:
        w(f"块合计 {st.end:.4f} µs = 填充 {c0.start:.4f}（②）"
          f" + 稳态 {n_k}×{comp:.4g} 双忙（③）"
          f" + 写回 {st.dur:.4g}（④）\n")
        load_t = align_up(t * t * DTYPE_IN) / DMA_BW
        single_blk = (align_up(t * DTYPE_ACC) / DMA_BW + 2 * load_t
                      + n_k * (2 * load_t + comp) + st.dur)
        w(f"（单缓冲同块 {single_blk:.4f} µs——D102 的轮流值班，见 5.4）\n")
    s1 = sum(1 for o in ops if o.kind == "compute" and o.block == 0)
    s2 = sum(1 for o in ops if o.kind == "load" and o.block == 0
             and o.name.startswith("A") and o.sync_in == "S2")
    dist = 1 if mode == "single" else 2
    w(f"本块同步点：S1×{s1}（每圈计算等搬运，RAW）   "
      f"S2×{s2}（覆盖槽前等上{'一' if dist == 1 else '上'}圈读者，WAR 距离 {dist}）\n")
    w(f"            S3×1（写回等末圈，RAW）   "
      f"S4×1（下一块的 C←0 等本块写回，WAR）\n")
    w(f"\n⑤ 让位——S4 之后：C 槽交给块 1，SRAM 的 {fmt_b(estimate(cfg)['total'])}"
      f" 全程不动\n")
    w(f"   （住得下就一直住着：空间账在第二幕就定了，运行期不再变化）\n")

    # ⑥ 交班：pipeline 模式的块 0→1 边界
    ops_p = build_ops("pipeline", t)
    simulate(ops_p)
    border = sorted([o for o in ops_p if 7.9 <= o.start <= 11.1],
                    key=lambda o: (o.start, o.kind != "compute"))
    w(f"\n⑥ 交班——跨块预取流水线：块 0 → 块 1 边界事件（µs，真实运行）\n")
    w("-" * 78 + "\n")
    for o in border:
        qty = f"{fmt_b(o.nbytes)}" if o.nbytes else f"{o.macs:,} MAC"
        note = ""
        if o.kind == "load" and o.block == 1:
            note = "预取下一块，填空槽"
        elif o.kind == "compute" and o.block == 1:
            note = "下一块计算无缝续上"
        elif o.kind == "store":
            note = "写回与预取并行"
        w(f"{o.start:9.4f}–{o.end:9.4f} "
          f"{'DMA' if o.kind != 'compute' else '计算'}  {o.name:<16}{qty:>13}"
          f"  {note}\n")
    w("-" * 78 + "\n")
    w("末圈计算时 DMA 预取块 1 的首圈——填充/排空从『每块一次』摊薄成\n"
      "『全 kernel 一次』（D103 的账：26.38% → 0.28%）。\n\n")
    return {"double_ops": ops, "pipeline_ops": ops_p}


def act4_print(cfg: TileConfig, out, refs: dict):
    w = out.write
    t = cfg.tm
    w("=" * 78 + "\n")
    w("第四幕（汇总）：三种模式的内核总账（64 块，真实运行）\n")
    w("=" * 78 + "\n")
    rows = []
    for mode, label in (("single", "单缓冲(D102)"), ("double", "逐块双缓冲"),
                        ("pipeline", "跨块预取流水线")):
        ops = refs.get(mode + "_ops")
        if ops is None:
            ops = build_ops(mode, t)
            simulate(ops)
        s = kernel_stats(ops, t)
        rows.append((label, s))
    base = rows[0][1]["total"]
    w(f"{'指标':<22}{'单缓冲(D102)':>15}{'逐块双缓冲':>13}{'跨块预取流水线':>15}\n")
    w("-" * 78 + "\n")
    for key, name, fmt in (
            ("total", "总时长 µs", "{:.1f}"), ("dma_busy", "DMA 忙 µs", "{:.1f}"),
            ("dma_idle", "DMA 闲置 µs", "{:.0f}"), ("comp_busy", "计算忙 µs", "{:.0f}"),
            ("comp_bubble", "计算气泡 µs", "{:.1f}"),
            ("comp_util", "计算利用率", "{:.2%}"), ("dma_util", "DMA 利用率", "{:.2%}")):
        cells = "".join(fmt.format(s[key]).rjust(wd)
                        for (_, s), wd in zip(rows, (15, 13, 15)))
        w(f"{name:<22}{cells}\n")
    sp = "".join(f"{base / s['total']:.2f}×".rjust(wd)
                 for (_, s), wd in zip(rows, (15, 13, 15)))
    w(f"{'加速比(vs单缓冲)':<22}{sp}\n")
    w("-" * 78 + "\n")
    w("理想重叠下界 = max(DMA忙, 计算忙) = "
      f"{max(rows[0][1]['dma_busy'], rows[0][1]['comp_busy']):.1f} µs"
      "（D102 预告的 1.94× 上限）\n")
    w("与 D103 compare-modes.txt 对账：1056.5 / 608.5 / 545.5 µs，"
      "1.74× / 1.94×——")
    ok = all(abs(r[1]["total"] - ref) < 0.05 for r, ref in
             zip(rows, (1056.5, 608.5, 545.5)))
    w("一致 ✓\n" if ok else "不一致 ✗（请检查模型！）\n\n")
    return rows


# ================================================================
# 主入口
# ================================================================
def run_story(cfg: TileConfig, out=sys.stdout):
    g = graph_level_ledger()
    act1_print(g, out)
    act2_print(cfg, out)
    refs = act3_print(cfg, out)
    ops_s = build_ops("single", cfg.tm)
    simulate(ops_s)
    refs["single_ops"] = ops_s
    act4_print(cfg, out, refs)
    w = out.write
    w("=" * 78 + "\n")
    w("环境：" + env_line() + "\n")
    w("硬件参数为示例值（DMA 32,768 B/µs、计算 262,144 MAC/µs、预算 256 KiB）；\n")
    w("输出为确定性模型在本次运行中的真实计算结果，不是实测性能数据。\n")


def env_line() -> str:
    return (f"Python {platform.python_version()}，{platform.machine()}，"
            f"{datetime.date.today().isoformat()}")


# ---------------- 自检 ----------------
def self_test() -> int:
    n = [0]

    def check(cond, what):
        n[0] += 1
        if not cond:
            print(f"[失败] {what}")
            raise SystemExit(1)
        print(f"[{n[0]:3d}] 通过  {what}")

    # ---- 第一幕 ----
    g = graph_level_ledger()
    check(g["live"]["x"] == (0, 1), "图级：x 活跃区间 [0,1]")
    check(g["live"]["t"] == (1, 2), "图级：t 活跃区间 [1,2]")
    check(g["live"]["y"] == (2, 3), "图级：y 活跃区间 [2,3]（活到图后）")
    check(g["peak_step_bytes"] == 2 * 1024 * 1024, "图级：峰值动态 = 2 MiB")
    check(g["workspace"] == 2 * 1024 * 1024, "图级：工作区 2 MiB")
    check(g["workspace"] == g["peak_step_bytes"], "图级：工作区 = 峰值（达下界）")
    check(g["plan"]["x"] == g["plan"]["y"], "图级：x 与 y 共享同一偏移")
    check(g["plan"]["t"] == 1024 * 1024, "图级：t 的房间在偏移 1 MiB")
    check(g["no_reuse"] == 3 * 1024 * 1024, "图级：无复用 3 MiB")

    # ---- 第二幕 ----
    v64 = gate_check(TileConfig(64, 64, 64))
    check(v64["ok"] and v64["bd"]["total"] == 82_176, "闸门：64³ double 82,176 B ✓")
    check(abs(v64["util"] - 82_176 / 262_144) < 1e-12, "闸门：利用率 31.3%")
    v64s = gate_check(TileConfig(64, 64, 64, buffering="single"))
    check(v64s["bd"]["total"] == 49_408, "闸门：64³ single 49,408 B（D101）")
    v128 = gate_check(TileConfig(128, 128, 128))
    check(not v128["ok"] and v128["over"] == 66_048,
          "闸门：128³ double 超预算 66,048 B（D104）")
    check(gate_check(TileConfig(128, 128, 128, buffering="single"))["bd"]["total"]
          == 197_120, "闸门：128³ single 197,120 B")
    check(gate_check(TileConfig(64, 64, 64, dtype_in="fp64"))["code"] == "BAD_PARAM",
          "闸门：fail-closed 拒绝未知 dtype")

    # ---- 第三幕 ----
    for mode, blk, kdl in (("single", 16.5078125, 16), ("double", 9.5078125, 8)):
        ops = build_ops(mode, 64)
        simulate(ops)
        st = [o for o in ops if o.kind == "store" and o.block == 0][0]
        c0 = [o for o in ops if o.kind == "compute" and o.block == 0 and o.k == 0][0]
        c1 = [o for o in ops if o.kind == "compute" and o.block == 0 and o.k == 1][0]
        check(abs(st.end - blk) < 1e-9, f"{mode}：块(0,0) 合计 {blk} µs（D102/D103）")
        check(abs(c0.start - 1.0078125) < 1e-9,
              f"{mode}：首个计算等 bias+A+B 完工，1.0078 µs 才开工")
        second = 3.0078125 if mode == "single" else 2.0078125
        check(abs(c1.start - second) < 1e-9,
              f"{mode}：第二圈计算开工于 {second} µs"
              f"（{'等重载' if mode == 'single' else '数据已就位'}）")
        s = kernel_stats(ops, 64)
        ref_total = {"single": 1056.5, "double": 608.5}[mode]
        check(abs(s["total"] - ref_total) < 0.05, f"{mode}：内核总时长 {ref_total} µs")
    ops_d = build_ops("double", 64)
    simulate(ops_d)
    s1 = sum(1 for o in ops_d if o.kind == "compute")
    s2 = sum(1 for o in ops_d if o.kind == "load" and o.name.startswith("A")
             and o.sync_in == "S2")
    s3 = sum(1 for o in ops_d if o.kind == "store")
    s4 = sum(1 for o in ops_d if o.kind == "compute" and o.block > 0 and o.k == 0
             and any(d.kind == "store" for d in o.deps))
    check((s1, s2, s3, s4) == (512, 510, 64, 63),
          f"double：同步点 S1/S2/S3/S4 = {s1}/{s2}/{s3}/{s4}（D103）")
    sd = kernel_stats(ops_d, 64)
    check(abs(sd["comp_util"] - 512 / 608.5) < 1e-12, "double：计算利用率 84.14%")

    ops_p = build_ops("pipeline", 64)
    simulate(ops_p)
    sp = kernel_stats(ops_p, 64)
    check(abs(sp["total"] - 545.5) < 0.05, "pipeline：总时长 545.5 µs（D103）")
    check(abs(sp["dma_busy"] - 544.5) < 0.05, "pipeline：DMA 忙 544.5 µs")
    check(abs(sp["dma_idle"] - 1.0) < 0.05, "pipeline：DMA 闲置 1 µs")
    check(abs(sp["comp_busy"] - 512.0) < 1e-9, "pipeline：计算忙 512 µs")
    check(abs(sp["comp_bubble"] - 33.5) < 0.05, "pipeline：计算气泡 33.5 µs")
    check(abs(sp["comp_util"] - 512 / 545.5) < 1e-12, "pipeline：计算利用率 93.86%")
    check(abs(1056.5 / sp["total"] - 1.937) < 0.01, "pipeline：加速比 1.94×")
    a10 = [o for o in ops_p if o.name.startswith("A[1,0]")][0]
    check(abs(a10.start - 8.0078125) < 1e-9, "pipeline：A[1,0] 预取开工于 8.0078 µs")
    st0 = [o for o in ops_p if o.kind == "store" and o.block == 0][0]
    check(abs(st0.start - 9.0078125) < 1e-9 and abs(st0.end - 9.5078125) < 1e-9,
          "pipeline：store[0] 在 9.0078–9.5078 µs（D103）")
    c10 = [o for o in ops_p if o.kind == "compute" and o.block == 1 and o.k == 0][0]
    check(abs(c10.start - 9.515625) < 1e-9, "pipeline：c[1,0] 于 9.5156 µs 无缝续上")

    print(f"\n自检全部通过：{n[0]}/{n[0]} 项。")
    return n[0]


def main():
    ap = argparse.ArgumentParser(description="一个 Tile 的一生（第 15 周复盘）")
    ap.add_argument("--tile", type=int, default=64, help="tile 边长（默认 64）")
    ap.add_argument("--buffering", choices=["single", "double"], default="double")
    ap.add_argument("--dtype", default="fp32")
    ap.add_argument("--self-test", action="store_true", help="跑断言自检")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return
    cfg = TileConfig(args.tile, args.tile, args.tile,
                     args.dtype, args.buffering)
    v = gate_check(cfg)
    if not v["ok"]:
        print("=" * 78)
        print("闸门先行：主角的配置没过资源关，旅程无法开始。")
        print("=" * 78)
        act2_print(cfg, sys.stdout)
        print("换 tile／缓冲策略／dtype 再来（本文 5.4 的对照实验就是它）。")
        return
    run_story(cfg)


if __name__ == "__main__":
    main()
