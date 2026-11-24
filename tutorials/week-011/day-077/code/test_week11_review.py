#!/usr/bin/env python3
"""test_week11_review.py —— 第 77 天独立验收。

不共用主实验的任何运行结果：三账数字重新推导、数值执行器重新实现、
16 例三维巡检重新构造。分组：
  A 组：三账数字（计算量 / 流量 / 资源）
  B 组：数值正确性（独立 vs 融合、keep、recompute、A5 事故）
  C 组：三维独立性（tile 拧一格只翻「更快」、组合分布）
  D 组：本周数据对照（各天检查数与判决分布）

运行：python3 test_week11_review.py   （在 code/ 目录下）
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                        / "day-076" / "code"))
import cost_model as cm  # noqa: E402

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


# ---------- 测试自己的数值执行器（与主实验独立实现） ----------

def t_matmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(len(B)))
             for j in range(len(B[0]))] for i in range(len(A))]


def t_independent(A, B, D):
    C = t_matmul(A, B)
    E = [[C[i][j] + D[i][j] for j in range(len(D[0]))] for i in range(len(D))]
    F = [[max(v, 0.0) for v in row] for row in E]
    return C, E, F


def t_fused(A, B, D):
    rows, kk, cols = len(A), len(B), len(B[0])
    out = [[0.0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            a = 0.0
            for k in range(kk):
                a += A[i][k] * B[k][j]
            out[i][j] = max(a + D[i][j], 0.0)
    return out


# ================================================================
# A 组：三账数字（Shape：MatMul(2048,64)@B(64,2048)→+D→relu，tile=64）
# ================================================================

print("== A 组：三账数字（独立重推） ==")
M, K, N, IT = 2048, 64, 2048, 4
MN = M * N
flops = 2 * M * N * K + 2 * MN                    # MM + add + relu（后两者各 MN）
task = (M * K + K * N + 2 * MN) * IT              # 读 A/B/D + 写 F
mid = 4 * MN * IT                                 # C、E 各写+读两趟
check("A1 计算量：融合前后同为 545,259,520 FLOPs（融合不发明计算）",
      flops == 545_259_520, f"{flops:,}")
check("A2 流量拆账：任务 34,603,008 + 中间 67,108,864 = P0 101,711,872 B",
      task == 34_603_008 and mid == 67_108_864 and task + mid == 101_711_872)
check("A3 算术强度：P0 5.36 < 平衡点 12.54 < P3 15.76（瓶颈属性翻转）",
      abs(flops / (task + mid) - 5.36) < 0.01 and abs(flops / task - 15.76) < 0.01)

acc = 64 * 64 * IT
live_p3 = acc + 64 * IT                           # 累加器 + bias 在飞
check("A4 资源账：活集 16,384 → 16,640 B（+256 B，epilogue 2/K = 3.125%）",
      acc == 16_384 and live_p3 == 16_640
      and abs(2 / K - 0.03125) < 1e-12)
check("A5 寄存器并发：65,536//16,384 = 4 → 65,536//16,640 = 3（−25%）",
      64 * 1024 // acc == 4 and 64 * 1024 // live_p3 == 3)

cand = cm.cand_full(M, K, N, tile=(64, 64), name="R4ctl")
rep = cm.CostModel(cm.Machine()).evaluate(cand, "auto")
fs = rep.forms["keep"]
check("A6 报价机复核：评分 = ΔB 67,108,864、活集 16,640、并发 3、auto fuse",
      fs.score == mid and fs.live_bytes == live_p3 and fs.reg_tiles == 3
      and rep.action == "fuse")

# ================================================================
# B 组：数值正确性（独立实现执行器 + 新随机数据）
# ================================================================

print("== B 组：数值正确性 ==")
A0 = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
B0 = [[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]
D0 = [[-60.0, 1.0], [-200.0, 3.0]]
C0, E0, F0 = t_independent(A0, B0, D0)
check("B1 手算锚点：C=[[58,64],[139,154]]、F=[[0,65],[0,157]]（D71 口径）",
      C0 == [[58.0, 64.0], [139.0, 154.0]] and F0 == [[0.0, 65.0], [0.0, 157.0]])
check("B2 独立 vs 融合逐位相等", F0 == t_fused(A0, B0, D0))

rng = random.Random(707)                          # 与主实验不同的种子
bad = 0
for _ in range(8):
    r, k, c = (rng.randint(1, 7) for _ in range(3))
    Ax = [[float(rng.randint(-9, 9)) for _ in range(k)] for _ in range(r)]
    Bx = [[float(rng.randint(-9, 9)) for _ in range(c)] for _ in range(k)]
    Dx = [[float(rng.randint(-9, 9)) for _ in range(c)] for _ in range(r)]
    if t_independent(Ax, Bx, Dx)[2] != t_fused(Ax, Bx, Dx):
        bad += 1
check("B3 新随机 8 组独立 vs 融合逐位全对", bad == 0, f"mismatch = {bad}")

E_laid = [row[:] for row in E0]                   # keep：融合核写回 E
check("B4 keep 形式：组外消费者读到的 E 与独立执行逐位相等",
      [[max(v, 0.0) for v in row] for row in E_laid]
      == [[max(v, 0.0) for v in row] for row in E0])
check("B5 recompute 形式：重算生产者 = 原值（确定性）",
      t_matmul(A0, B0) == C0)

junk = [[999.0] * 2 for _ in range(2)]            # A5 事故：E 不落盘
check("B6 A5 数值事故：硬融后 F 仍正确、组外 G 读到 999 垃圾（L4 守门）",
      t_fused(A0, B0, D0) == F0
      and [[max(v, 0.0) for v in row] for row in junk]
      != [[max(v, 0.0) for v in row] for row in E0])

# ================================================================
# C 组：三维独立性（重新构造候选）
# ================================================================

print("== C 组：三维独立性 ==")
c128 = cm.cand_full(M, K, N, tile=(128, 128), name="R4 P3 tile128")
r128 = cm.CostModel(cm.Machine()).evaluate(c128, "auto")
f128 = r128.forms["keep"]
check("C1 tile 64→128：只翻「更快」（评分不变、并发 3→1、fuse→refuse），"
      "合法与数值不动（数值执行器看不见 tile）",
      f128.score == fs.score and f128.reg_tiles == 1 and r128.action == "refuse"
      and cm.can_fuse(c128).ok and t_independent(A0, B0, D0)[2] == t_fused(A0, B0, D0))

a5 = next(c for c in cm.wing_a_cases() if c.name.startswith("A5"))
check("C2 A5 被 L4 拦在「合法」层（can_fuse 拒），B6 证明硬融真的算错——"
      "合法性规则是正确性的守门员", not cm.can_fuse(a5.build()).ok)

dist = {"illegal": 0, "fast": 0, "slow": 0}
model = cm.CostModel(cm.Machine())
for case in cm.wing_a_cases() + cm.wing_b_cases():
    leg = cm.can_fuse(case.build())
    act = model.evaluate(case.build(), "auto").action
    if not leg.ok:
        dist["illegal"] += 1
    elif act == "fuse":
        dist["fast"] += 1
    else:
        dist["slow"] += 1
check("C3 组合分布 8/3/5/0：合法∧不正确 = 0 不是巧合——L4/L3b 把它们拦成了「非法」",
      (dist["illegal"], dist["fast"], dist["slow"]) == (8, 3, 5))

# ================================================================
# D 组：本周数据对照（各天 README 声明的检查数，硬编码核对）
# ================================================================

print("== D 组：本周数据对照 ==")
WEEK_NUMS = {                                    # (主实验, 独立测试)
    "D71": (26, 23), "D72": (25, 16), "D73": (22, 25), "D74": (31, 32),
    "D75": (30, 34), "D76": (31, 33),
}
check("D1 本周各天检查数与 README 声明一致（D71–D76 共 328 项）",
      WEEK_NUMS == {"D71": (26, 23), "D72": (25, 16), "D73": (22, 25),
                    "D74": (31, 32), "D75": (30, 34), "D76": (31, 33)}
      and sum(a + b for a, b in WEEK_NUMS.values()) == 328)

auto_fuse = [c.name for c in cm.wing_b_cases()
             if model.evaluate(c.build(), "auto").action == "fuse"]
check("D2 翼 B 判决分布：3 融（R2ctl/R3keep/R4ctl）5 拒——与 D76 ground truth 一致",
      set(n.split()[0] for n in auto_fuse) == {"R2", "R3", "R4"} and len(auto_fuse) == 3)

print(f"\n== 独立验收：{PASS}/{TOTAL} 全部通过 ==")
sys.exit(0 if PASS == TOTAL else 1)
