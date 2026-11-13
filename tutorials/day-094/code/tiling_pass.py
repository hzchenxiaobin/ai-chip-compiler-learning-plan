#!/usr/bin/env python3
"""第 94 天：实现基础 Tiling——块循环、点循环与整除契约。

学习计划（第 94 天）：
  学习：Tile 外层循环、点循环和尾部处理。
  实践：对 MatMul 三维循环进行 Tiling，先保证静态 Shape 和整除场景正确。
  产出：Tiled IR 和整除测试。

昨天（Day 93）的 LoopOptions 把 tile 收进了配置，但第④道消费门把它拒了
（"Tiling 的 lowering 是 Day 94 的内容"）。今天兑现这句话：

  TilingPattern：mini.matmul → 6 层循环（3 层块循环 × 3 层点循环）
      块循环   for %i0 = 0 to M step tile_m     # 每圈跳一整块
      点循环   for %i  = %i0 to %i0+tile_m      # 块内一圈一行（lb 是块循环的 iv）
      累加链   k 点循环块内走 iter_args（寄存器）；跨 k-块走 C 的读-改-写（内存）
               → 跨块语义与 Day 92「形态 B」同构：需要 init nest 铺零起点
      尾部     不整除时点循环上界 %k0+Tk 会越过 K——尾部处理是 Day 95 的内容，
               今天由消费门 fail-closed 拒绝（绝不静默生成越界 IR）

两个新部件（都是「扩展」而不是「修改」——Day 90/92/93 的文件一行不动）：
  ① arith.addi 注册进合法算子表：真实 MLIR 的 Tiling 分解恰好生成
     arith.addi 算块内上界（%ub = %i0 + %cTm）；ConversionTarget::addLegalOp
     干的就是这件事——我们在注册表里登记它
  ② TilingInterp：给 Day 87 的解释执行器加 index 加法（子类覆写 exec_op）

检查套件（真实运行，本机未安装 MLIR，与 Day 57~93 同口径）：
  TL1  结构不变量：Tiled IR 恒 31 op（walk 序列逐项对照）；块循环 step=块尺寸、
       点循环 trip=块尺寸；常量多重集 = {0,1,M,N,K,Tm,Tn,Tk}
  TL2  语义不变性：小例 8 种整除 tile ＋ 16³ 五种全部位等价；(i,j,k) 三元组
       从真实日志重建后恰好全覆盖一次；每个 (i,j) 的 k 顺序 == 0..K-1
  TL3  流量公式：A/B 的 load 总数与 tile 无关（恒 2·M·N·K）；
       C 读 = C 写 = M·N·K/Tk（Tk 一个进公式）＋ M·N 清零
  TL4  整除测试（计划点名的交付物）：小例 8 ＋ 16³ 10 ＋ 非方形/单维 多组，
       全部「31 op＋位等价＋零越界＋零未初始化读」
  TL5  缓存收益实验：16³ 真实轨迹回放，untiled i-j-k / i-k-j vs
       tiled 2x2x2 / 4x4x4 / 8x8x8——512B 与 1KB 两个容量档
  TL6  消费契约更新：tile 开张（Day 93 被拒的 tile=2x2x3 今天端到端跑通）；
       不整除 → 拒（点名 Day 95）；unroll → 拒（Day 96 口径不变）；
       tile×非默认 order → 拒（Day 97）；块比维度大 → 第③道门 error

用法：
    python3 tiling_pass.py                        # TL1~TL6 全跑，写 outputs/
    python3 tiling_pass.py --config "tile=2x2x1"  # 一份配置串的完整旅程（四道门→端到端）
    python3 tiling_pass.py --demo nondiv          # 复现「绕过配置层的非整除」→ 探针拦下
    python3 tiling_pass.py --demo acczero         # 复现「跨块累加丢失」（经典 Tiling bug）
    python3 tiling_pass.py --demo noinit          # 复现「忘记清零 nest」（Day 92 教训复验）

产出（outputs/）：
    tiled-ir.txt         两份 Tiled IR（tile=2x2x1 多 k-块 ＋ tile=2x2x3 Day 93 预告的配置）
    divisible-tests.txt  整除测试汇总表（计划点名的交付物）
    cache-blocking.txt   缓存收益实验：真实轨迹回放，untiled vs tiled
    consume-guard.txt    消费契约实录：六份配置的真实命运
"""

from __future__ import annotations

import argparse
import platform
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "day-093" / "code"))
sys.path.insert(0, str(HERE.parent.parent / "day-092" / "code"))
sys.path.insert(0, str(HERE.parent.parent / "day-090" / "code"))

import loop_options as lo   # noqa: E402  Day 93 的配置对象——只取不改（第①②③道门）
import order_pass as od     # noqa: E402  Day 92 的工程——只取不改（untiled 基线/缓存回放）
import shape_pass as sp     # noqa: E402  Day 90 的工程——只取不改（IR 内核/执行器）
from shape_pass import (    # noqa: E402
    ConversionPattern, Interp, LoopSpec, MemRefOOBError, Value, build_main_graph,
    is_static, make_inputs, make_memref, memref_shape, print_module,
    reference_matmul, run_pass, trip_count,
)

# 今天的新算子：真实 MLIR 的 Tiling 分解恰好用 arith.addi 算块内上界。
# 等价于 ConversionTarget::addLegalOp("arith.addi")——注册表登记，不是改文件。
sp.TARGET_LEGAL.add("arith.addi")

OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

SEED = 94          # 第 94 天自己的输入种子（可复现）
M, K, N = 2, 3, 2  # 贯穿例：2×3 乘 3×2 → 2×2（与 Day 92/93 同形状，种子不同）
SIM_SHAPE = od.SIM_SHAPE   # (16,16,16)：缓存实验形状（Day 92 口径）
SIM_CACHES = [32, 64, 256]  # 512B / 1KB / 4KB（Day 92 的两个翻转档 + 全装下基线）

PASS, FAIL = 0, 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"：{detail}" if detail else ""))
    return ok


def env_line():
    return (f"环境：{platform.system()} {platform.machine()}, "
            f"Python {platform.python_version()}, numpy {np.__version__}; "
            f"本机未安装 MLIR（Day 57~93 口径：Python 复刻 DialectConversion 语义仿真）")


def tname(tile):
    return "x".join(str(t) for t in tile)


# ============================================================
# 部件一：TilingInterp——给 Day 87 执行器加 index 加法（子类扩展）
# ============================================================

class TilingInterp(Interp):
    """解释执行器（Day 87 原样 ＋ 今天的 arith.addi）。

    Day 87~93 的执行器认得 load/store/mulf/addf/scf.for(iter_args)，但没有
    整数加法——而 Tiling 的点循环上界是 %i0 + tile_m，每圈都要现算。真实
    MLIR 的 Tiling 分解同样会生成 arith.addi；我们在子类里补上它的语义，
    其余 op 全部走父类（Day 88~90 的探针：访存日志/iv 轨迹/按维越界原样生效）。
    """

    def exec_op(self, op):
        if op.name == "arith.addi":
            self.env[id(op.results[0])] = (int(self.val(op.operands[0]))
                                           + int(self.val(op.operands[1])))
            return
        super().exec_op(op)


# ============================================================
# 部件二：TilingPattern——mini.matmul → 6 层循环（今天的主角）
# ============================================================

class TilingPattern(ConversionPattern):
    """把 Day 89 的三重循环 i-j-k 切成方块：3 层块循环 ＋ 3 层点循环。

    生成的结构（tile = (tile_m, tile_n, tile_k)，整除契约由配置层把关）：

        清零 nest：for i { for j { store %zero → C[i,j] } }     ← Day 92 形态 B 同款
        for %i0 = 0 to M step tile_m      ← 块循环（strip）
          for %j0 = 0 to N step tile_n
            for %k0 = 0 to K step tile_k  ← 归约维也被切块
              %ub_i = arith.addi %i0, %cTm
              for %i = %i0 to %ub_i step 1        ← 点循环（intra-tile）
                %ub_j = arith.addi %j0, %cTn
                for %j = %j0 to %ub_j step 1
                  %cv = load C[%i,%j]             ← 上一个 k-块的部分和（读端）
                  %ub_k = arith.addi %k0, %cTk
                  %acc = for %k = %k0 to %ub_k iter_args(%acc = %cv)
                           load A / load B / mulf / addf / yield   ← 块内寄存器累加
                  store %acc → C[%i,%j]            ← 本块部分和落盘（写端）

    两条累加通道（今天最重要的设计决定）：
      · 块内：k 点循环带 iter_args——Tk 次乘加在寄存器里完成，不碰内存；
      · 跨块：k 被切成 K/Tk 个块后，(i,j) 点循环被外层 k0 反复重访，
        寄存器存不下 Tm×Tn 个部分和 → 部分和落回 C（读-改-写），
        这正是 Day 92「k 不在最内层 → 累加器住内存」的结论在 Tiling 世界的重现，
        init nest 因此必须存在（否则第一个块读到垃圾——Day 87 的内存模型）。

    注入旋钮（§6 的三个真实错误用，默认全关＝正确形态；与 Day 90 的猎杀矩阵同款）：
      · acc_from_zero ：k 点循环的 iter_args 初值写成 %zero 而不是 %cv
                        → 前几个 k-块的和凭空消失（跨块累加丢失——经典 bug）
      · init          ：关掉清零 nest → 第一个块读到垃圾（Day 92 OT5 的复验）
    """

    root_name = "mini.matmul"
    benefit = 1
    debug_name = "TilingPattern"

    def __init__(self, tile, init=True, acc_from_zero=False):
        self.tile = tuple(int(t) for t in tile)
        assert len(self.tile) == 3 and all(t >= 1 for t in self.tile), \
            f"tile 必须是 3 个正整数，拿到 {tile}"
        self.init = init
        self.acc_from_zero = acc_from_zero
        self.tile_specs = []     # 块循环的出生证明（LoopSpec）
        self.point_specs = []    # 点循环的出生证明

    def matchAndRewrite(self, op, adaptor, rewriter):
        # ---------- match：与 Day 89~92 同一套契约 ----------
        if len(adaptor.operands) != 2:
            return rewriter.notifyMatchFailure(
                op, f"期望 2 个操作数，实际 {len(adaptor.operands)}")
        ta, tb = adaptor.operands[0].type, adaptor.operands[1].type
        sa, sb = memref_shape(ta), memref_shape(tb)
        if sa is None or sb is None:
            return rewriter.notifyMatchFailure(
                op, f"操作数还不是 memref（拿到 {ta} / {tb}）")
        if len(sa) != 2 or len(sb) != 2:
            return rewriter.notifyMatchFailure(
                op, f"只支持 2 维矩阵乘，拿到 A{sa} @ B{sb}")
        if not (is_static(sa) and is_static(sb)):
            return rewriter.notifyMatchFailure(
                op, f"动态维度（A{sa} @ B{sb}）：静态 Pattern 宁拒不猜（Day 90 口径）")
        if sa[1] != sb[0]:
            return rewriter.notifyMatchFailure(
                op, f"内维不匹配：A.shape[1]={sa[1]} ≠ B.shape[0]={sb[0]}")
        M, K = sa
        N = sb[1]
        a, b = adaptor.operands[0], adaptor.operands[1]
        Tm, Tn, Tk = self.tile

        # ---------- rewrite：一切修改走 rewriter（Day 86 起的事务契约） ----------
        dim = {"i": M, "j": N, "k": K}
        tsz = {"i": Tm, "j": Tn, "k": Tk}
        self.tile_specs = [
            LoopSpec("%i0", 0, M, Tm, f"M/tile_m = {M // Tm} 个 i-块（step = tile_m）"),
            LoopSpec("%j0", 0, N, Tn, f"N/tile_n = {N // Tn} 个 j-块（step = tile_n）"),
            LoopSpec("%k0", 0, K, Tk, f"K/tile_k = {K // Tk} 个 k-块（归约维也被切）"),
        ]
        self.point_specs = [
            LoopSpec("%i", 0, Tm, 1, "lb = %i0（块起点）；ub = addi(%i0, %cTm) = 起点+块尺寸"),
            LoopSpec("%j", 0, Tn, 1, "lb = %j0；ub = addi(%j0, %cTn)"),
            LoopSpec("%k", 0, Tk, 1, "lb = %k0；ub = addi(%k0, %cTk)——trip 恒 = 块尺寸（整除契约）"),
        ]

        # ① 输出缓冲 ② 零起点 ③ 8 个 index 常量（Day 87 的积木 ＋ 今天新增 3 个块尺寸）
        alloc = rewriter.create(
            "memref.alloc", result_names=["%c"], result_types=[make_memref((M, N))],
            comments=[f"输出缓冲 {M * N * 4} B：alloc 不清零（D87）——k 被切块后",
                      "部分和住在 C 里，所以下面还要铺清零 nest"])
        zero = rewriter.create(
            "arith.constant", result_names=["%zero"], result_types=["f32"],
            attrs={"value": 0.0},
            comments=["零起点：喂给清零 nest（跨块内存累加的零起点——Day 92 形态 B 的教训）"])
        cvals = [("c0", 0), ("c1", 1), ("cM", M), ("cN", N), ("cK", K),
                 ("cTm", Tm), ("cTn", Tn), ("cTk", Tk)]
        consts = {}
        for nm, v in cvals:
            consts[nm] = rewriter.create(
                "arith.constant", result_names=[f"%{nm}"], result_types=["index"],
                attrs={"value": v},
                comments=[_CONST_DOC[nm].format(M=M, N=N, K=K, Tm=Tm, Tn=Tn, Tk=Tk,
                                               md=M // Tm, nd=N // Tn, kd=K // Tk)])

        # 归纳变量：块循环用 %i0/%j0/%k0；点循环用 %i/%j/%k（清零 nest 复用 %i/%j）
        iv0 = {v: Value(f"%{v}0", "index") for v in "ijk"}
        iv = {v: Value(f"%{v}", "index") for v in "ijk"}

        # ④ 清零 nest：跨块累加的内存零起点（k0 > 0 的块读到的就是这里的 0）
        if self.init:
            stz = rewriter.create(
                "memref.store", operands=[zero.results[0], alloc.results[0],
                                           iv["i"], iv["j"]],
                comments=["清零：C[i,j] ← 0——第一个 k-块读到的零起点"])
            fjz = rewriter.create(
                "scf.for", operands=[consts["c0"].results[0], consts["cN"].results[0],
                                      consts["c1"].results[0]],
                attrs={"iv": "%j", "iv_value": iv["j"]}, body=[stz],
                comments=[f"四要素：[0,{N}) step 1，trip = {N}"])
            rewriter.create(
                "scf.for", operands=[consts["c0"].results[0], consts["cM"].results[0],
                                      consts["c1"].results[0]],
                attrs={"iv": "%i", "iv_value": iv["i"]}, body=[fjz],
                comments=[f"清零 nest：[0,{M}) step 1，trip = {M}——M·N 次 store"])

        # ⑤ 主循环 nest：从最内层（k 点循环）往外建
        acc_arg = Value("%acc", "f32")
        xa = rewriter.create(
            "memref.load", operands=[a, iv["i"], iv["k"]],
            result_names=["%xa"], result_types=["f32"],
            comments=["读 A：A[i,k]——i、k 都是点循环 iv（块内真实坐标）"])
        xb = rewriter.create(
            "memref.load", operands=[b, iv["k"], iv["j"]],
            result_names=["%xb"], result_types=["f32"],
            comments=["读 B：B[k,j]——与 Day 89 同一公式，换的只是循环骨架"])
        p = rewriter.create("arith.mulf", operands=[xa.results[0], xb.results[0]],
                            result_names=["%p"], result_types=["f32"],
                            comments=["%p = A[i,k]·B[k,j]"])
        s = rewriter.create("arith.addf", operands=[acc_arg, p.results[0]],
                            result_names=["%s"], result_types=["f32"],
                            comments=["%acc（区域参数）＋ %p → %s——k 升序舍入顺序不变"])
        yld = rewriter.create("scf.yield", operands=[s.results[0]],
                              comments=["写回通道：本趟 %s → 下一趟 %acc（块内寄存器累加）"])

        cv = rewriter.create(
            "memref.load", operands=[alloc.results[0], iv["i"], iv["j"]],
            result_names=["%cv"], result_types=["f32"],
            comments=["读 C：上一个 k-块留下的部分和——跨块累加的读端",
                      "（k0=0 时读到的是清零 nest 铺的 0）"])
        ub_k = rewriter.create(
            "arith.addi", operands=[iv0["k"], consts["cTk"].results[0]],
            result_names=["%ub_k"], result_types=["index"],
            comments=["%ub_k = %k0 + tile_k——点循环上界每圈现算（真实 MLIR 同款）"])
        acc_init = zero.results[0] if self.acc_from_zero else cv.results[0]
        init_note = ("错误旋钮 acc_from_zero：初值写成 %zero——每块都从 0 重来，"
                     "前面块的和全部丢失" if self.acc_from_zero else
                     "iter_args 初值 = %cv（上一块的终点）——跨块接力棒")
        f_k = rewriter.create(
            "scf.for", operands=[iv0["k"], ub_k.results[0], consts["c1"].results[0],
                                 acc_init],
            result_names=["%acc"], result_types=["f32"],
            attrs={"iv": "%k", "iv_value": iv["k"],
                   "iter_names": ["%acc"], "iter_args": [acc_arg]},
            body=[xa, xb, p, s, yld],
            comments=[f"点循环 k：[%k0, %k0+{Tk}) step 1，trip = {Tk}（整除契约：块起点+块尺寸 ≤ K={K}）",
                      f"块内寄存器累加：{init_note}"])
        stm = rewriter.create(
            "memref.store", operands=[f_k.results[0], alloc.results[0], iv["i"], iv["j"]],
            comments=["写 C：本块部分和落盘——每个 k-块各写一次（共 K/tile_k 次）"])

        ub_j = rewriter.create(
            "arith.addi", operands=[iv0["j"], consts["cTn"].results[0]],
            result_names=["%ub_j"], result_types=["index"],
            comments=[f"%ub_j = %j0 + tile_n（{N // Tn} 个 j-块的边界）"])
        f_j = rewriter.create(
            "scf.for", operands=[iv0["j"], ub_j.results[0], consts["c1"].results[0]],
            attrs={"iv": "%j", "iv_value": iv["j"]},
            body=[cv, ub_k, f_k, stm],
            comments=[f"点循环 j：[%j0, %j0+{Tn}) step 1，trip = {Tn}",
                      "循环体四件事：读部分和 → 算 k 上界 → 块内乘加 → 写回"])

        ub_i = rewriter.create(
            "arith.addi", operands=[iv0["i"], consts["cTm"].results[0]],
            result_names=["%ub_i"], result_types=["index"],
            comments=[f"%ub_i = %i0 + tile_m（{M // Tm} 个 i-块的边界）"])
        f_i = rewriter.create(
            "scf.for", operands=[iv0["i"], ub_i.results[0], consts["c1"].results[0]],
            attrs={"iv": "%i", "iv_value": iv["i"]},
            body=[ub_j, f_j],
            comments=[f"点循环 i：[%i0, %i0+{Tm}) step 1，trip = {Tm}"])

        f_k0 = rewriter.create(
            "scf.for", operands=[consts["c0"].results[0], consts["cK"].results[0],
                                  consts["cTk"].results[0]],
            attrs={"iv": "%k0", "iv_value": iv0["k"]},
            body=[ub_i, f_i],
            comments=[*loop_note(self.tile_specs[2]),
                      f"归约维被切成 {K // Tk} 块——块内寄存器、跨块内存（今天的核心设计）"])
        f_j0 = rewriter.create(
            "scf.for", operands=[consts["c0"].results[0], consts["cN"].results[0],
                                  consts["cTn"].results[0]],
            attrs={"iv": "%j0", "iv_value": iv0["j"]},
            body=[f_k0],
            comments=[*loop_note(self.tile_specs[1]),
                      "j0 每跳一格，B 的列面板和 C 的方块都换一批"])
        rewriter.create(
            "scf.for", operands=[consts["c0"].results[0], consts["cM"].results[0],
                                 consts["cTm"].results[0]],
            attrs={"iv": "%i0", "iv_value": iv0["i"]},
            body=[f_j0],
            comments=[*loop_note(self.tile_specs[0]),
                      "最外层块循环 i0：step = tile_m——每圈跳一整块（今天出生的结构）"])
        rewriter.replaceOp(op, [alloc.results[0]])
        return True


_CONST_DOC = {
    "c0": "常量 0：所有循环的 lb",
    "c1": "常量 1：点循环与清零 nest 的 step",
    "cM": "常量 M = {M}：i 块循环的 ub",
    "cN": "常量 N = {N}：j 块循环的 ub",
    "cK": "常量 K = {K}：k 块循环的 ub（归约维）",
    "cTm": "常量 tile_m = {Tm}：i 块尺寸——今天从 LoopOptions.tile 来（Day 93 的字段）",
    "cTn": "常量 tile_n = {Tn}：j 块尺寸",
    "cTk": "常量 tile_k = {Tk}：k 块尺寸——K/Tk = {kd} 个 k-块，跨块累加的接力次数",
}


def loop_note(spec):
    return [f"块循环：[{spec.lb},{spec.ub}) step {spec.step}，trip = {trip_count(spec)}",
            f"ub 来源：{spec.ub_source}"]


# 31 op 的 walk 先序（结构是数据：与形状、块尺寸无关）
TILED_BODY = (["func.func", "memref.alloc", "arith.constant"]        # func/alloc/%zero
              + ["arith.constant"] * 8                              # c0,c1,cM,cN,cK,cTm,cTn,cTk
              + ["scf.for", "scf.for", "memref.store"]               # 清零 nest
              + ["scf.for"] * 3                                     # 块循环 i0/j0/k0
              + ["arith.addi", "scf.for"]                            # %ub_i + 点循环 i
              + ["arith.addi", "scf.for"]                            # %ub_j + 点循环 j
              + ["memref.load", "arith.addi", "scf.for"]             # %cv, %ub_k, 点循环 k
              + ["memref.load", "memref.load", "arith.mulf", "arith.addf",
                 "scf.yield", "memref.store", "func.return"])        # 合计 31 op


# ============================================================
# 运行工具：跑一次「转换＋解释执行」，带回真实访存日志
# ============================================================

def run_tiled(tile, m, k, n, seed=SEED, init=True, acc_from_zero=False):
    """TilingPattern 版的 run_order：转换 → TilingInterp 执行 → 收集探针数据。"""
    func = build_main_graph(m, k, n)
    pat = TilingPattern(tile, init=init, acc_from_zero=acc_from_zero)
    _, res = run_pass(func, "full", patterns=[pat])
    if not res.ok:
        return dict(res=res, pat=pat, func=func, interp=None, C=None,
                    err=None, A=None, B=None, ref=None)
    A, B = make_inputs(m, k, n, seed)
    interp = TilingInterp({"%a": A, "%b": B})
    err = None
    try:
        interp.run(func)
    except MemRefOOBError as exc:
        err = str(exc)
    C = None
    if err is None and interp.ret is not None:
        C = np.array([cell[1] for cell in interp.mem[interp.ret]],
                     dtype=np.float32).reshape(m, n)
    return dict(res=res, pat=pat, func=func, interp=interp, C=C, err=err,
                A=A, B=B, ref=reference_matmul(A, B))


def traffic_of(r):
    """从真实访存日志数出各流流量（清零段单列——它不是主循环的流量）。"""
    log = r["interp"].access_log
    counts = Counter((kd, m_) for kd, m_, *_ in log)
    init_len = _mn_of(r) if r["pat"].init else 0
    return dict(a_loads=counts[("load", "%a")], b_loads=counts[("load", "%b")],
                c_loads=counts[("load", "%c")],
                c_stores=counts[("store", "%c")] - init_len,
                init_stores=init_len)


def _mn_of(r):
    # 清零 nest 的 store 数 = M·N（从 alloc 类型读形状，不猜）
    for op in r["func"].walk():
        if op.name == "memref.alloc":
            shp = memref_shape(op.results[0].type)
            return shp[0] * shp[1]
    return 0


def triples_of(r):
    """从真实访存日志重建 (i,j,k) 访问三元组序列。

    k 点循环体每趟先 load A 再 load B（相邻两条日志）——配对即得一次乘法的坐标。
    """
    log = r["interp"].access_log
    out, pend = [], None
    for kd, m_, idx, addr, v in log:
        if kd == "load" and m_ == "%a":
            pend = idx                       # (i, k)
        elif kd == "load" and m_ == "%b" and pend is not None:
            out.append((pend[0], idx[1], pend[1]))   # (i, j, k)
            pend = None
    return out


# ============================================================
# 消费契约（第 94 天版）：tile 开张——四道门今天怎么把守
# ============================================================

def run_with_config(cfg, m=M, k=K, n=N, seed=SEED):
    """一份配置串/LoopOptions → 端到端。门序沿用 Day 93：③形状门在前、④消费门在后。

    今天第④道门的更新：
      · tile=None          → 走 Day 92 的 LoopOrderPattern（Day 93 口径不变）
      · tile 设置且整除     → TilingPattern 消费（今天开张！）
      · tile 不整除        → 拒绝运行，点名 Day 95（尾部处理——绝静默生成越界 IR）
      · unroll ≠ 1         → 拒绝运行，点名 Day 96（Day 93 口径不变）
      · tile × 非默认 order → 拒绝运行，点名 Day 97（组合实验——绝不静默丢掉 order）
    """
    opts = lo.LoopOptions.parse(cfg) if isinstance(cfg, str) else cfg
    notes = []
    findings = opts.validate_for_shape(m, k, n)
    errors = [msg for lv, msg in findings if lv == "error"]
    if errors:
        raise lo.OptionsValidationError("第③道门（形状门）拒绝：" + "；".join(errors))
    warns = [msg for lv, msg in findings if lv == "warn"]
    notes += [f"形状检查（warn）：{msg}" for msg in warns]

    if opts.unroll != 1:
        raise lo.OptionsNotConsumedError(
            f"unroll={opts.unroll} 通过了校验（第①~②道门），"
            f"但展开 lowering 是 Day 96 的内容——今天拒绝运行，绝不静默忽略")
    if opts.tile is None:
        notes.append("tile 未设置：走 Day 92 的 LoopOrderPattern 路径（Day 93 口径不变）")
        run = od.run_order(opts.order, m, k, n, seed=seed)
        _, traffic, _ = od.measured_streams(run, m, k, n)
        return dict(opts=opts, run=run, traffic=traffic, notes=notes, tiled=False)
    if opts.order != ("i", "j", "k"):
        raise lo.OptionsNotConsumedError(
            f"tile={tname(opts.tile)} 已开张，但 tile × 非默认 order（{'-'.join(opts.order)}）"
            f"的组合实验是 Day 97 的内容——今天拒绝运行，绝不静默忽略")
    if warns:
        raise lo.OptionsNotConsumedError(
            f"tile={tname(opts.tile)} 通过了校验（第①~③道门，warn 级），但："
            + "；".join(warns)
            + "——今天只保证整除场景正确，拒绝运行（尾部处理是 Day 95 的内容）")
    if opts.tile == (1, 1, 1):
        notes.append("tile=1x1x1 是平凡块：K/Tk = K 个 k-块——合法但最笨（C 流量回到形态 B 水平）")

    run = run_tiled(opts.tile, m, k, n, seed=seed)
    notes.append(f"tile={tname(opts.tile)} 已消费（今天开张）："
                 f"{m // opts.tile[0]}×{n // opts.tile[1]}×{k // opts.tile[2]} 个块，"
                 f"Tiled IR {len(list(run['func'].walk()))} op")
    return dict(opts=opts, run=run, traffic=traffic_of(run), notes=notes, tiled=True)


# ============================================================
# TL1：结构不变量——Tiled IR 恒 31 op
# ============================================================

def tl1_structure(r_small, r_sim):
    print("\n—— TL1 结构不变量：Tiled IR 恒 31 op（形状与块尺寸都是数据） ——")
    seq = [op.name for op in r_small["func"].walk()]
    check("TL1a 贯穿例 tile=2x2x1：walk 序列逐项对照（31 op）", seq == list(TILED_BODY),
          f"实测 {len(seq)} op；积木：alloc/zero/常量×8/清零 nest×3/"
          "块循环×3/点循环×3/addi×3/乘加链")
    seq16 = [op.name for op in r_sim["func"].walk()]
    check("TL1b 16³ tile=4x4x4：同一份结构（walk 序列逐项相同）", seq16 == list(TILED_BODY),
          "换形状、换块尺寸，IR 结构不变——形状与块尺寸是常量值，不是代码结构")
    ts, ps = r_small["pat"].tile_specs, r_small["pat"].point_specs
    Tm, Tn, Tk = r_small["pat"].tile
    ok_spec = (ts[0].iv == "%i0" and ts[0].lb == 0 and ts[0].ub == M and ts[0].step == Tm
               and ts[1].step == Tn and ts[2].step == Tk
               and ps[0].iv == "%i" and ps[0].step == 1 and ps[0].ub == Tm
               and ps[1].ub == Tn and ps[2].ub == Tk
               and trip_count(ts[0]) == M // Tm and trip_count(ps[0]) == Tm)
    check("TL1c LoopSpec 四要素：块循环 step=块尺寸 trip=维/块；点循环 step=1 trip=块尺寸",
          ok_spec,
          f"i0: [0,{M}) step {Tm} trip {M // Tm}；i: [i0,i0+{Tm}) trip {Tm}"
          f"——点循环的 trip 恒等于块尺寸，这就是整除契约")
    vals = sorted(op.attrs["value"] for op in r_small["func"].walk()
                  if op.name == "arith.constant" and op.results[0].type == "index")
    check("TL1d index 常量多重集 = {0,1,M,N,K,Tm,Tn,Tk}",
          vals == sorted([0, 1, Tm, Tn, Tk, K, M, N]),
          f"实测 {vals}——三个块尺寸常量是今天的新面孔（Day 89 只有 5 个常量）")


# ============================================================
# TL2：语义不变性——位等价与访问全覆盖
# ============================================================

def tl2_semantics(r_small, runs_small, runs_sim, r_untiled):
    print("\n—— TL2 语义不变性：切块之后，结果一个比特都不变 ——")
    eq = bool(np.array_equal(r_small["C"], r_small["ref"]))
    check("TL2a 贯穿例 A(2,3)@B(3,2)，tile=2x2x1：与同序参考位等价", eq,
          "k0 块升序 ＋ 块内 k 升序 → 每个 C[i,j] 的乘加顺序与 Day 89 完全相同")
    allok = all(bool(np.array_equal(r["C"], r["ref"])) for r in runs_small.values())
    check("TL2b 小例全部 8 种整除 tile 位等价（1/2 × 1/2 × 1/3 的笛卡尔积）", allok,
          "；".join(f"{tname(t)}" for t in runs_small) + "——8 份 Tiled IR、1 个答案")
    allok16 = all(bool(np.array_equal(r["C"], r["ref"])) for r in runs_sim.values())
    check("TL2c 16³ 五种 tile（1/2/4/8/16 立方）全部位等价", allok16,
          "包括 1x1x1（最笨）与 16x16x16（单块退化为 Day 92 形态 B）——正确性与块尺寸无关")
    m, k, n = SIM_SHAPE
    tri = triples_of(r_small)
    grid = Counter((i, j, kk) for i in range(M) for j in range(N) for kk in range(K))
    check("TL2d (i,j,k) 三元组恰好全覆盖一次（从真实日志重建）", Counter(tri) == grid,
          f"重建 {len(tri)} 次乘法 == M·N·K = {M * N * K}——无重复、无遗漏")
    korder_ok = True
    for i in range(M):
        for j in range(N):
            ks = [kk for (ii, jj, kk) in tri if (ii, jj) == (i, j)]
            korder_ok &= (ks == list(range(K)))
    check("TL2e 每个 (i,j) 的 k 加法顺序 == 0..K-1（位等价的机械解释）", korder_ok,
          "块循环 k0 升序套点循环 k 升序 → 全局 k 仍升序——舍入顺序不变")
    check("TL2f 与 Day 92 untiled i-j-k 逐位相同（两条 lowering 链对齐）",
          bool(np.array_equal(r_small["C"], r_untiled["C"])),
          "Tiled IR 与 Day 89 的 18 op IR 殊途同归——这就是「语义不变」")


# ============================================================
# TL3：流量公式——tile 改变的是「什么时候」，不是「多少次」（A/B）
# ============================================================

def tl3_traffic(r_small, r_213, r_small_sim):
    print("\n—— TL3 流量公式：A/B 的 load 总数与 tile 无关；C 的 RMW 由 Tk 独家决定 ——")
    t = traffic_of(r_small)
    check("TL3a A/B 的 load 总数与 tile 无关（恒 2·M·N·K）",
          t["a_loads"] == M * N * K and t["b_loads"] == M * N * K,
          f"实测 A {t['a_loads']}、B {t['b_loads']}（tile=2x2x1）——"
          "切块改的是访问的『时机』（局部性），不是访问的『次数』")
    Tm, Tn, Tk = r_small["pat"].tile
    ok = (t["c_loads"] == M * N * (K // Tk) and t["c_stores"] == M * N * (K // Tk)
          and t["init_stores"] == M * N)
    check("TL3b C 流量公式：读=写=M·N·K/Tk，清零=M·N", ok,
          f"实测 {t['c_loads']}L+{t['c_stores']}S+{t['init_stores']}清 = 4·{K // Tk} RMW＋4 清零")
    t2 = traffic_of(r_213)
    check("TL3c Tk 换档实验：tile 2x2x1 → 2x2x3，C 流量 12L+12S → 4L+4S",
          t2["c_loads"] == 4 and t2["c_stores"] == 4,
          f"实测 {t2['c_loads']}L+{t2['c_stores']}S+{t2['init_stores']}清——只有 Tk 进公式："
          "k-块每少一个，C 的读-改-写就少一轮")
    t16 = traffic_of(r_small_sim)
    m, k, n = SIM_SHAPE
    Tm, Tn, Tk = r_small_sim["pat"].tile
    check("TL3d 16³ tile=4x4x4 流量对齐公式",
          t16["a_loads"] == m * n * k and t16["c_loads"] == m * n * (k // Tk)
          and t16["init_stores"] == m * n,
          f"实测 A {t16['a_loads']}，C {t16['c_loads']}L+{t16['c_stores']}S+{t16['init_stores']}清"
          f"（公式 M·N·K/Tk = {m}·{n}·{k // Tk}）")


# ============================================================
# TL4：整除测试（计划点名的交付物）
# ============================================================

def tl4_battery():
    print("\n—— TL4 整除测试：静态 Shape ＋ 整除场景全过（计划点名的交付物） ——")
    cases = []
    for tm in (1, 2):
        for tn in (1, 2):
            for tk in (1, 3):
                cases.append(((M, K, N), (tm, tn, tk)))
    for tile in ((1, 1, 1), (2, 2, 2), (4, 4, 4), (8, 8, 8), (16, 16, 16),
                 (2, 8, 4), (4, 2, 8), (8, 4, 2), (1, 16, 1), (16, 1, 16)):
        cases.append((SIM_SHAPE, tile))
    for shape, tile in (((4, 8, 6), (2, 3, 4)), ((4, 8, 6), (4, 2, 8)),
                        ((4, 8, 6), (1, 1, 1)), ((1, 5, 1), (1, 1, 5)),
                        ((1, 5, 1), (1, 1, 1)), ((3, 2, 7), (3, 1, 2)),
                        ((6, 4, 2), (3, 2, 4)), ((5, 10, 15), (5, 5, 5))):
        cases.append((shape, tile))
    rows, all_ok, all_eq = [], True, True
    for (m, k, n), tile in cases:
        r = run_tiled(tile, m, k, n)
        t = traffic_of(r)
        ops = len(list(r["func"].walk()))
        eq = bool(np.array_equal(r["C"], r["ref"]))
        oob = r["err"] is None
        uninit = len(r["interp"].stats["uninit_reads"]) if r["interp"] else -1
        ok = (ops == 31 and eq and oob and uninit == 0)
        all_ok &= ok
        all_eq &= eq
        rows.append(dict(shape=(m, k, n), tile=tile, ops=ops, eq=eq,
                         tiles=f"{m // tile[0]}×{n // tile[1]}×{k // tile[2]}",
                         cflow=f"{t['c_loads']}L+{t['c_stores']}S+{t['init_stores']}清",
                         ktiles=k // tile[2]))
    check("TL4a 小例 8 种整除 tile 全过（位等价＋零越界＋零未初始化读＋恒 31 op）",
          all(r["eq"] and r["ops"] == 31 for r in rows[:8]),
          "Tm∈{1,2}×Tn∈{1,2}×Tk∈{1,3} 的完整笛卡尔积")
    check("TL4b 16³ 十种 tile 全过（含 1x1x1 平凡块与 16x16x16 全块退化）",
          all(r["eq"] and r["ops"] == 31 for r in rows[8:18]),
          "结构恒定、语义恒定——块尺寸是数据；1x1x1 最笨、16x16x16 单块，都正确")
    check("TL4c 非方形与单维 8 组全过（4×8×6、1×5×1、3×2×7、6×4×2、5×10×15）",
          all(r["eq"] and r["ops"] == 31 for r in rows[18:]),
          "M、N、K 独立取值（Day 90 的边界精神）＋ 维度为 1 ＋ 非方形块（2x3x4）")
    check("TL4d 汇总：26/26 全部位等价、恒 31 op（表格落盘 outputs/divisible-tests.txt）",
          all_ok and all_eq and len(rows) == 26,
          "整除场景的正确性有机械口径：结构、数值、探针三张网一起收口")
    return rows


# ============================================================
# TL5：缓存收益实验——blocking 兑现 Day 92 的预言
# ============================================================

def tl5_cache():
    print("\n—— TL5 缓存收益：16³ 真实轨迹回放，untiled vs tiled（512B/1KB/4KB） ——")
    m, k, n = SIM_SHAPE
    runs = {}
    runs[("untiled", ("i", "j", "k"))] = od.run_order(("i", "j", "k"), m, k, n, seed=SEED)
    runs[("untiled", ("i", "k", "j"))] = od.run_order(("i", "k", "j"), m, k, n, seed=SEED)
    for tile in ((2, 2, 2), (4, 4, 4), (8, 8, 8)):
        runs[("tiled", tile)] = run_tiled(tile, m, k, n)
    sims = {key: {ln: od.cache_sim(r["interp"].access_log, m, k, n, lines=ln)
                  for ln in SIM_CACHES} for key, r in runs.items()}
    base_ijk = sims[("untiled", ("i", "j", "k"))]
    tiled444 = sims[("tiled", (4, 4, 4))]
    check("TL5a 512B（32 行）：tiled 4x4x4 缺失 < untiled i-j-k",
          tiled444[32]["misses"] < base_ijk[32]["misses"],
          f"实测 {tiled444[32]['misses']} vs {base_ijk[32]['misses']}"
          f"（Day 92 的痛点：i-j-k 在 512B 下 B 列扫描全缺失）")
    b_ijk = base_ijk[32]["per_mem"].get("%b", 0)
    b_444 = tiled444[32]["per_mem"].get("%b", 0)
    check("TL5b B 的缺失塌缩：tiled 4x4x4 的 B 缺失 ≤ i-j-k 的 1/8",
          b_444 <= b_ijk // 8,
          f"实测 B缺 {b_444} vs {b_ijk}——列面板 (k0..k0+3)×(j0..j0+3) 装得下缓存，"
          "B 每格被 4 次复用不再靠运气")
    ikj = sims[("untiled", ("i", "k", "j"))]
    check("TL5c 1KB（64 行）：tiled 4x4x4 仍优于两个 untiled 基线",
          tiled444[64]["misses"] < ikj[64]["misses"]
          and tiled444[64]["misses"] < base_ijk[64]["misses"],
          f"实测 tiled {tiled444[64]['misses']} vs untiled ijk {base_ijk[64]['misses']}"
          f" / ikj {ikj[64]['misses']}——Day 92 的 1KB 赢家（ikj）也被块循环超过")
    tot_t = tiled444[32]["total"]
    tot_u = base_ijk[32]["total"]
    ktiles = k // 4
    check("TL5d 诚实的代价列：总访问数上升（C 的跨块 RMW）",
          tot_t == tot_u + m * n * ktiles * 2,
          f"实测 {tot_u} → {tot_t}（+{(tot_t - tot_u) / tot_u:.0%}）——"
          "tiling 用多出来的 C 流量换少的缺失：账要两头记")
    return runs, sims


# ============================================================
# TL6：消费契约更新——tile 开张，其余照旧 fail-closed
# ============================================================

def tl6_guard():
    print("\n—— TL6 消费契约：tile 开张；不整除/组合/展开仍然 fail-closed ——")
    results = []

    def fate(desc, thunk):
        try:
            r = thunk()
            results.append((desc, "通过", r))
            return r
        except (lo.OptionsValidationError, lo.OptionsNotConsumedError) as e:
            results.append((desc, f"拒绝：{e}", None))
            return None

    r213 = fate("parse('tile=2x2x3')——Day 93 第④道门拒过的配置",
                lambda: run_with_config("tile=2x2x3"))
    ok213 = (r213 is not None and r213["tiled"]
             and bool(np.array_equal(r213["run"]["C"], r213["run"]["ref"])))
    check("TL6a Day 93 的报错原文今天兑现：tile=2x2x3 端到端跑通且位等价", ok213,
          "「Tiling 的 lowering 是 Day 94 的内容」——今天它来了（配置层一周的伏笔回收）")
    r222 = fate("parse('tile=2x2x2')——Tk=2 不整除 K=3",
                lambda: run_with_config("tile=2x2x2"))
    check("TL6b 不整除被拒（点名 Day 95）", r222 is None
          and "Day 95" in results[-1][1], "报错原文：" + results[-1][1][:80] + "…")
    r_un = fate("parse('unroll=2')", lambda: run_with_config("unroll=2"))
    check("TL6c unroll 仍被拒（点名 Day 96，Day 93 口径不变）", r_un is None
          and "Day 96" in results[-1][1], results[-1][1])
    r_mix = fate("parse('order=ikj,tile=2x2x3')——组合实验",
                 lambda: run_with_config("order=ikj,tile=2x2x3"))
    check("TL6d tile×非默认 order 组合被拒（点名 Day 97，绝不静默丢 order）", r_mix is None
          and "Day 97" in results[-1][1], results[-1][1])
    r_big = fate("parse('tile=4x4x4') on A(2,3)@B(3,2)", lambda: run_with_config("tile=4x4x4"))
    check("TL6e 块比维度大 → 第③道门 error（Day 93 的门原样把守）", r_big is None
          and "第③道门" in results[-1][1], results[-1][1])
    r_def = fate("parse('order=ikj')——默认路径回退", lambda: run_with_config("order=ikj"))
    ok_def = (r_def is not None and not r_def["tiled"]
              and len(list(r_def["run"]["func"].walk())) == 21)
    check("TL6f tile 未设置时走 Day 92 路径（order=ikj 21 op——回退兼容）", ok_def,
          "昨天的 25 项检查今天原样成立：开张新字段不改变旧路径的行为")
    r_tri = fate("parse('tile=1x1x1')——平凡块", lambda: run_with_config("tile=1x1x1"))
    check("TL6g 平凡块放行并附注（不是静默忽略）",
          r_tri is not None and any("平凡块" in nt for nt in r_tri["notes"]),
          "附注原文：" + next(nt for nt in r_tri["notes"] if "平凡块" in nt))
    return results


# ============================================================
# 产出文件
# ============================================================

def write_ir_outputs():
    r1 = run_tiled((2, 2, 1), M, K, N)
    r2 = run_tiled((2, 2, 3), M, K, N)
    L = ["Tiled IR（第 94 天交付物）——两份配置、两份 Tiled 循环、同一个答案", env_line(), "",
         "贯穿例：A(2,3) @ B(3,2) → C(2,2)，种子 94；两份 IR 都与参考位等价（TL2）",
         "结构：31 op = Day 89 的 18 op ＋ 清零 nest 3 ＋ 块循环上界与点循环骨架 10", ""]
    for tag, r in (("tile=2x2x1（K 切成 3 块——跨块累加看得见）", r1),
                   ("tile=2x2x3（Day 93 第④道门拒过的配置——单块，K/Tk=1）", r2)):
        L.append("=" * 78)
        L.append(tag)
        L.append("=" * 78)
        L += print_module(r["func"], [
            f"// 第 94 天：Tiled MatMul，{tag.split('（')[0]}",
            f"// 块循环 ×3（step=块尺寸）→ 点循环 ×3（lb=块起点，ub=addi(起点,块尺寸)）",
            f"// C 流量：{traffic_of(r)['c_loads']}L+{traffic_of(r)['c_stores']}S"
            f"+{traffic_of(r)['init_stores']}清；与参考位等价 = "
            f"{bool(np.array_equal(r['C'], r['ref']))}",
            env_line()]).rstrip().split("\n")
        L.append("")
    (OUT / "tiled-ir.txt").write_text("\n".join(L) + "\n", encoding="utf-8")


def write_tests_output(rows):
    L = ["整除测试汇总（第 94 天交付物）——所有配置真实运行", env_line(), "",
         "口径：恒 31 op（TL1）；位等价 = 与同序参考逐位相同；",
         "     零越界 = 解释器按维探针无 MemRefOOBError；零未初始化读 = Day 87 内存模型",
         "     C 流量 = M·N·K/Tk 读 + M·N·K/Tk 写 + M·N 清零（TL3 公式的实测值）", ""]
    L.append(f"{'形状 M×K×N':<12}{'tile':<10}{'块数 i×j×k':<12}{'k-块数':<7}"
             f"{'C 流量':<18}{'op':<5}{'位等价':<6}")
    for r in rows:
        m, k, n = r["shape"]
        L.append(f"{f'{m}x{k}x{n}':<12}{tname(r['tile']):<10}{r['tiles']:<12}"
                 f"{r['ktiles']:<7}{r['cflow']:<18}{r['ops']:<5}"
                 f"{'√' if r['eq'] else '×'}")
    L.append("")
    L.append("读表三问：")
    L.append("  ① op 列恒 31——形状与块尺寸是数据（常量值），不是代码结构；")
    L.append("  ② C 流量只随 k-块数（K/Tk）变——Tk 换档，跨块 RMW 轮数跟着除（TL3c）；")
    L.append("  ③ 1x1x1 与 16x16x16 是两个极端退化（全碎／整块），照样位等价——")
    L.append("     整除契约下正确性与块尺寸无关，性能才与块尺寸有关（TL5/Day 97）。")
    (OUT / "divisible-tests.txt").write_text("\n".join(L) + "\n", encoding="utf-8")


def write_cache_output(runs, sims):
    m, k, n = SIM_SHAPE
    L = ["缓存收益实验：blocking 兑现 Day 92 的预言（真实访存轨迹回放）", env_line(), "",
         f"形状 A({m},{k}) @ B({k},{n})；直接映射；行 16B；矩阵间隔 1 行（Day 92 口径）",
         "基线：untiled i-j-k（Day 92 的 512B 灾难户）与 i-k-j（Day 92 的 512B 赢家）",
         "tiled：块循环×3 + 点循环×3；配置 2x2x2 / 4x4x4 / 8x8x8", ""]
    L.append(f"{'配置':<20}{'总访问':<8}{'512B缺失':<10}{'1KB缺失':<9}{'4KB缺失':<9}"
             f"{'B缺@512B':<10}{'命中率@512B':<12}")
    for key in runs:
        if key[0] == "untiled":
            name = f"untiled {'-'.join(key[1])}"
        else:
            name = f"tiled {tname(key[1])}"
        s32, s64, s4k = sims[key][32], sims[key][64], sims[key][256]
        L.append(f"{name:<20}{s32['total']:<8}{s32['misses']:<10}{s64['misses']:<9}"
                 f"{s4k['misses']:<9}{s32['per_mem'].get('%b', 0):<10}"
                 f"{s32['hit_rate']:.1%}")
    L.append("")
    ijk = sims[("untiled", ("i", "j", "k"))]
    t444 = sims[("tiled", (4, 4, 4))]
    L.append("三个读数（数字全部来自真实回放）：")
    L.append(f"  ① B缺：untiled i-j-k {ijk[32]['per_mem'].get('%b', 0)} → "
             f"tiled 4x4x4 {t444[32]['per_mem'].get('%b', 0)}——"
             "列面板装进缓存，B 的复用从『靠外层轮回』变『块内四连』；")
    L.append(f"  ② 512B 总缺失：{ijk[32]['misses']} → {t444[32]['misses']}；"
             f"1KB：{ijk[64]['misses']} → {t444[64]['misses']}——两个容量档都占优；")
    L.append(f"  ③ 代价：总访问 {ijk[32]['total']} → {t444[32]['total']}"
             f"（+{(t444[32]['total'] - ijk[32]['total']) / ijk[32]['total']:.0%}，"
             "来自 C 的跨块 RMW）——多做的访问几乎全部命中，划算。")
    L.append("")
    L.append("注：直接映射、无预取、无写缓冲——数字只用于配置之间的对比（Day 92 口径）；")
    L.append("    最优块尺寸取决于『缓存容量 vs 每块工作集』——这是 Day 97 多配置实验的主菜。")
    (OUT / "cache-blocking.txt").write_text("\n".join(L) + "\n", encoding="utf-8")


def write_guard_output(results):
    L = ["消费契约实录（第 94 天版）——六份配置的真实命运", env_line(), "",
         "门序沿用 Day 93：③形状门在前、④消费门在后；今天第④道门对 tile 开张，",
         "其余路径（不整除 / unroll / 组合）仍然 fail-closed——绝不静默忽略。", ""]
    for desc, fate, r in results:
        mark = "✓" if fate == "通过" else "✗"
        L.append(f"{mark} {desc}")
        if fate == "通过":
            run, traffic = r["run"], r["traffic"]
            ops = len(list(run["func"].walk()))
            eq = bool(np.array_equal(run["C"], run["ref"]))
            L.append(f"    端到端：{ops} op；C 流量 "
                     f"{traffic['c_loads']}L+{traffic['c_stores']}S"
                     f"+{traffic['init_stores']}清；与参考位等价 = {eq}")
            for nt in r["notes"]:
                L.append(f"    附注：{nt}")
        else:
            L.append(f"    {fate}")
        L.append("")
    L.append("一周的闭环：Day 93 形状门写着『整除场景，Day 94 的首选测试点』——")
    L.append("今天 26 组整除测试全部通过（TL4），两个非整除路径全部被点名拒绝（TL6b/§6）。")
    (OUT / "consume-guard.txt").write_text("\n".join(L) + "\n", encoding="utf-8")


# ============================================================
# §6 的三个真实错误演示（交互模式）
# ============================================================

def demo_nondiv():
    print("错误演示 1：绕过配置层，直接给 TilingPattern 一个非整除的 tile=2x2x2")
    print(f"  A({M},{K})@B({K},{N})：tile_m=2|M ✓，tile_n=2|N ✓，tile_k=2 ∤ K=3 ✗")
    r = run_tiled((2, 2, 2), M, K, N)
    print(f"  转换阶段：照常成功（{len(list(r['func'].walk()))} op——IR 生成不讲武德）")
    print(f"  执行阶段：{r['err']}")
    print("  → 点循环上界 %ub_k = %k0 + 2 = 4 越过 K=3，k=3 那圈直接越界；")
    print("    没有探针的机器上这是读垃圾＋多算一次乘加——静默的错误结果。")
    print("  → 修复：不绕过配置层。第④道消费门对不整除 fail-closed（TL6b）。")


def demo_acczero():
    print("错误演示 2：跨块累加丢失——k 点循环的初值写成 %zero（acc_from_zero 旋钮）")
    r_bad = run_tiled((2, 2, 1), M, K, N, acc_from_zero=True)
    eq_bad = bool(np.array_equal(r_bad["C"], r_bad["ref"]))
    maxd = float(np.max(np.abs(r_bad["C"] - r_bad["ref"])))
    last_tile = (r_bad["A"][:, 2:3] * r_bad["B"][2:3, :]).astype(np.float32)  # 只有 k=2 进了和
    only_last = bool(np.array_equal(r_bad["C"], last_tile))
    print(f"  tile=2x2x1（3 个 k-块）：acc 初值 %cv → %zero 之后：")
    print(f"  与参考位等价 = {eq_bad}；max|C−ref| = {maxd:.3f}")
    print(f"  C 里只剩下最后一个 k-块（k=2）的贡献 = {only_last}"
          "——前两个块的和凭空消失")
    print("  → 修复：iter_args 初值接 %cv（读端），块末 store 回 C（写端）——接力棒不能从零开始")


def demo_noinit():
    print("错误演示 3：忘记清零 nest——Day 92 OT5 的教训在 Tiling 世界复验")
    r = run_tiled((2, 2, 1), M, K, N, init=False)
    uninit = r["interp"].stats["uninit_reads"]
    eq = bool(np.array_equal(r["C"], r["ref"]))
    print(f"  tile=2x2x1 且 init=False：未初始化读 {len(uninit)} 条"
          f"（第一个 k-块的 %cv 全部读到垃圾 777+7·addr）")
    print(f"  与参考位等价 = {eq}——垃圾进了跨块累加链")
    print("  → 修复：跨块累加 ＝ 内存累加，零起点要自己铺——init nest 必须在（Day 92 形态 B）")


# ============================================================
# 主流程
# ============================================================

def collect():
    """跑齐主角数据（贯穿例＋16³＋untiled 基线），供检查与图共用。"""
    r_small = run_tiled((2, 2, 1), M, K, N)
    runs_small = {(tm, tn, tk): run_tiled((tm, tn, tk), M, K, N)
                  for tm in (1, 2) for tn in (1, 2) for tk in (1, 3)}
    runs_sim = {tile: run_tiled(tile, *SIM_SHAPE) for tile in
                ((1, 1, 1), (2, 2, 2), (4, 4, 4), (8, 8, 8), (16, 16, 16))}
    r_untiled = od.run_order(("i", "j", "k"), M, K, N, seed=SEED)
    return r_small, runs_small, runs_sim, r_untiled


def run_all():
    print("第 94 天 · 实现基础 Tiling：块循环 × 点循环 × 跨块累加 × 整除契约")
    print(env_line())
    r_small, runs_small, runs_sim, r_untiled = collect()
    r_213 = run_tiled((2, 2, 3), M, K, N)
    tl1_structure(r_small, runs_sim[(4, 4, 4)])
    tl2_semantics(r_small, runs_small, runs_sim, r_untiled)
    tl3_traffic(r_small, r_213, runs_sim[(4, 4, 4)])
    rows = tl4_battery()
    runs_cache, sims = tl5_cache()
    guard = tl6_guard()
    write_ir_outputs()
    write_tests_output(rows)
    write_cache_output(runs_cache, sims)
    write_guard_output(guard)
    print()
    print(f"—— 检查测试 {PASS} PASS / {FAIL} FAIL ——")
    print("tiled-ir.txt / divisible-tests.txt / cache-blocking.txt / "
          "consume-guard.txt 已写入 outputs/")
    return FAIL == 0


def config_mode(cfg):
    """一份配置串的完整旅程：描述 → 四道门 → 端到端（或拒绝）。"""
    opts = lo.LoopOptions.parse(cfg) if cfg else lo.LoopOptions()
    print(opts.describe())
    print(f"形状感知校验（A({M},{K})@B({K},{N})，第③道门）：")
    for lv, msg in opts.validate_for_shape(M, K, N):
        print(f"  [{lv}] {msg}")
    print("消费门（第④道，Day 94 版）：tile 开张；不整除/unroll/组合仍 fail-closed")
    try:
        r = run_with_config(opts)
    except (lo.OptionsValidationError, lo.OptionsNotConsumedError) as e:
        print(f"✗ {type(e).__name__}：{e}")
        return 1
    run, traffic = r["run"], r["traffic"]
    if r["tiled"]:
        ops = len(list(run["func"].walk()))
        eq = bool(np.array_equal(run["C"], run["ref"]))
        print(f"✓ 端到端（A({M},{K})@B({K},{N})，种子 {SEED}）：{ops} op；"
              f"C 流量 {traffic['c_loads']}L+{traffic['c_stores']}S+{traffic['init_stores']}清；"
              f"与参考位等价 = {eq}")
    else:
        print(f"✓ 端到端（Day 92 路径）：{len(list(run['func'].walk()))} op；"
              f"C 流量 {traffic['c_loads']}L+{traffic['c_stores']}S")
    for nt in r["notes"]:
        print(f"  附注：{nt}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="第 94 天：实现基础 Tiling")
    ap.add_argument("--config", metavar="CFG", help="一份配置串的完整旅程（如 'tile=2x2x1'）")
    ap.add_argument("--demo", choices=["nondiv", "acczero", "noinit"],
                    help="复现三个真实错误（§6 的交互版）")
    args = ap.parse_args()
    if args.config is not None:
        sys.exit(config_mode(args.config))
    if args.demo == "nondiv":
        demo_nondiv()
    elif args.demo == "acczero":
        demo_acczero()
    elif args.demo == "noinit":
        demo_noinit()
    else:
        sys.exit(0 if run_all() else 1)


if __name__ == "__main__":
    main()
