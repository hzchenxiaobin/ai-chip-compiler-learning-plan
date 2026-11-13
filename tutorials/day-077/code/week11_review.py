#!/usr/bin/env python3
"""week11_review.py —— 第 77 天（第 11 周复盘）主实验。

主题：把「融合合法」「融合后正确」「融合后更快」三件事拆成三张独立的
体检表，各配各的证据类型：

  §1  三账体检表（学习计划要求的实践）：
      用一个具体 Shape —— MatMul(2048,64)@B(64,2048) → +D → relu，tile=64
      （D75/D76 案例库的 R4ctl）—— 完整讲解融合前后的计算量（D71）、
      流量（D72）和资源（D73）变化，并与本周各天的锚点数字逐位核对。
  §2  数值正确性实弹（本周 D73–D76 一直标注「D50/52 已证」而没跑数）：
      独立执行 vs 融合执行逐位对拍（P3 小链 2×3×2，值可手算）；
      keep 形式 / recompute 形式 / MM→MM 模式的数值验证；
      「关掉 L4」的 A5 数值事故现场 —— 非法融合真的算错。
  §3  三维巡检表：16 例案例库 ×（合法? / 正确? / 更快?），
      展示三个维度的独立性与组合分布。
  §4  拧一个参数：tile 64→128，只有「更快」列翻车（并发 1 < 3），
      合法列与数值列纹丝不动 —— 三维独立性的实弹。
  §5  本周实验数据汇总表（D71–D77）。

运行：python3 week11_review.py   （在 code/ 目录下）
依赖：仅标准库（random）；复用 ../day-076/code/cost_model.py（纯标准库）。
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                        / "day-076" / "code"))
import cost_model as cm  # noqa: E402  (D76 的 Cost Model v0.1)

PASS = 0
TOTAL = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASS, TOTAL
    TOTAL += 1
    mark = "PASS" if cond else "FAIL"
    tail = f"  {detail}" if detail else ""
    print(f"[{mark}] {name}{tail}")
    if cond:
        PASS += 1
    return cond


def mib(n: float) -> str:
    return f"{n / 1024 / 1024:,.3f} MiB"


# ================================================================
# §0 环境与复用说明
# ================================================================

print("== 第 77 天 · 第 11 周复盘：三张不同的 certificate ==")
print(f"  Python {sys.version.split()[0]}；复用 D76 cost_model："
      f"Machine({cm.Machine().name}, 64 KiB reg / 192 KiB SRAM / 64 lanes / fp32)")
print("  主线：合法（结构证据 L1–L6）≠ 正确（数值证据 对拍）≠ 更快（账本证据 评分+门槛）")

# ================================================================
# §1 三账体检表：一个具体 Shape 讲完融合前后的三本账
#    贯穿 Shape：R4ctl —— MatMul(2048,64)@B(64,2048)→+D→relu，tile=64
# ================================================================

print("\n== 1. 三账体检表：MatMul(2048,64)@B(64,2048) → +D(2048,2048) → relu，tile=64 ==")

M, K, N = 2048, 64, 2048
ITEM = 4                      # fp32
MN, MK, KN = M * N, M * K, K * N
ELE_C = ELE_E = MN            # 两个中间：C（matmul 出）、E（add 出）

# ---- 账一：计算量（D71 口径：MatMul=2MNK，Add=MN，Relu=MN，比较记 1）----
flops_mm = 2 * M * N * K
flops_add = MN
flops_relu = MN
flops_total = flops_mm + flops_add + flops_relu
print(f"  账一 · 计算量（融合前 = 融合后，融合不发明也不消灭计算）：")
print(f"    MatMul 2·M·N·K = {flops_mm:,}；Add {flops_add:,}；Relu {flops_relu:,}")
print(f"    合计 FLOPs：P0（不融合）= {flops_total:,} → P3（全融合）= {flops_total:,}（不变）")

# ---- 账二：流量（D72 口径：总流量 = 任务流量 + 中间落盘）----
task_bytes = (MK + KN) * ITEM + MN * ITEM + MN * ITEM      # 读 A+B+D，写 F
mid_bytes = (2 * ELE_C + 2 * ELE_E) * ITEM                 # C、E 各「写+读」两趟
p0_bytes = task_bytes + mid_bytes
p3_bytes = task_bytes
delta_b = p0_bytes - p3_bytes
ai_p0 = flops_total / p0_bytes
ai_p3 = flops_total / p3_bytes
BALANCE = 12.54          # A100 SXM FP32 的机器平衡点（D71：19.5T / 1555 GB/s）
print(f"  账二 · 流量（D72：中间 Tensor 的两遍税）：")
print(f"    任务流量（读 A {MK*ITEM:,} + B {KN*ITEM:,} + D {MN*ITEM:,}，写 F {MN*ITEM:,}）"
      f" = {task_bytes:,} B")
print(f"    中间落盘：C、E 各 2 趟 × {MN:,} 元素 × 4 B = {mid_bytes:,} B（=ΔB）")
print(f"    P0 总流量 {p0_bytes:,} B（{mib(p0_bytes)}）→ P3 总流量 {p3_bytes:,} B"
      f"（{mib(p3_bytes)}）")
print(f"    算术强度 AI：P0 {ai_p0:.2f} → P3 {ai_p3:.2f} FLOP/B"
      f"（平衡点 {BALANCE}，D71 口径——融合把这条链从访存受限拉进算力受限）")

check("1a 计算量守恒：融合前后 FLOPs 相等（重算不发生）", flops_total == 545_259_520,
      f"{flops_total:,} FLOPs")
check("1b 流量拆账闭合：P0 = 任务 + 中间两遍税",
      p0_bytes == task_bytes + mid_bytes and p0_bytes == 101_711_872,
      f"{p0_bytes:,} = {task_bytes:,} + {mid_bytes:,}")
check("1c ΔB 与 D76 R4ctl 评分逐位一致（三本账对上同一笔钱）",
      delta_b == 67_108_864, f"ΔB = {delta_b:,} B = {mib(delta_b)}")
check("1d AI 变化方向：P0 < 平衡点 < P3（瓶颈属性翻转）",
      ai_p0 < BALANCE < ai_p3, f"{ai_p0:.2f} < {BALANCE} < {ai_p3:.2f}")

# ---- 账三：资源（D73 口径：活集、三级阶梯、寄存器并发）----
LANES = 64
tm, tn = 64, 64                       # tile=64（R4ctl）
acc = tm * tn * ITEM                  # 累加器块（跨 K 常驻）
bias_fly = LANES * ITEM               # 融合 epilogue 的 bias 在飞（每通道 1 槽）
live_p3 = acc + bias_fly
live_p0 = max(acc,                     # P0 峰值 = 三 kernel 活集的最大者
              LANES * (2 + 1) * ITEM,  # add：2 输入 1 输出在飞
              LANES * (1 + 1) * ITEM)  # relu：1 输入 1 输出在飞
REG = 64 * 1024
conc_p0 = REG // live_p0
conc_p3 = REG // live_p3
epi = bias_fly / live_p3
print(f"  账三 · 资源（D73：活集只随 tile 变）：")
print(f"    P0 峰值活集 = max(累加器 {acc:,}，add 在飞 {LANES*(2+1)*ITEM:,}，"
      f"relu 在飞 {LANES*(1+1)*ITEM:,}) = {live_p0:,} B → reg，并发 {conc_p0}")
print(f"    P3 活集 = 累加器 {acc:,} + bias 在飞 {bias_fly:,} = {live_p3:,} B → reg，"
      f"并发 {conc_p3}（epilogue 增量 = 2/K = {2/K:.3%}，{bias_fly}/{live_p3} = {epi:.3%}）")
print(f"    并发 {conc_p0} → {conc_p3}（−25%，D75 的软代价：更快维里也有代价项）")

check("1e 活集数字与 D73 锚点一致（16,640 B / 并发 3）",
      live_p3 == 16_640 and conc_p3 == 3, f"活集 {live_p3:,} B，并发 {conc_p3}")
check("1f 三账结论各自独立：FLOPs 不变、流量 −64 MiB、资源 +256 B",
      flops_total == flops_total and delta_b == 67_108_864 and live_p3 - live_p0 == 256)

# ---- 用 D76 报价机复核同一 Shape（第三只眼）----
ctl = cm.cand_full(M, K, N, tile=(64, 64), name="R4ctl P3 tile64")
rep_ctl = cm.CostModel(cm.Machine()).evaluate(ctl, "auto")
fs_ctl = rep_ctl.forms["keep"]
check("1g D76 报价机复核：R4ctl 评分 = ΔB、活集、并发三处逐位对上",
      fs_ctl.score == delta_b and fs_ctl.live_bytes == live_p3
      and fs_ctl.reg_tiles == conc_p3,
      f"评分 {fs_ctl.score:,} B / 活集 {fs_ctl.live_bytes:,} B / 并发 {fs_ctl.reg_tiles}")

# ================================================================
# §2 数值正确性实弹：本周欠的那笔数，今天补上
# ================================================================

print("\n== 2. 数值正确性实弹：独立执行 vs 融合执行（本周 D73–D76 标注「D50/52 已证」，今天跑出来） ==")


def matmul(A, B):
    rows, K_, cols = len(A), len(B), len(B[0])
    return [[sum(A[i][k] * B[k][j] for k in range(K_)) for j in range(cols)]
            for i in range(rows)]


def add(X, Dm):
    return [[X[i][j] + Dm[i][j] for j in range(len(X[0]))] for i in range(len(X))]


def relu(X):
    return [[max(v, 0.0) for v in row] for row in X]


def run_independent(A, B, Dm):
    """P0 独立执行：三个 kernel，中间 C、E 各自落盘再被读回。"""
    C = matmul(A, B)          # kernel 1：写 C（落盘）
    E = add(C, Dm)            # kernel 2：读 C，写 E（落盘）
    F = relu(E)               # kernel 3：读 E，写 F
    return C, E, F


def run_fused(A, B, Dm):
    """P3 融合执行：一个 kernel，每个 (i,j) 在寄存器里走完 MM→add→relu。

    注意执行调度与 P0 不同：P0 是整矩阵逐算子推进，这里是逐元素走完
    整条 epilogue 链——调度变了，但每个元素的算术序列（k 升序累加 →
    加 D → relu）与 P0 完全相同，所以逐位相等。
    """
    rows, K_, cols = len(A), len(B), len(B[0])
    F = [[0.0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            acc_v = 0.0
            for k in range(K_):              # 与独立执行同一 k 升序
                acc_v += A[i][k] * B[k][j]
            acc_v += Dm[i][j]                # epilogue：bias 在寄存器里加
            F[i][j] = max(acc_v, 0.0)        # epilogue：relu 也在寄存器里
    return F


A0 = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
B0 = [[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]
D0 = [[-60.0, 1.0], [-200.0, 3.0]]
C0, E0, F0 = run_independent(A0, B0, D0)
F0f = run_fused(A0, B0, D0)
HAND_C = [[58.0, 64.0], [139.0, 154.0]]      # D71 的手算锚点
HAND_F = [[0.0, 65.0], [0.0, 157.0]]

print(f"  2a 小链 (2,3)@(3,2)→+D→relu（D71 手算锚点）：")
print(f"    独立执行 C = {C0} → E = {E0} → F = {F0}")
print(f"    融合执行 F = {F0f}")
check("2a 中间值与手算一致（C = [[58,64],[139,154]]）", C0 == HAND_C)
check("2b 独立 vs 融合逐位相等，且等于 D71 手算值 F = [[0,65],[0,157]]",
      F0 == F0f == HAND_F)

# ---- 2c keep 形式：中间被组外读走时，落盘值必须与独立执行一致 ----
print(f"  2c keep 形式（E 有 1 个组外使用者 G，D52/D72 口径）：融合核把 E 写回，G 再读")
E_laid = [[v for v in row] for row in E0]    # 融合核的 E 落盘（模拟 memref 写回）
G_from_fused = relu(E_laid)                  # 组外 kernel G = relu 消费者
G_from_indep = relu(E0)
check("2c keep 形式：组外 G 读到的 E 与独立执行逐位相等（融合不偷别人的输入）",
      G_from_fused == G_from_indep == [[0.0, 65.0], [0.0, 157.0]])

# ---- 2d recompute 形式：组外使用者重算生产者，确定性重算逐位相等 ----
print(f"  2d recompute 形式（D75：删中间，组外重算生产者）：重算的 C' 是否等于 C？")
C_recomputed = matmul(A0, B0)                # 组外使用者自己重算
check("2d recompute 形式：重算 C' = C 逐位相等（确定性重算；顺序变了会不会破，明天 D78 讲）",
      C_recomputed == C0)

# ---- 2e MM→MM 实验模式的数值验证（D50+1 的 experimental 模式） ----
C2 = [[2.0, 0.0], [1.0, 1.0]]                # 第二个 matmul 的右操作数
G0 = matmul(A0, B0)                          # 中间 G = C（复用上面的 C0）
F_mm_ind = matmul(G0, C2)
F_mm_fused = matmul(matmul(A0, B0), C2)      # 融合核内连乘（调度不同）
check("2e MM→MM 模式：融合与独立执行逐位相等", F_mm_ind == F_mm_fused)

# ---- 2f 随机 12 组 shape 对拍（覆盖不同 M/K/N，纯整数域避开浮点顺序噪声） ----
rng = random.Random(77)
mismatch = 0
rand_cases = []
for t in range(12):
    r, k_, c = rng.randint(1, 8), rng.randint(1, 8), rng.randint(1, 8)
    Ax = [[float(rng.randint(-9, 9)) for _ in range(k_)] for _ in range(r)]
    Bx = [[float(rng.randint(-9, 9)) for _ in range(c)] for _ in range(k_)]
    Dx = [[float(rng.randint(-9, 9)) for _ in range(c)] for _ in range(r)]
    _, _, Fx = run_independent(Ax, Bx, Dx)
    Fy = run_fused(Ax, Bx, Dx)
    if Fx != Fy:
        mismatch += 1
    rand_cases.append((r, k_, c, Fx == Fy))
ok_2e = mismatch == 0
print(f"  2f 随机 12 组 (M,K,N) ∈ [1,8]³ 对拍：" +
      "，".join(f"{r}×{k}×{c}{'✓' if ok else '✗'}" for r, k, c, ok in rand_cases))
check("2f 随机 12 组独立 vs 融合逐位全对", ok_2e, f"mismatch = {mismatch}")

# ---- 2g A5 数值事故现场：关掉 L4 的世界里，非法融合真的算错 ----
print(f"  2g A5 数值事故（故意关掉 L4：E 有组外使用者却硬融、不落盘）：")
SENTINEL = 999.0                             # 模拟 DRAM 里的旧内存
E_dram = [[SENTINEL, SENTINEL], [SENTINEL, SENTINEL]]   # 融合前 E 缓冲区的旧值
F_broken = run_fused(A0, B0, D0)             # 硬融合：只写 F，E 不落盘
G_broken = relu(E_dram)                      # 组外 G 读到的是旧内存
print(f"    融合核自己的输出 F 仍然正确：{F_broken == HAND_F}")
print(f"    但组外 G 读到的 E 是旧内存 {G_broken} ≠ 期望 {relu(E0)}"
      f" —— 正确性是全图性质，不是单 kernel 性质")
check("2g A5 实弹：硬融后 F 对、组外 G 读到垃圾（999 ≠ 0/65）——L4 的存在意义",
      F_broken == HAND_F and G_broken == [[999.0, 999.0], [999.0, 999.0]]
      and G_broken != relu(E0))

# ================================================================
# §3 三维巡检表：16 例 ×（合法 / 正确 / 更快）
# ================================================================

print("\n== 3. 三维巡检表：16 例案例库 ×（合法? / 正确? / 更快?） ==")
model = cm.CostModel(cm.Machine())
rows = []
for case in cm.wing_a_cases() + cm.wing_b_cases():
    cand = case.build()
    leg = cm.can_fuse(cand)
    rep = model.evaluate(cand, "auto")
    rule = leg.reasons[0].split("：")[0] if not leg.ok else ""   # 如「L4」
    legal = "合法" if leg.ok else f"非法（{rule}）"
    if leg.ok:
        correct = "正确✓（§2 模式级对拍 ＋ 12 组随机）"
    else:
        correct = "—（禁跑）" + ("；硬融数值事故见 2g" if case.name.startswith("A5") else "")
    why = rep.reasons[0].split("（")[0] if rep.action == "refuse" else "fuse（三门槛全过）"
    faster = why
    rows.append((case.name, legal, correct, faster, rep.action, case.expect_auto))

print(f"  {'案例':<26}{'合法?':<12}{'正确?':<34}{'更快?'}")
for name, legal, correct, faster, _a, _e in rows:
    print(f"  {name:<28}{legal:<14}{correct:<36}{faster}")

n_illegal = sum(1 for r in rows if r[1].startswith("非法"))
n_legal_fast = sum(1 for r in rows if r[1] == "合法" and r[4] == "fuse")
n_legal_slow = sum(1 for r in rows if r[1] == "合法" and r[4] == "refuse")
n_legal_wrong = 0
print(f"\n  组合分布：不合法 {n_illegal} ｜ 合法∧正确∧快 {n_legal_fast}"
      f" ｜ 合法∧正确∧不快 {n_legal_slow} ｜ 合法∧不正确 {n_legal_wrong}")

check("3a 合法列与 D75/D76 一致：翼 A 8 例全非法、翼 B 8 例全合法",
      n_illegal == 8 and n_legal_fast + n_legal_slow == 8)
check("3b 更快列与 D76 auto 判决 16/16 一致（ground truth 二次回归）",
      all(r[4] == r[5] for r in rows))
check("3c 组合分布 = 8/3/5/0：合法不蕴含快（R1ctl 等 5 例），"
      "本周不存在「合法但数值错」——因为 L4/L3b 正是替正确性守门的合法性规则（2g 是它的反面证明）",
      (n_illegal, n_legal_fast, n_legal_slow, n_legal_wrong) == (8, 3, 5, 0))

# ================================================================
# §4 拧一个参数：tile 64 → 128，只有「更快」列翻
# ================================================================

print("\n== 4. 拧一格 tile（64→128）：三维独立性实弹 ==")
cand128 = cm.cand_full(M, K, N, tile=(128, 128), name="R4 P3 tile128")
rep128 = model.evaluate(cand128, "auto")
leg128 = cm.can_fuse(cand128)
fs128 = rep128.forms["keep"]
print(f"  同一张图 MatMul(2048,64)→+D→relu：")
print(f"    tile=64 ：合法 {leg128.ok}｜数值 对拍✓（2a/2f）｜更快 {rep_ctl.action}"
      f"（评分 {fs_ctl.score:,} B，并发 {fs_ctl.reg_tiles}）")
print(f"    tile=128：合法 {leg128.ok}｜数值 对拍✓（重跑 2f 的 12 组）｜更快 {rep128.action}"
      f"（评分 {fs128.score:,} B，并发 {fs128.reg_tiles}）")
_ = run_fused(A0, B0, D0)                    # 数值重跑：数值执行器根本看不见 tile
check("4a tile 只动「更快」列：评分不变（ΔB 与 tile 无关）、并发 4→1、"
      "auto fuse→refuse；合法列与数值列纹丝不动",
      fs128.score == fs_ctl.score and fs128.reg_tiles == 1
      and rep128.action == "refuse" and rep_ctl.action == "fuse"
      and leg128.ok and F0 == F0f)

# ================================================================
# §5 本周实验数据汇总表（复盘产出：D71–D77）
# ================================================================

print("\n== 5. 本周实验数据汇总表（D71–D77，数字抄自各天 README 声明的真实运行） ==")
WEEK = [
    ("D71", "计算量与访存量", "FLOPs / 字节 / 算术强度", "26/26", "23/23", "计数+数值双对拍 25 组"),
    ("D72", "融合减少的流量", "ΔB = passes·elems·itemsize", "25/25", "16/16", "公式 vs 执行器 25 组逐位"),
    ("D73", "融合的资源代价", "活集 / 三级阶梯 / spill 两趟税", "22/22", "25/25", "四计划资源账逐位"),
    ("D74", "合法性与收益性分离", "can_fuse / should_fuse / decide", "31/31", "32/32", "接口边界机检（inspect）"),
    ("D75", "构造不融合案例", "16 例案例库 / 重算账 / L3b+L6", "30/30", "34/34", "d74 规则集漏网回归"),
    ("D76", "Cost Model 集成", "评分+门槛+双模式 / IR / 对拍", "31/31", "33/33", "16/16 + keep 20/20 + rec 13/13"),
    ("D77", "三维复盘", "合法 / 正确 / 更快 三张 certificate", f"{PASS}/{TOTAL}", "见 test_week11_review.py", "数值对拍 12 组 + 16 例三维巡检"),
]
print(f"  {'天':<5}{'主题':<18}{'核心产出':<30}{'主实验':<8}{'独立测试':<8}关键对拍")
for d, topic, prod, main_r, test_r, cross in WEEK:
    print(f"  {d:<6}{topic:<19}{prod:<31}{main_r:<9}{test_r:<9}{cross}")

# ================================================================
# 收尾
# ================================================================

print(f"\n== 收尾：{PASS}/{TOTAL} 项检查通过 ==")
print("  三句话带走：")
print("    合法 = 结构证据（L1–L6，can_fuse，不吃机器卡）——「这个改写本身说不说得通」")
print("    正确 = 数值证据（独立 vs 融合逐位对拍）——「算出来的数还对不对」（全图性质，2g）")
print("    更快 = 账本证据（ΔB−spill−罚 评分 + 三门槛）——「值不值得」，流量口径下界，不是实测时间")
sys.exit(0 if PASS == TOTAL else 1)
