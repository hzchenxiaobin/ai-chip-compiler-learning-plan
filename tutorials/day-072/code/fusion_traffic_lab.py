#!/usr/bin/env python3
"""fusion_traffic_lab.py —— 第 72 天主实验：融合减少的流量。

问题：MatMul → Add(Bias) → Relu 链独立执行时，中间 Tensor C、E 必须各
「写回 DRAM 一遍 + 读出一遍」（第 71 天记好的 64 B 两遍税）。融合把中间值
搬进寄存器，到底省多少字节？半融合又能省多少？

模型口径（写死在本文件，第 71 天同款）：
  1. 落盘 = 中间结果离开计算单元、写回全局内存（DRAM）；kernel 之间交接必须落盘。
  2. 仪器化执行器 = 真实计算（numpy）+ 显式记账：每个 kernel 的输入各读一遍、
     输出各写一遍（compulsory 理想下界）。
  3. 融合 kernel 的中间值驻留寄存器，不落盘（寄存器够用的理想化；代价第 73 天算）。
  4. 不计 kernel launch 开销、不计跨 kernel 缓存复用——今天的公式是
     「无缓存复用」口径下的收益（大 Tensor 或显式分层存储的加速器上成立）。
  5. FLOPs 不因融合改变（恒 32，第 71 天已数）；今天只算字节。

运行：python3 fusion_traffic_lab.py
"""

from __future__ import annotations

import numpy as np

PASSED = 0
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASSED, CHECKS
    CHECKS += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' ' + detail) if detail else ''}")
    if cond:
        PASSED += 1
    return cond


class Dram:
    """显式记账的 DRAM：kernel 的输入必须 read 一遍，输出必须 write 一遍。"""

    def __init__(self):
        self.reads = 0
        self.writes = 0

    def read(self, *arrays) -> None:
        for a in arrays:
            self.reads += a.nbytes

    def write(self, *arrays) -> None:
        for a in arrays:
            self.writes += a.nbytes

    @property
    def total(self) -> int:
        return self.reads + self.writes


# ---------------------------------------------------------------
# 贯穿示例（与第 71 天完全相同，保证账本可对上）
# A(2,3) @ B(3,2) → C(2,2)；C + D(2,2) → E(2,2)；relu(E) → F(2,2)
# ---------------------------------------------------------------

A0 = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
B0 = np.array([[7, 8], [9, 10], [11, 12]], dtype=np.float32)
D0 = np.array([[-60, 1], [-200, 3]], dtype=np.float32)   # 第 71 天同款：让 relu 真的干活
F0_EXPECTED = np.array([[0.0, 65.0], [0.0, 157.0]], dtype=np.float32)


def run_plan(plan: str, A: np.ndarray, B: np.ndarray, D: np.ndarray,
             dram: Dram) -> np.ndarray:
    """仪器化执行四种执行计划之一；返回最终结果 F。

    P0：三个 kernel 独立执行；P1：MatMul | FusedAddReLU；
    P2：FusedMatMulBias | ReLU；P3：FusedMatMulBiasReLU（单 kernel）。
    每个 kernel 前把输入 read 记账、后把输出 write 记账；
    融合 kernel 内部的中间值只存在于局部变量（「寄存器」），不记账。
    """
    if plan == "P0":
        C = A @ B
        dram.read(A, B)
        dram.write(C)
        E = C + D
        dram.read(C, D)
        dram.write(E)
        F = np.maximum(E, 0)
        dram.read(E)
        dram.write(F)
    elif plan == "P1":
        C = A @ B
        dram.read(A, B)
        dram.write(C)
        F = np.maximum(C + D, 0)      # FusedAddReLU：C+D 和 relu 在同一 kernel
        dram.read(C, D)
        dram.write(F)
    elif plan == "P2":
        E = A @ B + D                 # FusedMatMulBias：A@B 和 +D 在同一 kernel
        dram.read(A, B, D)
        dram.write(E)
        F = np.maximum(E, 0)
        dram.read(E)
        dram.write(F)
    elif plan == "P3":
        F = np.maximum(A @ B + D, 0)  # 全部在一个 kernel：C、E 只活在寄存器
        dram.read(A, B, D)
        dram.write(F)
    else:
        raise ValueError(plan)
    return F


def plan_bytes(M: int, K: int, N: int, itemsize: int = 4,
               bias: str = "full") -> dict[str, tuple[int, int]]:
    """公式：四种执行计划的 (读字节, 写字节)。bias='full' 是 (M,N)，'bc' 是 (N,)。"""
    be = M * N if bias == "full" else N
    plans = {
        "P0": (M * K + K * N + be + 2 * M * N, 3 * M * N),
        "P1": (M * K + K * N + be + M * N, 2 * M * N),
        "P2": (M * K + K * N + be + M * N, 2 * M * N),
        "P3": (M * K + K * N + be, M * N),
    }
    return {k: (r * itemsize, w * itemsize) for k, (r, w) in plans.items()}


def intermediates_bytes(M: int, N: int, itemsize: int = 4) -> int:
    """收益公式：全融合消掉的中间 Tensor 落盘字节。

    每个被消除的中间 Tensor 省两趟（写一遍 + 读一遍）：
    ΔB = 2 个中间 × 2 趟 × M·N 元素 × itemsize = 16·MN 字节。
    """
    return 2 * 2 * (M * N) * itemsize


def fusion_savings_passes(intermediates, itemsize: int) -> int:
    """多使用者推广的收益公式：每个中间 Tensor 能省几趟 DRAM。

    intermediates: [(名字, 元素数, 组内使用者数, 组外使用者数), ...]
    规则（独立执行 → 生产者与全部组内消费者进融合组）：
      - 组外使用者 = 0：写 1 趟 + 每个组内消费者的读 1 趟全部消失 → 省 (1 + 组内数) 趟；
      - 组外使用者 > 0：写必须保留（要给别人）、组外读必须保留 → 只省组内消费者的读。
    """
    saved = 0
    for _name, elems, n_in, n_out in intermediates:
        passes = (1 + n_in) if n_out == 0 else n_in
        saved += passes * elems * itemsize
    return saved


# ---------------------------------------------------------------
# 多使用者场景：E 还被外部 kernel G 消费（第 52 天的反例回到流量账上）
# ---------------------------------------------------------------

def run_multi_refuse(A, B, D, dram):
    """策略 A（第 52 天默认）：拒绝融合 → 账与 P0 相同，外加 G 的账。"""
    C = A @ B
    dram.read(A, B)
    dram.write(C)
    E = C + D
    dram.read(C, D)
    dram.write(E)
    F = np.maximum(E, 0)
    dram.read(E)
    dram.write(F)
    G_out = E.copy()               # 外部 kernel G：读 E、写自己的输出
    dram.read(E)
    dram.write(G_out)
    return F, E, G_out


def run_multi_keep(A, B, D, dram):
    """策略 B（第 52 天 keep）：融合三个算子，但 E 落盘留给 G。"""
    reg = A @ B                     # C 在寄存器
    reg = reg + D                   # E 在寄存器
    F = np.maximum(reg, 0)          # F 在寄存器
    dram.read(A, B, D)
    dram.write(F)
    E_mem = reg.copy()              # E 有外部使用者 → 必须落盘一次
    dram.write(E_mem)
    G_out = E_mem.copy()            # 外部 kernel G：读 DRAM 里的 E
    dram.read(E_mem)
    dram.write(G_out)
    return F, E_mem, G_out


# ---------------------------------------------------------------
# 主实验
# ---------------------------------------------------------------

def main() -> None:
    print("== 1. 口径卡 ==")
    print("  落盘 = 中间结果写回 DRAM；kernel 之间交接必须落盘（第 71 天同口径）")
    print("  仪器化执行器 = numpy 真实计算 + 显式记账（kernel 输入读一遍 / 输出写一遍）")
    print("  融合 kernel 的中间值驻留寄存器不落盘（寄存器够用的理想化，代价第 73 天算）")
    print("  不计 launch 开销与跨 kernel 缓存复用：今天的收益是「无缓存复用」口径")
    print("  贯穿示例：A(2,3)@B(3,2)→C(2,2)，C+D(2,2)→E(2,2)，relu(E)→F(2,2)，fp32")
    print(f"  数值链（第 71 天手算过）：C=[[58,64],[139,154]]，E=[[-2,65],[-61,157]]，"
          f"F=[[0,65],[0,157]]")

    # ---- 2. 仪器化对拍 ----
    print("\n== 2. 仪器化对拍：四种执行计划（公式 vs 真跑一遍的记账）==")
    plan_names = {
        "P0": "不融合",
        "P1": "MatMul | FusedAddReLU",
        "P2": "FusedMatMulBias | ReLU",
        "P3": "FusedMatMulBiasReLU",
    }
    plan_ids = {"P0": "2a", "P1": "2b", "P2": "2c", "P3": "2d"}
    results = {}
    for plan in ("P0", "P1", "P2", "P3"):
        dram = Dram()
        F = run_plan(plan, A0, B0, D0, dram)
        results[plan] = (F, dram)
        fr, fw = plan_bytes(2, 3, 2)[plan]
        print(f"  {plan} {plan_names[plan]}：读 {dram.reads} B + 写 {dram.writes} B"
              f" = {dram.total} B（公式 {fr}/{fw}/{fr + fw}）")
        check(f"{plan_ids[plan]} {plan} 仪器化 == 公式",
              dram.reads == fr and dram.writes == fw and dram.total == fr + fw)
    same = all(np.array_equal(results[p][0], F0_EXPECTED) for p in results)
    print(f"  四个计划的 F 逐位相等且等于手算值：{same}（F = [[0,65],[0,157]]）")
    check("2e 融合不改变数值：四个计划 F 相等", same)
    t0 = results["P0"][1].total
    t3 = results["P3"][1].total
    print(f"  融合前总流量 {t0} B → 融合后 {t3} B；第 71 天的 144 B 账本对上了")
    check("2f 与第 71 天账本一致：P0 == 144 B 且 P3 == 80 B", t0 == 144 and t3 == 80)

    # ---- 3. 融合流量对照表 ----
    print("\n== 3. 融合流量对照表（今天的核心产出）==")
    task = 24 + 24 + 16 + 16     # 读 A、B、D + 写 F：任务流量
    inter = {"P0": 64, "P1": 32, "P2": 32, "P3": 0}
    print("  执行计划                      kernel  读(B)  写(B)  总流量  任务  中间落盘  ΔB    省比   链AI")
    ai = {"P0": 32 / 144, "P1": 32 / 112, "P2": 32 / 112, "P3": 32 / 80}
    nk = {"P0": 3, "P1": 2, "P2": 2, "P3": 1}
    for plan in ("P0", "P1", "P2", "P3"):
        d = results[plan][1]
        delta = t0 - d.total
        frac = f"{delta / t0:.1%}" if delta else "—"
        print(f"  {plan} {plan_names[plan]:<24s}    {nk[plan]}   {d.reads:>4}  {d.writes:>4}"
              f"  {d.total:>5}   {task:>3}    {inter[plan]:>4}"
              f"   {(str(delta) if delta else '—'):>4}  {frac:>5}  {ai[plan]:.3f}")
    print(f"  融合前需要落盘的中间 Tensor 字节：C 32 B + E 32 B = 64 B"
          f"（写 32 + 读 32）；全融合后 = 0 B")
    print(f"  任务流量 = 读 A 24 + B 24 + D 16 + 写 F 16 = {task} B：四种计划都一样，"
          f"P3 恰好只付任务流量")
    check("3a 全融合 ΔB = 2 中间 × 2 趟 × 16 B = 64 B",
          t0 - t3 == intermediates_bytes(2, 2) == 64)
    check("3b 两算子融合 ΔB = 1 中间 × 2 趟 × 16 B = 32 B",
          t0 - results["P1"][1].total == 32 and t0 - results["P2"][1].total == 32)
    check("3c 融合后 = 融合前 − ΔB（P3 == 144 − 64 == 80）", t3 == t0 - 64)
    check("3d 拆账闭合：任务 80 + 中间落盘 == 总流量（四种计划）",
          all(task + inter[p] == results[p][1].total for p in inter))
    check("3e 全融合省比 = 64/144 = 4/9 ≈ 44.4%",
          abs((t0 - t3) / t0 - 4 / 9) < 1e-12)
    check("3f FLOPs 恒 32：链 AI 从 0.222 升到 0.400（仍远低于平衡点）",
          abs(ai["P3"] - 0.4) < 1e-12 and abs(ai["P0"] - 32 / 144) < 1e-12)
    check("3g P1 与 P2 字节数相同：本例 C、E 同尺寸（一般情况未必，见练习）",
          results["P1"][1].total == results["P2"][1].total)

    # ---- 4. Shape 扫描 ----
    print("\n== 4. Shape 扫描：绝对收益恒定，相对收益随形状变化 ==")
    print("  (a) 固定 M=N=256，扫 K（fp32）：ΔB = 16·MN = 1,048,576 B 恒定")
    print("      K       不融合(B)       融合(B)        ΔB(B)     省比")
    frac_k = []
    deltas_k = []
    for K in (1, 16, 64, 256, 1024, 4096):
        f0 = sum(plan_bytes(256, K, 256)["P0"])
        f3 = sum(plan_bytes(256, K, 256)["P3"])
        delta = f0 - f3
        frac_k.append(delta / f0)
        deltas_k.append(delta)
        print(f"    {K:>5}  {f0:>12,}  {f3:>12,}  {delta:>10,}  {delta / f0:>7.1%}")
    check("4a ΔB 与 K 无关：恒 1,048,576 B（16·MN）",
          all(d == 1048576 for d in deltas_k))
    print("  (b) 固定 K=64，扫 M=N=n（fp32）：省比爬向 2/3 的天花板")
    print("      n      不融合(B)       融合(B)        ΔB(B)     省比")
    frac_n = []
    for n in (16, 64, 256, 1024):
        f0 = sum(plan_bytes(n, 64, n)["P0"])
        f3 = sum(plan_bytes(n, 64, n)["P3"])
        delta = f0 - f3
        frac_n.append(delta / f0)
        print(f"    {n:>5}  {f0:>12,}  {f3:>12,}  {delta:>10,}  {delta / f0:>7.1%}")
    check("4b K↑ → 省比单调下降（M=N=256）",
          all(a > b for a, b in zip(frac_k, frac_k[1:])))
    check("4c n↑ → 省比单调上升（K=64，正方形）",
          all(a < b for a, b in zip(frac_n, frac_n[1:])))
    check("4d 省比恒 < 2/3（fraction = 4MN/(MK+KN+6MN) 的上界）",
          all(f < 2 / 3 for f in frac_k + frac_n))
    cross_a = frac_k[2]
    cross_b = frac_n[2]
    check("4e 两张表在 (n=256, K=64) 交点一致（61.5%）",
          abs(cross_a - cross_b) < 1e-12 and abs(cross_a - 0.6153846153846154) < 1e-12)
    print(f"  公式：省比 = 4MN / (MK + KN + 6MN)，正方形 M=N=n 时 = 2n/(K+3n)"
          f" → 上界 2/3 ≈ 66.7%")

    # ---- 5. 多使用者 ----
    print("\n== 5. 多使用者反例：E 还被外部 kernel G 消费（第 52 天策略回到账上）==")
    da, db = Dram(), Dram()
    F_a, E_a, G_a = run_multi_refuse(A0, B0, D0, da)
    F_b, E_b, G_b = run_multi_keep(A0, B0, D0, db)
    print(f"  策略 A 拒绝融合（第 52 天默认）：读 {da.reads} B + 写 {da.writes} B"
          f" = {da.total} B（P0 的 144 B + G 读 E 16 B + G 写 16 B）")
    print(f"  策略 B 融合但保留 E（keep）  ：读 {db.reads} B + 写 {db.writes} B"
          f" = {db.total} B（E 仍落盘，C 消失）")
    delta_multi = da.total - db.total
    print(f"  keep 策略省 ΔB = {delta_multi} B = C 的 2 趟（32 B）+ E 的 1 趟（16 B）")
    print(f"  拆解：C 落盘 {16 * 2} B → 0 B；E 落盘 {16 * 3} B → {16 * 2} B"
          f"（写和 G 的读保留，relu 的读消失）")
    check("5a 拒绝策略 ΔB = 0（账与 P0 相同，外加 G 的固定账）",
          da.total == 144 + 16 + 16)
    check("5b keep 策略 ΔB = 48 B（不是 64 B：E 的写与外部读省不掉）",
          delta_multi == 48)
    planner = fusion_savings_passes(
        [("C", 4, 1, 0), ("E", 4, 1, 1)], itemsize=4)
    check("5c 收益公式（多使用者版）== 仪器化：C 省 2 趟 + E 省 1 趟 = 48 B",
          planner == delta_multi == 48)
    check("5d 语义不变：两策略的 F、E、G_out 逐位相等",
          np.array_equal(F_a, F_b) and np.array_equal(E_a, E_b)
          and np.array_equal(G_a, G_b))

    # ---- 6. 改一个参数 ----
    print("\n== 6. 改一个参数再观察：bias 形状 (M,N) → (N,) 广播 ==")
    print("  真实模型里 bias 通常是 (N,)；M=N=1024，K=64，fp32")
    for bias in ("full", "bc"):
        f0 = sum(plan_bytes(1024, 64, 1024, bias=bias)["P0"])
        f3 = sum(plan_bytes(1024, 64, 1024, bias=bias)["P3"])
        name = "(M,N) 完整" if bias == "full" else "(N,)  广播"
        print(f"    bias {name}：不融合 {f0:>12,} B，融合 {f3:>12,} B，"
              f"ΔB {f0 - f3:>10,} B，省比 {(f0 - f3) / f0:.1%}")
    d_full = sum(plan_bytes(1024, 64, 1024)["P0"]) - sum(plan_bytes(1024, 64, 1024)["P3"])
    d_bc = sum(plan_bytes(1024, 64, 1024, bias="bc")["P0"]) - sum(
        plan_bytes(1024, 64, 1024, bias="bc")["P3"])
    check("6a ΔB 不随 bias 形状变：都是 16·MN = 16,777,216 B（16 MiB）",
          d_full == d_bc == 16 * 1024 * 1024)
    check("6b 广播让分母变小 → 省比从 65.3% 升到 78.0%",
          abs(d_full / sum(plan_bytes(1024, 64, 1024)["P0"]) - 0.6531) < 5e-4
          and abs(d_bc / sum(plan_bytes(1024, 64, 1024, bias="bc")["P0"]) - 0.7803) < 5e-4)
    d16 = sum(plan_bytes(256, 64, 256, itemsize=2)["P0"]) - sum(
        plan_bytes(256, 64, 256, itemsize=2)["P3"])
    print("  dtype 旁注：fp32 → fp16（itemsize 4 → 2），M=N=256，K=64")
    print(f"    ΔB 从 1,048,576 B 减半到 {d16:,} B；省比不变（所有项同比缩放）")
    check("6c fp16 下 ΔB 减半且省比不变（元素比与 dtype 无关）",
          d16 == 524288
          and abs(d16 / sum(plan_bytes(256, 64, 256, itemsize=2)["P0"])
                  - 1048576 / sum(plan_bytes(256, 64, 256)["P0"])) < 1e-12)

    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
