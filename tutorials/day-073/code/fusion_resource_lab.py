#!/usr/bin/env python3
"""fusion_resource_lab.py —— 第 73 天主实验：融合的资源代价。

问题：第 72 天的收益公式 ΔB = Σ 2·numel·itemsize 省掉了中间 Tensor 的
「一写一读」两趟 DRAM，但它有一个当时没展开的假设——中间值能驻留片上
（寄存器）。片上到底有多大？装不下会发生什么？装下了但挤占并行度呢？

今天把「融合的代价」记成一张资源账，四个轴：
  1. 寄存器：融合 kernel 的峰值活集（live set，任一时刻必须同时在片的
     中间值字节）必须装进寄存器堆；装不下就降级甚至溢出（spill）。
  2. 片上存储：降级到 SRAM 的活集 + 有数据复用的输入分块共享同一块 SRAM。
  3. 并行度：活集越大，寄存器堆能同时驻留的 tile 越少（occupancy 下降）。
  4. 指令复杂度：融合把消费者的指令并进来，增量 ≈ 逐元素指令数 / 生产者指令数。

核心结构：Machine（机器假设卡）＋ KernelResource（单个 kernel 的资源
估算记录）＋ place()（容量阶梯：寄存器 → SRAM → spill）。

产出：资源估算模型 + 假设清单（见第 1 节打印）。

运行：python3 fusion_resource_lab.py
"""

from __future__ import annotations

from dataclasses import dataclass

PASSED = 0
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASSED, CHECKS
    CHECKS += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' ' + detail) if detail else ''}")
    if cond:
        PASSED += 1
    return cond


def kib(n: float) -> str:
    """字节数的友好显示：大于 1 MiB 用 MiB，大于 1 KiB 用 KiB，否则 B。"""
    if n >= 1024 * 1024:
        s = n / 1024 / 1024
        return f"{s:.2f} MiB" if s != int(s) else f"{int(s)} MiB"
    if n >= 1024:
        s = n / 1024
        return f"{s:.2f} KiB" if s != int(s) else f"{int(s)} KiB"
    return f"{int(n)} B"


# ================================================================
# 1. 资源估算模型：机器假设卡 + 假设清单
# ================================================================

@dataclass(frozen=True)
class Machine:
    """机器假设卡：今天所有资源判断都基于这张卡（量级参照真实硬件的玩具参数）。

    regfile_bytes / sram_bytes / lanes 都可以换成别的机器重算——
    这正是「假设清单」的意义：结论跟着假设走，不跟着感觉走。
    """

    name: str = "toy-core v0"
    regfile_bytes: int = 64 * 1024      # 每核寄存器堆 64 KiB（累加器/在飞向量驻留）
    sram_bytes: int = 192 * 1024        # 每核片上 SRAM 192 KiB（降级活集 + 输入分块）
    lanes: int = 64                    # 每核 64 条并行通道（一次算 64 个元素）
    itemsize: int = 4                  # fp32

    @property
    def onchip_bytes(self) -> int:
        return self.regfile_bytes + self.sram_bytes


ASSUMPTIONS: list[str] = [
    "A1 机器参数是玩具假设（量级参照真实硬件：GPU 一个 SM 的寄存器堆约 256 KiB、"
    "共享存储约 48~228 KiB；NPU 的 Cube/Vector 配 Unified Buffer），可整体替换重算",
    "A2 活集（live set）= 峰值时刻必须同时在片的中间值字节；输入默认按需流过，不计入活集",
    "A3 有数据复用的输入（MatMul 的 A/B 分块）驻 SRAM；无复用的输入（如 bias D，"
    "每元素只用一次）流式读、不驻留",
    "A4 spill 按每字节一写一读两趟计（下界）；累加器在 K 循环中反复改写的 RMW 放大不计"
    "（真实溢出更贵）",
    "A5 逐元素 kernel 的活集 = 每通道在飞（输入＋输出）向量，与数据总量无关（流式）",
    "A6 MatMul 的累加器块（tile_m × tile_n）常驻寄存器跨 K 循环；融合进来的逐元素 "
    "epilogue 复用累加器槽，只额外要每通道 1 个在飞槽",
    "A7 并行度 proxy = 资源允许的并发 tile 数 = min(寄存器堆/每 tile 累加器, "
    "SRAM/每 tile 输入分块)，下限 1",
    "A8 不计 kernel launch、多核分发、跨核 SRAM 竞争、指令缓存与编译时间",
    "A9 收益口径沿用第 72 天（无缓存复用、compulsory 理想下界）；"
    "净收益 = ΔB − spill 流量",
    "A10 MatMul→MatMul 融合假设好调度（中间行块驻 SRAM、消费者横扫输出 tile），"
    "不计重算/重读放大；输入分块的 SRAM 需求今天不建模（记在 A8 的不计项里）",
]


@dataclass
class KernelResource:
    """单个 kernel（独立算子或融合块）的资源估算记录——今天的核心结构。

    reg_demand  必须驻寄存器的部分：累加器块 + 在飞向量
    extra_live  额外活集：须驻 SRAM 的中间块（如 MM→MM 的 G 行块）
    sram_demand 输入分块驻留（有复用的 A/B 分块；无复用输入为 0）
    placement   容量阶梯落位："reg" / "reg+sram" / "spill"
    spill_bytes 超出（寄存器堆＋SRAM）的部分 → 必须回 DRAM
    spill_traffic = 2 × spill_bytes（一写一读两趟，A4 下界口径）
    concurrent_tiles 并行度 proxy（A7）
    """

    name: str
    reg_demand: int
    extra_live: int = 0
    sram_demand: int = 0
    placement: str = ""
    demoted_bytes: int = 0       # 降级到 SRAM 的活集
    spill_bytes: int = 0
    spill_traffic: int = 0
    concurrent_tiles: int = 1
    staging_ok: bool = True      # 输入分块在活集占用后是否还放得下

    @property
    def live_bytes(self) -> int:
        return self.reg_demand + self.extra_live

    @property
    def resident_live(self) -> int:
        """驻留在片上的活集（寄存器 + SRAM），溢出部分不算。"""
        return self.live_bytes - self.spill_bytes


def place(res: KernelResource, m: Machine) -> KernelResource:
    """容量阶梯：活集优先保（超容量部分 spill），输入分块让路（可再细分）。

    优先级规则（写进假设清单的精神）：
      1. 活集先填寄存器堆，溢出的降级 SRAM，再溢出的 spill 回 DRAM（记两趟流量）；
      2. 输入分块用 SRAM 的剩余部分；放不下记 staging_ok=False——
         再细分 k 方向即可（不产生额外流量，只是复用下降），所以不 spill。
    """
    live = res.live_bytes
    demoted = min(max(0, live - m.regfile_bytes), m.sram_bytes)
    res.demoted_bytes = demoted
    res.spill_bytes = max(0, live - m.onchip_bytes)
    res.spill_traffic = 2 * res.spill_bytes
    if res.spill_bytes > 0:
        res.placement = "spill"
    elif demoted > 0:
        res.placement = "reg+sram"
    else:
        res.placement = "reg"
    staging_left = m.sram_bytes - demoted
    res.staging_ok = res.sram_demand <= staging_left
    reg_cap = m.regfile_bytes // max(1, res.reg_demand)
    sram_cap = (staging_left // res.sram_demand) if res.sram_demand > 0 else None
    res.concurrent_tiles = max(1, reg_cap if sram_cap is None else min(reg_cap, sram_cap))
    return res


# ================================================================
# 2. 算子级活集公式（对应假设 A3/A5/A6）
# ================================================================

def matmul_acc(tile_m: int, tile_n: int, m: Machine) -> int:
    """MatMul 累加器块：tile_m × tile_n 个 fp32，跨 K 循环常驻寄存器。"""
    return tile_m * tile_n * m.itemsize


def ew_live(m: Machine, n_in: int, n_out: int) -> int:
    """逐元素 kernel 活集：每通道在飞 n_in 个输入向量 + n_out 个输出向量。"""
    return m.lanes * (n_in + n_out) * m.itemsize


def sram_stage_ab(tile_m: int, K: int, tile_n: int, m: Machine) -> int:
    """A/B 分块的 SRAM 驻留：每个 A 元素在 tile 内被复用 tile_n 次、
    每个 B 元素被复用 tile_m 次——有复用才驻留（A3）。"""
    return (tile_m * K + K * tile_n) * m.itemsize


def fused_matmul_epilogue(tile_m: int, tile_n: int, m: Machine) -> int:
    """融合 MatMul+Bias+Relu 的寄存器需求：累加器块 + 每通道 1 个在飞 bias 槽。

    epilogue（逐元素）复用累加器自身的槽位做完 add/max 再写出，
    所以只多要一个在飞向量——「epilogue 融合寄存器上近乎免费」的定量来源。
    """
    return matmul_acc(tile_m, tile_n, m) + m.lanes * m.itemsize


def plan_kernels(M: int, K: int, N: int, m: Machine,
                 tile_m: int | None = None,
                 tile_n: int | None = None) -> dict[str, list[KernelResource]]:
    """四种执行计划（第 50/72 天同款）各自的 kernel 资源记录。

    P0：MatMul | Add | Relu        P1：MatMul | FusedAddReLU
    P2：FusedMatMulBias | Relu     P3：FusedMatMulBiasReLU（单 kernel）
    默认 tile = (M, N)（不分块）；传 tile_m/tile_n 后按分块计。
    """
    tm, tn = (tile_m or M), (tile_n or N)
    acc = matmul_acc(tm, tn, m)
    bias_vec = m.lanes * m.itemsize
    ab = sram_stage_ab(tm, K, tn, m)

    def kr(name, reg, extra=0, sram=0):
        return place(KernelResource(name, reg, extra, sram), m)

    return {
        "P0": [kr("MatMul", acc, sram=ab),
               kr("Add", ew_live(m, 2, 1)),
               kr("Relu", ew_live(m, 1, 1))],
        "P1": [kr("MatMul", acc, sram=ab),
               kr("FusedAddReLU", ew_live(m, 2, 1))],
        "P2": [kr("FusedMatMulBias", acc + bias_vec, sram=ab),
               kr("Relu", ew_live(m, 1, 1))],
        "P3": [kr("FusedMatMulBiasReLU", acc + bias_vec, sram=ab)],
    }


def delta_b_two_intermediates(M: int, N: int, m: Machine) -> int:
    """第 72 天收益公式：2 个中间 Tensor × 2 趟 × M·N 元素 × itemsize。"""
    return 2 * 2 * (M * N) * m.itemsize


# ================================================================
# 主实验
# ================================================================

def main() -> None:
    m = Machine()

    # ---- 1. 口径卡 + 假设清单 ----
    print("== 1. 机器假设卡 + 假设清单（今天的产出之一）==")
    print(f"  机器：{m.name}（全部结论只在这张卡上成立，换卡重算）")
    print(f"  寄存器堆 {kib(m.regfile_bytes)} / 片上 SRAM {kib(m.sram_bytes)}"
          f" / 并行通道 {m.lanes} / fp32")
    print(f"  片上总容量 = {kib(m.regfile_bytes)} + {kib(m.sram_bytes)}"
          f" = {kib(m.onchip_bytes)}")
    for a in ASSUMPTIONS:
        print(f"  {a}")
    check("1a 假设清单共 10 项且无空项", len(ASSUMPTIONS) == 10
          and all(len(a) > 20 for a in ASSUMPTIONS))
    check("1b 片上总容量 = 寄存器堆 + SRAM = 262,144 B",
          m.onchip_bytes == 262144)

    # ---- 2. 容量阶梯自检：place() 的三条落位 ----
    print("\n== 2. 容量阶梯自检：reg → reg+sram → spill ==")
    for label, reg, extra in [
        ("活集恰等寄存器堆", m.regfile_bytes, 0),
        ("活集超寄存器堆 1 B", m.regfile_bytes + 1, 0),
        ("活集超片上容量 1 B", m.onchip_bytes + 1, 0),
    ]:
        r = place(KernelResource("demo", reg, extra), m)
        print(f"  {label}：live {reg + extra:>7,} B → {r.placement:<9s}"
              f" 降级 {r.demoted_bytes:,} B，spill {r.spill_bytes:,} B"
              f"（流量 {r.spill_traffic:,} B）")
    r_eq = place(KernelResource("demo", m.regfile_bytes), m)
    r_over = place(KernelResource("demo", m.onchip_bytes + 1), m)
    check("2a 边界含等号：live == regfile 仍落 reg（降级 0）",
          r_eq.placement == "reg" and r_eq.demoted_bytes == 0)
    check("2b 超 1 B 只降级不溢出：live == onchip+1 才 spill 1 B",
          r_over.spill_bytes == 1 and r_over.spill_traffic == 2
          and r_over.placement == "spill")
    check("2c spill 流量 = 2 × 溢出字节（A4 一写一读下界）",
          r_over.spill_traffic == 2 * r_over.spill_bytes)

    # ---- 3. 贯穿示例：四种计划的资源账 ----
    print("\n== 3. 贯穿示例 A(2,3)@B(3,2)+D(2,2)→relu：四种计划的资源账 ==")
    M0, K0, N0 = 2, 3, 2
    plans = plan_kernels(M0, K0, N0, m)
    db = delta_b_two_intermediates(M0, N0, m)
    # 各计划消除的中间 Tensor 数（第 72 天对照表）：P0 消 0 个、P1/P2 各消 1 个、P3 消 2 个
    eliminated = {"P0": 0, "P1": 1, "P2": 1, "P3": 2}
    saved = {p: 2 * eliminated[p] * (M0 * N0) * m.itemsize for p in eliminated}
    print("  计划   kernel 数   各 kernel 活集(reg)     放置   spill   省下(第72天口径)  净收益")
    peak = {}
    for p in ("P0", "P1", "P2", "P3"):
        ks = plans[p]
        peak[p] = max(k.live_bytes + k.sram_demand for k in ks)
        descs = [f"{k.name} {k.live_bytes}+{k.sram_demand}staging" for k in ks]
        spill_t = sum(k.spill_traffic for k in ks)
        net = saved[p] - spill_t
        print(f"  {p}      {len(ks)}        {'; '.join(descs):<44s}"
              f"{ks[0].placement:>6s}  {spill_t:>3d} B  {saved[p]:>8d} B    {net} B")
    print(f"  峰值片上足迹：P0 {peak['P0']} B → P3 {peak['P3']} B"
          f"（都远小于寄存器堆 {kib(m.regfile_bytes)}：小链资源不设限）")
    p3_reg = plans["P3"][0].reg_demand
    mm_reg = plans["P0"][0].reg_demand
    check("3a 四种计划全部落 reg、零 spill", all(
        k.placement == "reg" and k.spill_bytes == 0
        for ks in plans.values() for k in ks))
    check("3b epilogue 融合的寄存器增量 = 每通道 1 槽 = 256 B",
          p3_reg - mm_reg == m.lanes * m.itemsize == 256)
    check("3c 净收益 = 各计划省下（第 72 天 ΔB 列）− 0 spill：0/32/32/64 B",
          all(saved[p] - sum(k.spill_traffic for k in plans[p]) == saved[p]
              for p in plans)
          and saved["P0"] == 0 and saved["P1"] == saved["P2"] == 32
          and saved["P3"] == db == 64)
    check("3d D 无复用不驻留：P3 的 SRAM 需求只有 A/B 分块 48 B",
          plans["P3"][0].sram_demand == (2 * 3 + 3 * 2) * 4 == 48)
    print(f"  对照：P3 片上活集 {p3_reg} B vs P0 的中间值驻 DRAM "
          f"C+E = {2 * M0 * N0 * m.itemsize} B")
    print("  → 融合 = 把中间值从 DRAM 搬进片上活集：代价 = 活集变大（+256 B/通道），"
          "收益 = 两遍税消失")

    # ---- 4. 放大 + tile 扫描：活集随 tile 走，不随总量走 ----
    print("\n== 4. 放大 M=N=2048, K=64：tile 是活集的调节阀 ==")
    M1, K1s, N1 = 2048, 64, 2048
    db1 = delta_b_two_intermediates(M1, N1, m)
    print(f"  全融合的 ΔB（第 72 天公式）= 16·MN = {db1:,} B = {kib(db1)}")
    print("  tile      活集(reg)      A/B驻SRAM   放置        spill    "
          "staging  并发tile  tile-AI   ΔB兑现")
    sweep = []
    for t in (2048, 256, 128, 64, 32):
        ks = plan_kernels(M1, K1s, N1, m, tile_m=t, tile_n=t)["P3"]
        k = ks[0]
        flops = 2 * t * t * K1s
        byts = (t * K1s + K1s * t + 2 * t * t) * m.itemsize   # A,B 分块 + D 流入 + F 写出
        ai = flops / byts
        net = db1 - k.spill_traffic
        rate = net / db1
        sweep.append((t, k, ai, net, rate))
        print(f"  {t:>4}   {k.reg_demand:>9,} B   {k.sram_demand:>8,} B"
              f"  {k.placement:>9s}  {k.spill_bytes:>8,} B"
              f"  {'ok' if k.staging_ok else 'short':>7s}  {k.concurrent_tiles:>6d}"
              f"   {ai:>6.2f}   {rate:>6.1%}")
    print("  （2048 = 不分块的贪心融合：累加器整块 16 MiB 直接顶爆片上 256 KiB）")
    check("4a tile 每减半，tile-AI 单调下降（表序 2048→32：复用随 tile 变小变差）",
          all(a[2] > b[2] for a, b in zip(sweep, sweep[1:])))
    check("4b tile 每减半，并发 tile 数单调不降（并行度随 tile 变小变好）",
          all(a[1].concurrent_tiles <= b[1].concurrent_tiles
              for a, b in zip(sweep, sweep[1:])))
    k128 = sweep[2][1]
    check("4c tile 128×128 累加器恰满寄存器堆，epilogue 的 256 B 把它顶过线"
          "（降级 256 B、placement reg+sram）",
          k128.reg_demand - m.lanes * m.itemsize == m.regfile_bytes
          and k128.demoted_bytes == 256 and k128.placement == "reg+sram")
    k256 = sweep[1][1]
    check("4d tile 256×256 开始溢出 256 B 且 staging 挤没（SRAM 全被降级活集占）",
          k256.spill_bytes == 256 and not k256.staging_ok)
    k2048 = sweep[0][1]
    net2048 = sweep[0][3]
    check("4e 不分块：spill 流量 33,030,656 B = 2×溢出，净收益被砍掉近半（50.8%）",
          k2048.spill_traffic == 2 * k2048.spill_bytes == 33030656
          and net2048 == db1 - k2048.spill_traffic
          and abs(net2048 / db1 - 0.508) < 1e-3)
    check("4f 存在舒适区 tile：spill=0、staging ok、并发 ≥ 3（64×64）",
          any(k.spill_bytes == 0 and k.staging_ok and k.concurrent_tiles >= 3
              for _t, k, _ai, _n, _r in sweep))
    print(f"  临界点：tile 128×128 的 tile-AI = {sweep[2][2]:.2f}，仍低于第 71 天"
          f"机器平衡点 12.54（访存受限）；tile 256 的 {sweep[1][2]:.2f} 翻过去，"
          "但 SRAM 容量先顶爆——容量约束比平衡点先生效")

    # ---- 5. 昂贵的融合：MatMul → MatMul（活集被消费者的归约结构钉死）----
    print("\n== 5. 反例：融合 MatMul(2048,64)→G(2048,K1)→MatMul(K1,2048) ==")
    print("  消费者输出 tile (128×128) 的累加器 = 64 KiB 恰满寄存器堆；")
    print("  中间 G 行块 (128×K1×4 B) 必须整块驻留——K1 是消费者的归约维，")
    print("  tile_n 缩小救不了它（这就是「不融合时生产者可自由分块、融合后被钉死」）")
    tm = tn = 128
    rows = M1 // tm
    print("   K1    G行块     落位      spill/行块  驻留G   兑现率    ΔB      "
          "spill流量    净收益")
    mm_sweep = []
    for Kmid in (64, 256, 1024, 4096):
        g_row = tm * Kmid * m.itemsize
        acc = matmul_acc(tm, tn, m)
        k = place(KernelResource("FusedMatMulMatMul", acc, g_row), m)
        resident_g = min(g_row, m.onchip_bytes - acc)
        db_mm = 2 * M1 * Kmid * m.itemsize                    # G 免两趟的潜力
        traffic = k.spill_traffic * rows
        net = db_mm - traffic
        rate = net / db_mm
        mm_sweep.append((Kmid, k, resident_g, db_mm, traffic, net, rate))
        print(f"  {Kmid:>5}  {g_row:>7,} B  {k.placement:>9s}  "
              f"{k.spill_bytes:>9,} B  {resident_g:>6,}  {rate:>6.1%}  "
              f"{kib(db_mm):>7s}  {kib(traffic):>9s}  {kib(net):>7s}")
    print(f"  净收益封顶 = 2 × 行块数({rows}) × 可驻留({kib(192 * 1024)})"
          f" = {kib(2 * rows * 192 * 1024)}：K1 再涨，封顶不动、兑现率一路降")
    check("5a K1 ≤ 384 时 G 行块整块驻留，兑现率 100%",
          mm_sweep[0][6] == 1.0 and mm_sweep[1][6] == 1.0)
    check("5b K1=1024：spill 320 KiB/行块，兑现率 = 驻留/G行块 = 37.5%",
          mm_sweep[2][1].spill_bytes == 320 * 1024
          and abs(mm_sweep[2][6] - 0.375) < 1e-12)
    check("5c 净收益封顶：K1=1024 与 K1=4096 的净收益都 = 6 MiB",
          mm_sweep[2][5] == mm_sweep[3][5] == 6 * 1024 * 1024)
    check("5d 兑现率随 K1 单调不升（前两行同为 100%，K1 ≥ 1024 后严格下降）",
          all(a[6] >= b[6] for a, b in zip(mm_sweep, mm_sweep[1:]))
          and mm_sweep[1][6] > mm_sweep[3][6])
    check("5e 溢出全归 G 行块：消费者累加器恰满寄存器堆（64 KiB），"
          "spill == G行块 − 驻留",
          matmul_acc(tm, tn, m) == m.regfile_bytes
          and all(k.spill_bytes == tm * k1 * m.itemsize - res
                  for k1, k, res, *_r in mm_sweep))

    # ---- 6. 指令复杂度：epilogue 的增量随 K 摊薄 ----
    print("\n== 6. 指令复杂度：融合并进来的指令占多少 ==")
    print("  每个输出元素：MatMul 需 K 条 MAC 指令；epilogue 需 2 条（bias add + max）")
    print("   K        MAC   epilogue   增量占比")
    for Kc in (3, 8, 64, 512, 4096):
        print(f"  {Kc:>5}     {Kc:>5}      2       {2 / Kc:>7.2%}")
    check("6a 增量 = 2/K：K=64 时 3.1%，K=4096 时 0.05%",
          abs(2 / 64 - 0.03125) < 1e-12 and abs(2 / 4096 - 0.00048828125) < 1e-12)
    check("6b 贯穿示例 K=3：增量 66.7%——相对大但绝对小（省的是流量，不是指令）",
          abs(2 / 3 - 2 / 3) < 1e-12)
    print("  → 重计算生产者（K 大）配逐元素 epilogue 指令上近乎免费；")
    print("    但融合让 kernel 无法直接调用高度优化的独立算子库（假设 A8 的不计项）")

    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
