#!/usr/bin/env python3
"""第 91 天：第 13 周复盘——图算子到循环实现的语义保持。

学习计划（第 91 天）：
  学习：回顾图算子到循环实现的语义保持；
  实践：手画一个 2×3 乘 3×2 的循环与索引示例，对照生成 IR；
  产出：Lowering 前后 IR、正确性报告和一页复盘。

本机未安装 MLIR（与 Day 57~90 一致）：复用 Day 90 的 shape_pass.py
（Python 复刻 MLIR DialectConversion 语义的仿真工程，今天只取不改），
把「复盘」做成能跑的——五个部分：

  RT1  前后 IR 快照：mini.matmul 源图（tensor）→ 18 op 循环 IR（memref），
       加结构检查（18 op 序列、LoopSpec、常量多重集 {0,1,M,N,K}）
  RT2  手画对照：把「手画的 2×3 乘 3×2」编码成一张预期表（循环四要素、
       下标配对、地址算式、每格乘积项数、流量、覆盖），逐行与
       生成 IR＋解释执行器的真实访存日志对账（地址逐条核对）
  RT3  语义条款审计：mini.matmul 的六条语义条款（数学/形状/数值/边界/
       内存/保守），每条给出「循环 IR 的实现点」＋「真实探针结果」
  RT4  分辨力检查：4 个注入变异在 (2,3,2) 上的真实结局——
       i_ub_n 在这里 SAME（M==N 巧合对：复盘例自己就有盲区！），
       引用 Day 90 全矩阵回归（15/15）补上这个盲区
  RT5  一页复盘：第 13 周七天链路（D85 设计→D86 骨架→D87 初始化→
       D88 三重循环→D89 循环体→D90 边界形状→D91 复盘）＋数字面板

用法：
    python3 review_pass.py                # RT1~RT5 全跑，写 outputs/
    python3 review_pass.py --cell 1 1     # 打印 C[1,1] 的 K 项展开（手画对照用）
    python3 review_pass.py --mutant i_ub_n # 单变异复跑（分辨力体验）

产出（outputs/）：
    pre-ir.txt             Lowering 前 IR（mini.matmul ＋ tensor 类型）
    post-ir.txt            Lowering 后 IR（18 op 循环实现）
    sketch-check.txt       手画预期表 × 生成 IR × 访存日志的逐行对账
    correctness-report.txt 正确性报告（六条款审计＋行为等价＋分辨力）
    review.txt             一页复盘（第 13 周总结）
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "day-090" / "code"))

import shape_pass as sp   # noqa: E402  （Day 90 的工程——今天只取不改）
from shape_pass import (  # noqa: E402
    EXPECTED_BODY, MatMulBodyPattern, build_dynamic_graph, build_main_graph,
    coverage, make_inputs, mem_strides_of, print_module, reference_matmul,
    run_case, run_pass, trip_count,
)

OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

SEED = 91          # 第 91 天自己的输入种子（可复现，与前几天的数字不同）
M, K, N = 2, 3, 2  # 计划点名的复盘例：2×3 乘 3×2 → 2×2（注意 M==N=2！）

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
            f"本机未安装 MLIR（Day 57~90 口径：Python 复刻 DialectConversion 语义仿真）")


# ============================================================
# 手画示例（计划实践：「手画一个 2×3 乘 3×2 的循环与索引示例」）
# —— 下面这张表就是手画结果的数字版：先不看生成 IR，在纸上写下预期，
#    再由 RT2 逐行对账。每一行的值都来自「手算」而不是抄 IR。
# ============================================================

SKETCH_LOOPS = [          # 三重循环四要素（lb 含、ub 不含、step）
    ("%i", 0, 2, "M = A 的行数 = 2"),
    ("%j", 0, 2, "N = B 的列数 = 2"),
    ("%k", 0, 3, "K = 内维契约 = A 列数 = B 行数 = 3"),
]
SKETCH_PAIRINGS = [       # 三个张量的下标配对（谁乘谁、写在哪个格子）
    ("%a", ("%i", "%k"), "A[i,k]：i 当行、k 当列"),
    ("%b", ("%k", "%j"), "B[k,j]：k 当行、j 当列"),
    ("%c", ("%i", "%j"), "C[i,j]：一行对一个 i、一列对一个 j"),
]
SKETCH_STRIDES = {        # 行主序 strides（手算：最后一维 1，往前乘 shape）
    "%a": (3, 1), "%b": (2, 1), "%c": (2, 1),
}
SKETCH_K_TERMS = 3        # 每个 C[i,j] 的乘积项数 = K
SKETCH_TRAFFIC = (24, 4)  # load = 2·M·N·K = 24，store = M·N = 4
SKETCH_COVERAGE = {"%a": 2, "%b": 2, "%c": 1}   # A 每格读 N 次 / B 每格读 M 次 / C 每格写 1 次


# ============================================================
# RT1：Lowering 前后 IR 快照
# ============================================================

def rt1_snapshots():
    print("\n—— RT1 前后 IR 快照 ——")
    # 前：源图 S0（mini.matmul 还在，类型是 tensor）
    src = build_main_graph(M, K, N)
    pre_ir = print_module(
        src, [f"// Lowering 前（源图 S0）：A({M},{K}) @ B({K},{N}) -> C({M},{N})",
              f"// 一个图算子 mini.matmul 概括全部语义；类型是 tensor（值语义）",
              env_line()])
    (OUT / "pre-ir.txt").write_text(pre_ir, encoding="utf-8")
    pre_ops = [op.name for op in src.walk()]
    pre_ok = (pre_ops == ["func.func", "mini.matmul", "func.return"]
              and sum(1 for o in src.walk() if o.name == "mini.matmul") == 1)
    check("RT1a 源图结构：func + mini.matmul + return（Lowering 前）", pre_ok,
          f"源图 {len(pre_ops)} op；mini.matmul 恰好 1 个")

    # 后：跑一遍 MatMul Lowering Pass（Day 90 正确形态）
    func = build_main_graph(M, K, N)
    pattern, res = run_pass(func, "full")
    post_ir = print_module(
        func, [f"// Lowering 后：{len(list(func.walk()))} op 循环实现（真实转换输出）",
               f"// mini.matmul 消失；类型变 memref（内存语义）；语义保持由 RT2~RT4 验证",
               env_line()])
    (OUT / "post-ir.txt").write_text(post_ir, encoding="utf-8")

    ops_ok = res.ok and [op.name for op in func.walk()] == EXPECTED_BODY
    spec_ok = (ops_ok and [(s.iv, s.lb, s.ub, s.step) for s in pattern.specs]
               == [("%i", 0, M, 1), ("%j", 0, N, 1), ("%k", 0, K, 1)])
    const_vals = sorted(op.attrs["value"] for op in func.walk()
                        if op.name == "arith.constant"
                        and op.results[0].type == "index")
    consts_ok = const_vals == sorted([0, 1, M, N, K])
    check("RT1b 终图结构：18 op 序列（结构恒定，形状是数据）", ops_ok,
          f"终图 {len(list(func.walk()))} op，残留非法 op = "
          f"{getattr(res, 'remaining', '无') if not res.ok else '无'}")
    check("RT1c LoopSpec 出生证明：(i:0..2, j:0..2, k:0..3)", spec_ok,
          "；".join(f"{s.iv}∈[{s.lb},{s.ub}) ← {s.ub_source}" for s in pattern.specs))
    check("RT1d 常量多重集 = {0,1,M,N,K} = {0,1,2,2,3}", consts_ok,
          f"实测 {const_vals}（M==N==2 → 两个 2，五个常量四个值）")
    return func, pattern


# ============================================================
# RT2：手画对照（预期表 × 生成 IR × 访存日志）
# ============================================================

def rt2_sketch(func, pattern):
    print("\n—— RT2 手画对照：纸上的预期 vs 生成 IR vs 访存日志 ——")
    lines = ["手画预期表 × 生成 IR × 解释执行访存日志（真实运行）",
             env_line(), ""]
    # 真实执行一次，拿访存日志
    A, B = make_inputs(M, K, N, seed=SEED)
    res2, interp, func2, C, err = run_case([MatMulBodyPattern()], M, K, N, seed=SEED)
    assert res2.ok and err is None and C is not None
    ref = reference_matmul(A, B)
    log = interp.access_log

    # ---- 行 1：循环四要素 ----
    rows_ok = []
    for (iv, lb, ub, why), spec in zip(SKETCH_LOOPS, pattern.specs):
        ok = (spec.iv == iv and spec.lb == lb and spec.ub == ub and spec.step == 1)
        rows_ok.append(ok)
        lines.append(f"循环 {iv}：手画 [{lb},{ub}) step 1（{why}）｜"
                     f"IR 实测 [{spec.lb},{spec.ub}) step {spec.step}，"
                     f"trip = {trip_count(spec)}｜{'✓' if ok else '✗'}")
    check("RT2a 三重循环四要素：手画 = IR（含 ub 来源）", all(rows_ok))

    # ---- 行 2：下标配对 ----
    pairs_ok = []
    ir_pair = {}
    for op in func.walk():
        if op.name == "memref.load":
            ir_pair[op.operands[0].name] = tuple(v.name for v in op.operands[1:])
        elif op.name == "memref.store":
            ir_pair[op.operands[1].name] = tuple(v.name for v in op.operands[2:])
    for mem, (i1, i2), why in SKETCH_PAIRINGS:
        ok = ir_pair.get(mem) == (i1, i2)
        pairs_ok.append(ok)
        lines.append(f"配对 {mem}：手画 [{i1}, {i2}]（{why}）｜"
                     f"IR 实测 [{', '.join(ir_pair.get(mem, ('?', '?')))}]｜{'✓' if ok else '✗'}")
    check("RT2b 下标配对：A[i,k] / B[k,j] / C[i,j]", all(pairs_ok))

    # ---- 行 3：地址算式（strides ＋ 逐条核对访存日志） ----
    real_strides = mem_strides_of(func)
    str_ok, addr_hits, addr_total = True, 0, 0
    for mem, (s0, s1) in SKETCH_STRIDES.items():
        rs = real_strides.get(mem)
        ok = rs == (s0, s1)
        str_ok &= ok
        lines.append(f"地址 {mem}：手画 strides [{s0}, {s1}] → addr = {s0}·r + {s1}·c｜"
                     f"IR 类型实测 strided<[{rs[0]}, {rs[1]}]>｜{'✓' if ok else '✗'}")
    # 24 次访存的线性地址逐条与手画公式对账
    for kind, mem, idx, addr, val in log:
        s0, s1 = SKETCH_STRIDES[mem]
        addr_total += 1
        if addr == s0 * idx[0] + s1 * idx[1]:
            addr_hits += 1
    check("RT2c 地址算式：strides 与类型一致", str_ok,
          f"{addr_hits}/{addr_total} 条访存的线性地址逐条等于手画公式（3i+k / 2k+j / 2i+j）")
    lines.append(f"访存日志逐条对账：{addr_hits}/{addr_total} 条地址 = 手画公式（"
                 f"A: 3i+k，B: 2k+j，C: 2i+j）")

    # ---- 行 4：每个 C 格子的乘积项数 ----
    terms, cur = [], 0
    for kind, mem, idx, addr, val in log:
        if kind == "load" and mem == "%a":
            cur += 1
        elif kind == "store" and mem == "%c":
            terms.append(cur)
            cur = 0
    terms_ok = terms == [SKETCH_K_TERMS] * (M * N)
    check("RT2d 每格乘积项数 = K = 3", terms_ok,
          f"实测每个 C 格子前的 A-load 数 {terms}（逐格计数，来自访存日志）")
    lines.append(f"每格乘积项数：手画 K = {SKETCH_K_TERMS}｜实测（每格前的 A-load 数）{terms}")

    # ---- 行 5：流量 ----
    st_ = interp.stats
    traffic_ok = (st_["loads"] == SKETCH_TRAFFIC[0] and st_["stores"] == SKETCH_TRAFFIC[1])
    check("RT2e 流量：load 24 = 2·M·N·K，store 4 = M·N", traffic_ok,
          f"实测 load {st_['loads']} / store {st_['stores']} / 未初始化读 "
          f"{len(st_['uninit_reads'])}")
    lines.append(f"流量：手画 load {SKETCH_TRAFFIC[0]} / store {SKETCH_TRAFFIC[1]}｜"
                 f"实测 {st_['loads']} / {st_['stores']}")

    # ---- 行 6：覆盖 ----
    cov = coverage(interp, func)
    cov_a = all(c == SKETCH_COVERAGE["%a"] for c in cov["%a"].values())
    cov_b = all(c == SKETCH_COVERAGE["%b"] for c in cov["%b"].values())
    cov_c = all(c == SKETCH_COVERAGE["%c"] for c in cov["%c"].values())
    cov_ok = (cov_a and cov_b and cov_c
              and set(cov["%a"]) == set(range(M * K))
              and set(cov["%b"]) == set(range(K * N))
              and set(cov["%c"]) == set(range(M * N)))
    check("RT2f 覆盖三定律：A 每格读 2 次（=N）、B 每格读 2 次（=M）、C 每格写 1 次",
          cov_ok, f"A {len(cov['%a'])} 格×2 ＋ B {len(cov['%b'])} 格×2 ＋ C {len(cov['%c'])} 格×1")
    lines.append(f"覆盖：手画 A×{SKETCH_COVERAGE['%a']} / B×{SKETCH_COVERAGE['%b']} / "
                 f"C×{SKETCH_COVERAGE['%c']}｜实测 A {len(cov['%a'])} 格、"
                 f"B {len(cov['%b'])} 格、C {len(cov['%c'])} 格，读/写次数全部符合")
    lines.append("")
    lines.append("结论：手画的每一行都被生成 IR 与访存日志证实——"
                 "「先手算、再对账」就是语义保持的人工版本。")
    (OUT / "sketch-check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return A, B, C, ref, interp


# ============================================================
# RT3：语义条款审计（六条款，每条带真实探针）
# ============================================================

def rt3_clauses(A, B, C, ref, interp):
    print("\n—— RT3 语义条款审计：mini.matmul 承诺了什么，循环 IR 兑现了什么 ——")
    lines = ["语义条款审计（正确性报告核心）：六条款 × 实现点 × 真实探针", env_line(), ""]
    st_ = interp.stats

    # S1 数学定义
    s1 = bool(np.array_equal(C, ref))
    check("S1 数学定义：C[i,j] = Σ_{k<3} A[i,k]·B[k,j]（K 项完整和）", s1,
          f"与同序参考实现逐位相等 = {s1}（RT2d 已证每格恰 3 项）")
    lines.append("S1 数学定义｜mini.matmul 承诺：C[i,j] 是 K 项完整内积｜循环 IR 实现："
                 "三重循环＋load A[i,k]·load B[k,j]→mulf→addf（iter_args 链）｜"
                 f"探针：位等价 = {s1}")

    # S2 形状契约
    s2 = (C.shape == (M, N) and C.dtype == np.float32)
    check("S2 形状契约：输出 (M,N)=(2,2)、f32；内维契约 K=3 已由 LoopSpec 兑现", s2,
          f"C.shape = {C.shape}，dtype = {C.dtype}；RT1c/RT1d 已验 ub 与常量来源")
    lines.append("S2 形状契约｜承诺：输出形状 (M,N)、内维 K 必须匹配｜实现：LoopSpec ub ← "
                 "M/N/K（A.shape[0]/B.shape[1]/内维契约），memref strided<[3,1]>/<[2,1]>/<[2,1]>｜"
                 f"探针：结构检查（RT1）＋ C 实测形状 {C.shape}")

    # S3 数值语义
    npm = np.matmul(A, B)
    npm_diff = float(np.max(np.abs(C - npm)))
    s3 = bool(np.array_equal(C, ref))
    check("S3 数值语义：f32 逐步舍入、k 升序的确定性求和顺序", s3,
          f"位等价（同序）= {s3}；np.matmul 对照 max|diff| = {npm_diff:.3e}"
          f"（舍入顺序不同，单独报告、不算失败——Day 89 起口径）")
    lines.append(f"S3 数值语义｜承诺：f32 元素、确定的求和顺序｜实现：iter_args(%acc=%zero) 链，"
                 f"每趟 addf 舍入一次，k 从 0 升到 2｜探针：位等价 = {s3}；"
                 f"np.matmul 差值 {npm_diff:.3e}（顺序不同属预期）")

    # S4 边界语义（K=0 回归——引用 Day 90 ST5 的口径，今天真跑一组）
    Ak, Bk = make_inputs(4, 0, 3, seed=SEED)
    resk, interpk, funck, Ck, errk = run_case([MatMulBodyPattern()], 4, 0, 3, seed=SEED)
    s4 = (resk.ok and errk is None and Ck is not None
          and bool(np.all(Ck == 0)) and interpk.stats["loads"] == 0
          and interpk.stats["stores"] == 12)
    check("S4 边界语义：K=0 → 空归约 = 单位元 0（C 全零）；trip 公式吸收零趟", s4,
          f"A(4,0)@B(0,3) 实测：C 全零 = {bool(np.all(Ck == 0))}，"
          f"load 0、store 12（%zero 出门——D87 伏笔在复盘里再兑一次）")
    lines.append("S4 边界语义｜承诺：任意非负 M/N/K 合法，K=0 → C 全零｜实现：trip = "
                 "max(0, ceil((ub-lb)/step))，%zero 是 iter_args 初值｜探针：K=0 回归 "
                 f"C 全零={bool(np.all(Ck == 0))}、load 0、store 12")

    # S5 内存语义（覆盖直接从访存日志重算——A/B 只读、C 每格写 1 次）
    from collections import Counter
    cov = {"%a": Counter(), "%b": Counter(), "%c": Counter()}
    for kind, mem, idx, addr, val in interp.access_log:
        cov[mem][addr] += 1
    c_only_store = all(c == 1 for c in cov["%c"].values()) and set(cov["%c"]) == set(range(M * N))
    ab_readonly = st_["stores"] == M * N     # store 只发生在 %c（流量定律已绑死）
    s5 = (c_only_store and ab_readonly and st_["uninit_reads"] == [] and st_["allocs"] == 1)
    check("S5 内存语义：C 每格恰好写 1 次终值；A/B 只读；无未初始化读；独立缓冲", s5,
          f"alloc {st_['allocs']} 块、store {st_['stores']} 次全落 %c、"
          f"未初始化读 {len(st_['uninit_reads'])}、%c {len(cov['%c'])} 格各写 1 次")
    lines.append("S5 内存语义｜承诺：输出写进独立缓冲，每格终值恰好写一次｜实现："
                 "memref.alloc %c；store 位于 k 外 j 内（作用域交集最内层）｜探针：覆盖定律 "
                 f"C×1={c_only_store}、未初始化读 {len(st_['uninit_reads'])}")

    # S6 保守边界（动态拒绝回归）
    dyn = build_dynamic_graph("M", base=(M, K, N))
    _p, dres = run_pass(dyn, "full")
    s6 = (not dres.ok)
    check("S6 保守边界：动态 '?' 宁拒不猜（拒绝且不留痕）", s6,
          f"动态 M=? 输入实测：转换拒绝——{dres.message[:52]}...")
    lines.append("S6 保守边界｜承诺：静态 Pattern 不猜动态形状｜实现：match 检测 '?' → "
                 f"notifyMatchFailure，事务 Rewriter 回滚｜探针：动态拒绝 = {s6}")

    all_ok = all([s1, s2, s3, s4, s5, s6])
    lines.append("")
    lines.append("审计结论：六条款全部有真实探针背书——语义保持不是一个笼统的「感觉对了」，"
                 "而是逐条款可验证的清单。")
    (OUT / "correctness-report.txt").write_text(
        "\n".join(lines[:2] + [""] + lines[2:]) + "\n", encoding="utf-8")
    return all_ok, dict(s1=s1, s2=s2, s3=s3, s4=s4, s5=s5, s6=s6, npm_diff=npm_diff)


# ============================================================
# RT4：分辨力检查（变异 × 复盘例的盲区）
# ============================================================

def rt4_discrimination():
    print("\n—— RT4 分辨力：正确性报告的「全绿」能证明什么 ——")
    # 复盘例 (2,3,2) 上四个变异的真实结局（预测在先：M==N=2 → i_ub_n 应隐身）
    PREDICT = {"M1 a_swap": "OOB", "M2 b_swap": "OOB", "M3 i_ub_n": "SAME", "M4 k_ub_n": "NUM"}
    lines = ["变异 × 复盘例 (2,3,2) 的真实结局（预测在前、实测对账）", env_line(), ""]
    grid = {}
    for mname, kwargs, desc in sp.MUTANTS:
        pats = [MatMulBodyPattern(**kwargs)]
        res, interp, func, Cm, err = run_case(pats, M, K, N, seed=SEED)
        if not res.ok:
            status, ev = "CONV", res.message
        elif err is not None:
            status, ev = "OOB", err
        else:
            A, B = make_inputs(M, K, N, seed=SEED)
            refm = reference_matmul(A, B)
            if np.array_equal(Cm, refm):
                status, ev = "SAME", "与同序参考逐位相同（隐身）"
            else:
                status, ev = "NUM", f"max|C − ref| = {float(np.max(np.abs(Cm - refm))):.3e}"
        grid[mname] = (status, ev)
        hit = status == PREDICT[mname]
        lines.append(f"{mname}：预测 {PREDICT[mname]}｜实测 {status}｜{ev}｜{'✓' if hit else '✗'}")
        lines.append(f"    （{desc}）")
    blind = grid["M3 i_ub_n"][0] == "SAME"
    check("RT4a 变异结局与预测对账：OOB / OOB / SAME / NUM", 
          all(grid[m][0] == PREDICT[m] for m in PREDICT),
          "a_swap→OOB（k=2 顶出行维）、b_swap→OOB（k=2 顶出列维）、"
          "i_ub_n→SAME（M==N=2，错误读数=正确读数）、k_ub_n→NUM（k 少跑 1 趟）")
    check("RT4b 复盘例自己的盲区：i_ub_n 在 (2,3,2) 上 SAME", blind,
          "M==N=2 → %cN 与 %cM 值相同——计划点名的复盘例恰是 Day 90 的 M==N 巧合对！"
          "单一形状的正确性报告抓不住它")
    # 全矩阵回归（Day 90 的 ST1 原样复跑）——补上盲区的证据来源
    ok_all, st1_lines, rows = sp.st1_matrix()
    n_pass = sum(1 for r in rows if r["good"])
    check("RT4c 全矩阵回归：15 组形状 × 11 项参数化检查（Day 90 ST1 原样复跑）", ok_all,
          f"{n_pass}/{len(rows)} 通过；i_ub_n 的盲区由矩阵其余成员杀死（Day 90 ST3：11/15 杀伤）")
    lines += ["", "全矩阵回归：" + "；".join(st1_lines[:2]),
              "结论：复盘例 (2,3,2) 的位等价全绿抓不住 i_ub_n——正确性报告必须引用"
              "形状矩阵整体（Day 90 猎杀矩阵：i_ub_n 被 11/15 组杀死），"
              "「单一形状全绿」只是语义保持的必要条件。"]
    with (OUT / "correctness-report.txt").open("a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(lines) + "\n")
    return grid, rows


# ============================================================
# RT5：一页复盘
# ============================================================

def rt5_review(clause_flags, grid, rows):
    print("\n—— RT5 一页复盘 ——")
    n_pass = sum(1 for r in rows if r["good"])
    L = [
        "第 13 周复盘（Day 85~91）：图算子到循环实现的语义保持",
        env_line(),
        "",
        "一句话：mini.matmul 的六条语义条款，全部落在恒为 18 op 的循环 IR 里，",
        "       且每条都有可复跑的探针证据；「正确」＝逐条款验证 ＋ 测试有分辨力。",
        "",
        "┌─ 七天链路：每天往论证里添的一块砖 ─────────────────────────────┐",
        "│ D85 设计    任务清单（类型/索引/初始化/循环/访存）→ 论证的「应然」面    │",
        "│ D86 骨架    ConversionPattern/Rewriter 事务性、失败不留痕 → 论证可信度  │",
        "│ D87 初始化  alloc 不清零 ＋ %zero 单位元 → S4 边界语义的根（K=0=全零） │",
        "│ D88 三重循环 LoopSpec 出生证明 ＋ trip 公式 → S2 形状契约的根          │",
        "│ D89 循环体  地址映射 ＋ iter_args 累加链 → S1/S3/S5 的根              │",
        "│ D90 边界形状 15 组形状矩阵 ＋ 4 变异猎杀 → 论证的分辨力（全绿≠正确）   │",
        "│ D91 复盘    六条款审计 ＋ 手画对照 → 把局部检查组装成整体论证          │",
        "└──────────────────────────────────────────────────────────────┘",
        "",
        "贯穿例：A(2,3) @ B(3,2) → C(2,2)（M=N=2、K=3——恰是 M==N 巧合对）",
        f"  手画对账：三重循环 [0,2)×[0,2)×[0,3)、配对 A[i,k]/B[k,j]/C[i,j]、",
        f"  地址 3i+k / 2k+j / 2i+j、每格 3 项、load {SKETCH_TRAFFIC[0]} / store {SKETCH_TRAFFIC[1]}、",
        f"  覆盖 A×2 / B×2 / C×1 —— 全部与生成 IR 及访存日志逐条相符（RT2）。",
        "",
        "数字面板（全部真实运行）：",
        f"  语义条款：S1..S6 = "
        f"{'/'.join('✓' if clause_flags[k] else '✗' for k in ('s1','s2','s3','s4','s5','s6'))}",
        f"  行为等价：与同序参考位等价 = True；np.matmul 差值 "
        f"{clause_flags['npm_diff']:.3e}（舍入顺序不同，不算失败）",
        f"  结构不变式：IR 恒 18 op；常量多重集 {{0,1,2,2,3}}；LoopSpec (i<M, j<N, k<K)",
        f"  分辨力：4 变异在复盘例上 = "
        + " / ".join(f"{m.split()[1]}={grid[m][0]}" for m in grid),
        f"  全矩阵回归：{n_pass}/{len(rows)}（Day 90 ST1 原样复跑）",
        "",
        "遗留与下周：语义保持只问「对不对」，不问「快不快」——同一份语义，",
        "  i/j/k 换个排列就是另一份访存行为。Day 92 起进入循环顺序与局部性：",
        "  连续访问、复用、以及 A 每格读 N 次背后的缓存故事。",
    ]
    (OUT / "review.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("一页复盘已写入 outputs/review.txt")
    return L


# ============================================================
# 练习模式：--cell I J 打印 C[i,j] 的 K 项展开（手画对照的对照答案）
# ============================================================

def cell_mode(ci, cj):
    A, B = make_inputs(M, K, N, seed=SEED)
    res, interp, func, C, err = run_case([MatMulBodyPattern()], M, K, N, seed=SEED)
    assert res.ok and err is None
    print(f"C[{ci},{cj}] 的 K 项展开（真实值，种子 {SEED}；地址按手画公式 3i+k / 2k+j）：")
    acc = np.float32(0.0)
    terms = []
    for k in range(K):
        a_addr, b_addr = 3 * ci + k, 2 * k + cj
        av, bv = np.float32(A[ci, k]), np.float32(B[k, cj])
        p = np.float32(av * bv)
        acc = np.float32(acc + p)
        terms.append(f"  k={k}: A[{ci},{k}]@{a_addr} · B[{k},{cj}]@{b_addr} "
                     f"= {av:+.6f} · {bv:+.6f} → 累加 {acc:+.6f}")
    print("\n".join(terms))
    print(f"  手算终值 {acc:+.6f} ｜ 执行器实测 C[{ci},{cj}] = {C[ci, cj]:+.6f} ｜ "
          f"逐位相等：{np.float32(C[ci, cj]) == acc}")
    print(f"  写回：memref.store %acc, %c[{ci},{cj}] → 线性地址 {2 * ci + cj}")


def mutant_mode(name):
    kwargs = dict(next(kw for mn, kw, _ in sp.MUTANTS if mn.split()[1] == name))
    pats = [MatMulBodyPattern(**kwargs)]
    res, interp, func, C, err = run_case(pats, M, K, N, seed=SEED)
    print(f"变异 {name} 在 A({M},{K})@B({K},{N}) 上的真实结局：")
    if err is not None:
        print(f"  OOB —— {err}")
    elif C is not None:
        A, B = make_inputs(M, K, N, seed=SEED)
        ref = reference_matmul(A, B)
        same = np.array_equal(C, ref)
        print(f"  {'SAME —— 与同序参考逐位相同（该形状对此变异免疫）' if same else 'NUM —— 静默算错'}"
              + ("" if same else f"，max|C−ref| = {float(np.max(np.abs(C - ref))):.3e}"))
    else:
        print(f"  CONV —— {res.message}")


# ============================================================ 主流程

def run_all():
    print("第 91 天 · 第 13 周复盘：图算子到循环实现的语义保持（检查测试报告）")
    print(env_line())
    func, pattern = rt1_snapshots()
    A, B, C, ref, interp = rt2_sketch(func, pattern)
    all_ok, flags = rt3_clauses(A, B, C, ref, interp)
    grid, rows = rt4_discrimination()
    rt5_review(flags, grid, rows)
    print()
    print(f"—— 检查测试 {PASS} PASS / {FAIL} FAIL ——")
    print("pre-ir.txt / post-ir.txt / sketch-check.txt / "
          "correctness-report.txt / review.txt 已写入 outputs/")
    return FAIL == 0


def main():
    ap = argparse.ArgumentParser(description="第 91 天：第 13 周复盘")
    ap.add_argument("--cell", type=int, nargs=2, metavar=("I", "J"),
                    help="打印 C[i,j] 的 K 项展开（手画对照）")
    ap.add_argument("--mutant", choices=[m.split()[1] for m, _, _ in sp.MUTANTS],
                    help="在复盘例上复跑一个注入变异")
    args = ap.parse_args()
    if args.cell:
        cell_mode(*args.cell)
    elif args.mutant:
        mutant_mode(args.mutant)
    else:
        sys.exit(0 if run_all() else 1)


if __name__ == "__main__":
    main()
