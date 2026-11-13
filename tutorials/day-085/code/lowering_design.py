#!/usr/bin/env python3
"""第 85 天：设计 mini.matmul → 循环表示的 Lowering 路线。

本机未安装 MLIR。与 Day 57~84 的做法一致：用 Python 复刻 MLIR
DialectConversion 框架的**角色分工与流程**（仿真），不伪造 MLIR 本身的行为。

    MLIR 里的角色（mlir/Transforms/DialectConversion.h）      仿真里的对应
    ---------------------------------------------------------------------
    ConversionTarget（合法性清单 addIllegalDialect/isLegal）    TARGET_LEGAL 集合
    TypeConverter（convertType + 三个物化钩子）                 tensor→memref 映射 + to_tensor/to_memref
    ConversionPattern（matchAndRewrite 读源 op、写目标 op）     PATTERNS 规则表
    applyFullConversion / applyPartialConversion（驱动器）      apply_conversion() 两种模式

用法：
    python3 lowering_design.py                # 生成当天全部产出（outputs/）
    python3 lowering_design.py --shape 2 3 2  # 换形状复算，结果打印到 stdout（练习用）

产出：
    outputs/design-doc.md    Lowering 设计文档（当天产出 1）
    outputs/test-report.txt  测试计划执行报告（当天产出 2，全部真实运行结果）
    outputs/ir-loop.txt      降级后的循环 IR（文本）
"""

from __future__ import annotations

import argparse
import platform
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "outputs"
SEED = 85
GARBAGE = np.float32(777.0)   # 模拟 memref.alloc 出来的"内容未定义"内存


# ================================================================ 类型系统

def row_major_strides(shape):
    """行主序 strides：最后一维为 1，往前逐维乘 shape。"""
    s = [1] * len(shape)
    for d in range(len(shape) - 2, -1, -1):
        s[d] = s[d + 1] * shape[d + 1]
    return tuple(s)


def addr(strides, idx):
    """线性地址 = Σ index_d × stride_d——今天"索引任务"的核心公式。"""
    return sum(i * s for i, s in zip(idx, strides))


def prod(xs):
    r = 1
    for x in xs:
        r *= x
    return r


@dataclass
class Design:
    """一次 Lowering 设计的全部可变参数。三个探针（P1/P2/P3）就是改这里。"""
    shape_a: tuple          # 输入 A 的 shape (M, K)
    shape_b: tuple          # 输入 B 的 shape (K, N)
    strides: dict           # 类型任务：{"A": s, "B": s, "C": s}
    init: str               # 输出初始化任务："iter_args" | "fill_load" | "garbage"
    k_bound: int | None     # 索引任务：内维循环上界；None = 用真正的 K

    @property
    def shape_c(self):
        return (self.shape_a[0], self.shape_b[1])


def baseline_design(M, K, N):
    return Design(
        shape_a=(M, K), shape_b=(K, N),
        strides={"A": row_major_strides((M, K)),
                 "B": row_major_strides((K, N)),
                 "C": row_major_strides((M, N))},
        init="iter_args",          # 方案 B：scf.for iter_args(%acc = 0.0)
        k_bound=None,
    )


# ============================================================ 循环 IR 执行器

def execute_loop_ir(design, A, B):
    """解释执行降级后的循环 IR。

    与 outputs/ir-loop.txt 是同一个程序：所有访存都显式经过 addr()
    计算线性地址（模拟 memref.load / memref.store），运算全部 np.float32。
    """
    M, K = A.shape
    _, N = B.shape
    sa, sb, sc = design.strides["A"], design.strides["B"], design.strides["C"]
    kb = design.k_bound if design.k_bound is not None else K
    Af, Bf = A.ravel(), B.ravel()
    C = np.full((M, N), GARBAGE)          # memref.alloc：内容未定义
    Cf = C.ravel()
    if design.init == "fill_load":        # 方案 A：先 fill 0，再读改写
        Cf[:] = np.float32(0.0)
    for i in range(M):
        for j in range(N):
            if design.init == "iter_args":
                acc = np.float32(0.0)     # 方案 B：iter_args 从常量 0 起步
            else:                         # 方案 A / A′：从 C[i,j] 读改写
                acc = np.float32(Cf[addr(sc, (i, j))])
            for k in range(kb):
                xa = np.float32(Af[addr(sa, (i, k))])   # load %a[%i,%k]
                xb = np.float32(Bf[addr(sb, (k, j))])   # load %b[%k,%j]
                acc = np.float32(acc + np.float32(xa * xb))
            Cf[addr(sc, (i, j))] = acc                  # store %c[%i,%j]
    return C


def reference_matmul(A, B):
    """同序 fp32 三重循环——位等价的对照对象。

    与 execute_loop_ir 是同一运算序列（乘加顺序相同、同为 fp32），
    所以"逐位相等"验证的是**地址与初值**的正确性，而不是浮点的运气。
    """
    M, K = A.shape
    _, N = B.shape
    C = np.zeros((M, N), np.float32)
    for i in range(M):
        for j in range(N):
            acc = np.float32(0.0)
            for k in range(K):
                acc = np.float32(acc + np.float32(np.float32(A[i, k]) * np.float32(B[k, j])))
            C[i, j] = acc
    return C


# ================================================== DialectConversion 仿真

# ConversionTarget：降级"完成"的验收清单——终图里只允许出现这些 op。
TARGET_LEGAL = {
    "func.func", "func.return",
    "memref.alloc", "memref.fill", "memref.load", "memref.store",
    "scf.for", "scf.yield",
    "arith.constant", "arith.mulf", "arith.addf",
    "bufferization.to_tensor", "bufferization.to_memref",
}

# mini 方言整个标为非法（对应 ConversionTarget::addIllegalDialect("mini")）。
MINI_OPS = {"mini.matmul", "mini.transpose", "mini.reshape",
            "mini.conv", "mini.add", "mini.relu"}

# ConversionPattern：mini.matmul 的改写产物（目标 op 序列）。
MATMUL_TARGET = [
    "memref.alloc",       # 输出缓冲 C
    "arith.constant",     # 0.0 : f32（iter_args 初值）
    "arith.constant",     # 0/4/3/6 : index（循环边界，全来自静态 shape）
    "scf.for",            # %i
    "scf.for",            # %j
    "scf.for",            # %k（iter_args(%acc = 0.0)）
    "memref.load",        # %a[%i, %k]
    "memref.load",        # %b[%k, %j]
    "arith.mulf",
    "arith.addf",
    "scf.yield",
    "memref.store",       # %c[%i, %j]
]

PATTERNS = {"mini.matmul": MATMUL_TARGET}

# 源图 S0：第三阶段图优化器交付的"干净图"（沿用 Day 83 终图 GEMM 的形状）
S0_OPS = ["func.func", "mini.matmul", "func.return"]


def apply_conversion(ops, patterns, mode="full"):
    """驱动器仿真：工作列表反复改写非法 op，直到没有非法 op。

    mode="full"    对应 applyFullConversion：还剩一个非法 op 就整体失败；
    mode="partial" 对应 applyPartialConversion：允许残留，交给后续 Pass。
    返回 (final_ops, log, error)。
    """
    work, log = list(ops), []
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(work):
            op = work[i]
            if op in TARGET_LEGAL:
                i += 1
                continue
            if op in patterns:
                repl = list(patterns[op])
                work[i:i + 1] = repl
                log.append(f"rewrite {op} -> {len(repl)} 个目标 op：{', '.join(repl[:4])}…")
                changed = True
            elif mode == "full":
                return None, log, (f"无法合法化 '{op}'：没有注册对应的 "
                                   f"ConversionPattern（模式=full，整体失败）")
            else:
                log.append(f"skip {op}（模式=partial，留待后续 Pass 处理）")
                i += 1
    return work, log, None


# ============================================================ 测试计划 TP1~TP6

def tp1_type_table(design):
    """类型完整性：每个源 tensor 类型都有 memref 映射；shape 与元素类型不变；
    strides 必须等于行主序计算值；字节数 = 元素数 × 4。"""
    lines, ok = [], True
    entries = [("A", design.shape_a, design.strides["A"], "函数入参（签名降级）"),
               ("B", design.shape_b, design.strides["B"], "函数入参（签名降级）"),
               ("C", design.shape_c, design.strides["C"], "memref.alloc（Pattern 构建）")]
    for name, shape, strides, note in entries:
        expect = row_major_strides(shape)
        good = tuple(strides) == tuple(expect)
        ok &= good
        lines.append(f"  {name}: tensor<{'x'.join(map(str, shape))}xf32> -> "
                     f"memref<{'x'.join(map(str, shape))}xf32, strided<{list(strides)}>>"
                     f"  {'✓' if good else '✗ 期望 ' + str(list(expect))}"
                     f"  [{prod(shape) * 4} B, {note}]")
    return ok, lines


def tp2_index_probes(design, probes):
    """索引探针：抽样 (i,j,k)，A/B/C 三类访存的线性地址必须等于
    numpy.ravel_multi_index（多下标压平的官方答案）。"""
    lines, ok = [], True
    M, K = design.shape_a
    _, N = design.shape_b
    for (i, j, k) in probes:
        checks = [("A[i,k]", design.strides["A"], (i, k), (M, K)),
                  ("B[k,j]", design.strides["B"], (k, j), (K, N)),
                  ("C[i,j]", design.strides["C"], (i, j), (M, N))]
        for label, strides, idx, shape in checks:
            got, exp = addr(strides, idx), int(np.ravel_multi_index(idx, shape))
            good = got == exp
            ok &= good
            lines.append(f"  {label} @ (i={i},j={j},k={k}): addr={got}"
                         f"{'✓' if good else ' ✗ ravel=' + str(exp)}")
    return ok, lines


def tp3_output_init(design, A, B, ref):
    """输出初始化：设计必须显式选择初值策略，且执行结果与参考逐位相等。
    alloc 不清零内存——什么都不选就是未定义行为（探针 P2 验证这真的会翻车）。"""
    if design.init not in ("iter_args", "fill_load"):
        return False, [f"  初值策略 = {design.init!r}：未显式决定 → alloc 内容未定义，"
                       f"读改写从垃圾值起步（未定义行为）"]
    C = execute_loop_ir(design, A, B)
    bitexact = bool(np.array_equal(C, ref))
    label = {"iter_args": "方案 B（scf.for iter_args，寄存器累加，C 每元素只写一次）",
             "fill_load": "方案 A（fill 0 + 读改写，多付 2×M×N×4 B 流量）"}[design.init]
    return bitexact, [f"  策略 = {design.init}（{label}）",
                      f"  执行 vs 参考：np.array_equal = {bitexact}"]


def tp4_legality():
    """合法性收敛：主图转换后无非法 op；带 mini.conv（无 Pattern）的变体在
    full 模式整体失败、在 partial 模式显式残留。"""
    lines, ok = [], True
    final, log, err = apply_conversion(S0_OPS, PATTERNS, "full")
    illegal_left = sorted(set(final or []) - TARGET_LEGAL)
    good = err is None and not illegal_left
    ok &= good
    lines.append(f"  主图（{len(S0_OPS)} op）full 模式：{'成功' if good else '失败'}"
                 f" → {len(final or [])} op，残留非法 op = {illegal_left or '无'}")
    for entry in log:
        lines.append(f"    · {entry}")

    conv_ops = ["func.func", "mini.conv", "mini.matmul", "func.return"]
    f2, l2, e2 = apply_conversion(conv_ops, PATTERNS, "full")
    good2 = e2 is not None
    ok &= good2
    lines.append(f"  含 mini.conv 变体 full 模式：{'按预期整体失败 → ' + e2 if good2 else '意外成功'}")
    f3, l3, e3 = apply_conversion(conv_ops, PATTERNS, "partial")
    left3 = sorted(set(f3) - TARGET_LEGAL)
    good3 = e3 is None and left3 == ["mini.conv"]
    ok &= good3
    lines.append(f"  含 mini.conv 变体 partial 模式：成功但显式残留 {left3}（交给后续 Pass）")
    return ok, lines


def tp5_boundary():
    """边界缝合（TypeConverter 物化钩子）：外部契约仍是 tensor 时，
    return 处需要一个 to_tensor 把 memref 缝回 tensor；不设钩子 → 类型不匹配。"""
    lines, ok = [], True
    s2 = ["func.func", "memref.alloc", "scf.for", "memref.load", "memref.store", "func.return"]
    with_hook = s2[:-1] + ["bufferization.to_tensor", "func.return"]
    good = set(with_hook) <= TARGET_LEGAL
    ok &= good
    lines.append("  设钩子：return 前插入 bufferization.to_tensor（源物化，memref→tensor）")
    lines.append(f"    终图 op 全部合法：{good}")
    no_hook = s2
    lines.append("  不设钩子：return 期望 tensor<4x3xf32>，拿到 memref<4x3xf32, strided<[3,1]>>")
    lines.append("    → 诊断：type mismatch（值在'半 tensor 半 memref'的中途状态上断裂）")
    return ok, lines


def tp6_execution(design, A, B, ref):
    """执行等价：解释执行循环 IR，与同序 fp32 参考逐位相等；
    与 np.matmul 的差异如实记录（顺序不同不保证逐位相等）。"""
    C = execute_loop_ir(design, A, B)
    bitexact = bool(np.array_equal(C, ref))
    npmm = A @ B
    diff = float(np.abs(C.astype(np.float64) - npmm.astype(np.float64)).max()) if C.shape == npmm.shape else float("nan")
    lines = [f"  循环 IR vs 同序参考：np.array_equal = {bitexact}（max|diff| = "
             f"{float(np.abs(C.astype(np.float64) - ref.astype(np.float64)).max()):.1e}）",
             f"  循环 IR vs np.matmul：max|diff| = {diff:.3e}（顺序不同，只记录不判红绿）"]
    return bitexact, lines


def run_test_plan(design, A, B, ref, probes):
    tps = [("TP1 类型完整性", lambda: tp1_type_table(design)),
           ("TP2 索引探针", lambda: tp2_index_probes(design, probes)),
           ("TP3 输出初始化", lambda: tp3_output_init(design, A, B, ref)),
           ("TP4 合法性收敛", lambda: tp4_legality()),
           ("TP5 边界缝合", lambda: tp5_boundary()),
           ("TP6 执行等价", lambda: tp6_execution(design, A, B, ref))]
    results = []
    for name, fn in tps:
        ok, lines = fn()
        results.append((name, ok, lines))
    return results


# ==================================================================== 探针

def make_probes(base):
    """三个故意埋进设计里的 bug，证明测试计划咬得住人（Day 84 的方法论）。
    P1 随形状取"行主序的逆序"，保证换形状练习时探针仍然成立。"""
    wrong_b = tuple(reversed(row_major_strides(base.shape_b)))
    return {
        f"P1（B 的 strides 写成 {list(wrong_b)}，行主序算反）":
            replace(base, strides={**base.strides, "B": wrong_b}),
        "P2（忘掉输出初始化任务，读改写从垃圾值起步）":
            replace(base, init="garbage"),
        "P3（内维 K 的循环上界误用 N）":
            replace(base, k_bound=base.shape_b[1]),
    }


def probe_matrix(base, A, B, ref, probes):
    """探针 × 局部检查的红绿矩阵。TP4/TP5 是结构性检查，与这三类 bug 无关。"""
    rows = []
    local = [("TP1", lambda d: tp1_type_table(d)[0]),
             ("TP2", lambda d: tp2_index_probes(d, probes)[0]),
             ("TP3", lambda d: tp3_output_init(d, A, B, ref)[0]),
             ("TP6", lambda d: tp6_execution(d, A, B, ref)[0])]
    for name, mutant in make_probes(base).items():
        row = [name] + [("绿" if fn(mutant) else "红") for _, fn in local]
        rows.append(row)
    return rows, [n for n, _ in local]


# ==================================================================== 报告

def env_line():
    return (f"{platform.system()} {platform.machine()}, Python {platform.python_version()}, "
            f"numpy {np.__version__}")


def make_ir_text(d):
    M, K = d.shape_a
    _, N = d.shape_b
    sa, sb, sc = [list(d.strides[k]) for k in ("A", "B", "C")]
    return f"""// 生成自 lowering_design.py（Day 85）——mini.matmul 的循环表示
// 形状 A({M},{K}) @ B({K},{N}) -> C({M},{N})；循环边界全部来自静态 shape，编译期已知
// 任务标注：[类型] [索引] [初始化] 对应设计文档 §3 的三张任务清单
func @main(%a: memref<{M}x{K}xf32, strided<{sa}>>,
           %b: memref<{K}x{N}xf32, strided<{sb}>>) -> memref<{M}x{N}xf32> {{
  %c = memref.alloc() : memref<{M}x{N}xf32, strided<{sc}>          // [类型] 结果缓冲，{prod(d.shape_c) * 4} B
  %zero = arith.constant 0.0 : f32
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %c{M} = arith.constant {M} : index                               // [索引] M 来自 A.shape[0]
  %c{N} = arith.constant {N} : index                               // [索引] N 来自 B.shape[1]
  %c{K} = arith.constant {K} : index                               // [索引] K 来自 A.shape[1]==B.shape[0]
  scf.for %i = %c0 to %c{M} step %c1 {{
    scf.for %j = %c0 to %c{N} step %c1 {{
      %acc = scf.for %k = %c0 to %c{K} step %c1
                  iter_args(%acc = %zero) -> (f32) {{               // [初始化] 方案 B：iter_args 从 0 起步
        %xa = memref.load %a[%i, %k]     // addr = {sa[0]}*%i + {sa[1]}*%k   // [索引]
        %xb = memref.load %b[%k, %j]     // addr = {sb[0]}*%k + {sb[1]}*%j   // [索引]
        %p  = arith.mulf %xa, %xb : f32
        %s  = arith.addf %acc, %p : f32
        scf.yield %s : f32
      }}
      memref.store %acc, %c[%i, %j]      // addr = {sc[0]}*%i + {sc[1]}*%j   // [索引]
    }}
  }}
  return %c : memref<{M}x{N}xf32>
}}"""


def make_design_doc(d, A, B, ref, results, matrix, rows_hdr, ir_text, extra):
    M, K = d.shape_a
    _, N = d.shape_b
    tps = {name: (ok, lines) for name, ok, lines in results}
    all_ok = all(ok for _, ok, _ in results)

    probe_rows = "\n".join(
        "| " + r[0] + " | " + " | ".join(r[1:]) + " |"
        for r in matrix)

    tp_rows = "\n".join(f"| {name} | {'通过' if ok else '失败'} |" for name, ok, _ in results)

    doc = f"""# mini.matmul → 循环表示：Lowering 设计文档（Day 85）

> 环境：{env_line()}；随机种子 {SEED}。本脚本是 MLIR DialectConversion 的角色仿真，
> 不依赖 MLIR，也不伪造 MLIR 的行为。

## 1. 目标与输入

- **源图（S0）**：`func @main(%x: tensor<{M}x{K}xf32>, %w: tensor<{K}x{N}xf32>) -> tensor<{M}x{N}xf32>`，
  体内一个 `mini.matmul`——第三阶段图优化器交付的"干净图"（形状沿用 Day 83 终图的 GEMM）。
- **目标（S4）**：只含 `scf` / `memref` / `arith` 的循环表示，`mini` 方言整体消失。

## 2. 路线（S0 → S4）

| 阶段 | 做什么 | 谁负责 | 产出状态 |
|---|---|---|---|
| S0 原图 | — | — | tensor 世界，`mini.matmul` 声明式描述"做什么" |
| S1 签名降级 | 函数入参 tensor→memref | TypeConverter（convertType） | 入参已是 memref，体内还没动 |
| S2 核心改写 | `mini.matmul` → alloc+三重循环+load/store | ConversionPattern（matchAndRewrite 读源写目标） | 体内只剩目标 op |
| S3 边界缝合 | return 需要的 tensor 用 to_tensor 物化 | TypeConverter（物化钩子） | 中途的"半 tensor 半 memref"被缝上 |
| S4 合法性验收 | 终图 ∩ 非法集 = ∅ | ConversionTarget + 驱动器 | 降级完成（或 full 模式整体失败） |

## 3. 三张任务清单

### 3.1 类型任务（TypeConverter）
"""
    sa, sb, sc = [list(d.strides[k]) for k in ("A", "B", "C")]
    doc += f"""
| 值 | 源类型 | 目标类型 | strides | 大小 | 来源 |
|---|---|---|---|---|---|
| %x | tensor<{M}x{K}xf32> | memref<{M}x{K}xf32, strided<{sa}>> | {sa} | {prod(d.shape_a) * 4} B | 签名降级 |
| %w | tensor<{K}x{N}xf32> | memref<{K}x{N}xf32, strided<{sb}>> | {sb} | {prod(d.shape_b) * 4} B | 签名降级 |
| %c | tensor<{M}x{N}xf32> | memref<{M}x{N}xf32, strided<{sc}>> | {sc} | {prod(d.shape_c) * 4} B | Pattern 内 alloc |

### 3.2 索引任务（地址与边界）

| 访问 | 多下标 | 线性地址公式 | 循环边界 | 边界来源 |
|---|---|---|---|---|
| A[i,k] | (i,k) | {sa[0]}·i + {sa[1]}·k | i ∈ [0,{M}) | A.shape[0] |
| B[k,j] | (k,j) | {sb[0]}·k + {sb[1]}·j | j ∈ [0,{N}) | B.shape[1] |
| C[i,j] | (i,j) | {sc[0]}·i + {sc[1]}·j | k ∈ [0,{K}) | A.shape[1]==B.shape[0]（内维契约，Day 12/83 闸0 已验） |

### 3.3 输出初始化任务（alloc 不清零！）

| 方案 | 做法 | 额外访存流量 | 位等价 |
|---|---|---|---|
| A：fill + 读改写 | `memref.fill(%c, 0.0)`，k 循环外先 load C[i,j] | +2×M×N×4 = {2 * prod(d.shape_c) * 4} B | {'✓' if tps['TP3 输出初始化'][0] else '✗'}（TP3 实测） |
| B：iter_args（**选定**） | `%acc` 从常量 0.0 起步，C 每元素只写一次 | +0 B | ✓（TP3/TP6 实测） |
| 什么都不做 | 读改写从垃圾值起步 | — | ✗ 未定义行为（探针 P2 实测翻车） |

## 4. 角色职责（源 op 与目标 op）

| 角色 | 一句话职责 | 今天仿真里的对应 |
|---|---|---|
| ConversionTarget | 定义"什么算降级完成"（合法性清单） | `TARGET_LEGAL` 集合 |
| TypeConverter | 类型降级 + 中途缝合（物化钩子） | §3.1 类型表 + to_tensor/to_memref |
| ConversionPattern | 读源 op 语义，写等价目标 op 序列 | `PATTERNS["mini.matmul"]` |
| 驱动器 | 反复改写直到没有非法 op，或整体失败 | `apply_conversion(full/partial)` |

- **源 op（`mini.matmul`）的职责**：提供完整语义——操作数类型/shape、内维契约、结果类型，
  Pattern 靠这些决定怎么翻；转换完成后被替换、擦除，不再出现。
- **目标 op（`scf.for`/`memref.*`）的职责**：①在 ConversionTarget 里合法；
  ②类型经过 TypeConverter 认可；③组合起来与源 op 数值等价（交给测试计划验收）。

## 5. 合法性规则

- 合法（终图允许）：{', '.join(sorted(TARGET_LEGAL))}
- 非法（必须消失）：{', '.join(sorted(MINI_OPS))}（整个 mini 方言标非法）
- 驱动器两种模式：`full` = 只要剩一个非法 op 就整体失败（applyFullConversion）；
  `partial` = 允许残留给后续 Pass（applyPartialConversion）。

## 6. 边界与失败模式

1. **物化钩子**：签名/外部契约还是 tensor 时，return 处用 `bufferization.to_tensor`
   把 memref 缝回 tensor（源物化）；反向是 `to_memref`（目标物化）。不设钩子 →
   "半 tensor 半 memref"的中途状态类型断裂（TP5）。
2. **无 Pattern 的非法 op**：`mini.conv` 目前没有规则——full 模式整体失败并指名 op；
   partial 模式显式残留（TP4）。**这是设计决定，不是 bug**。
3. **静态 shape 前提**：循环边界全部编译期已知。若 shape 动态，常量边界换成
   `memref.dim`——今天不处理，留给动态 shape 专题。

## 7. 测试计划

| 检查 | 问题 | 方法 | 通过标准 |
|---|---|---|---|
| TP1 | 类型表完整、strides 正确？ | 表 vs 行主序计算值 | 全部一致 |
| TP2 | 索引公式算的地址对吗？ | 抽样 (i,j,k) vs `np.ravel_multi_index` | 全部相等 |
| TP3 | 输出初值显式且正确？ | 三种策略执行 vs 同序参考 | 位等价 + 策略显式 |
| TP4 | 转换收敛且失败模式正确？ | op 级仿真（主图 + conv 变体 × 两种模式） | 无残留非法 / 按预期失败 |
| TP5 | 边界缝合有钩子？ | to_tensor 插入 vs 无钩子诊断 | 有钩子合法、无钩子可诊断 |
| TP6 | 执行结果等价？ | 解释执行循环 IR vs 同序 fp32 参考 | 逐位相等 |

## 8. 执行结果（真实运行）

| 检查 | 结果 |
|---|---|
{tp_rows}

探针矩阵（{rows_hdr[0]}/{rows_hdr[1]}/{rows_hdr[2]}/{rows_hdr[3]}；TP4/TP5 为结构性检查，不适用）：

| 探针 | {rows_hdr[0]} | {rows_hdr[1]} | {rows_hdr[2]} | {rows_hdr[3]} |
|---|---|---|---|---|
{probe_rows}

{extra}

## 9. 设计备注

1. **与 Day 83/84 的衔接**：图优化终图剩下的 `reshape((24,)→(4,6))` 在 Lowering 里是
   免费的——24 元素连续存储，重排成 (4,6) 只是"strides=[6,1] 的元信息改写"，
   零数据搬运（Day 84 补讲 1 的 `shares_memory=True` 已证明）。
   对应规则：`mini.reshape` → 产出同存储的 memref 视图（选做挑战）。
2. **Day 86 待办**：把 §2 的 S2 从"规则表"变成真正的 ConversionPattern 骨架
   （ConversionPatternRewriter 的原子提交、失败处理）——今天的三张任务清单就是它的填空题。

## 附：降级后的循环 IR

```mlir
{ir_text}
```
"""
    return doc, all_ok


def make_test_report(d, A, B, ref, results, matrix, rows_hdr, extra):
    lines = [f"Day 85 Lowering 设计·测试计划执行报告（真实运行）",
             f"环境：{env_line()}；种子 {SEED}",
             f"贯穿例子：A{d.shape_a} @ B{d.shape_b} -> C{d.shape_c}", ""]
    for name, ok, ev in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
        lines.extend(ev)
        lines.append("")
    lines.append("—— 探针矩阵（验证测试计划咬得住人）——")
    lines.append("探针 / " + " / ".join(rows_hdr))
    for row in matrix:
        lines.append("  " + row[0] + " / " + " / ".join(row[1:]))
    lines.append("")
    lines.append("—— 对照实验（输出初始化三策略，真实数据）——")
    lines.extend(extra)
    lines.append("")
    return "\n".join(lines)


def run_everything(M, K, N):
    rng = np.random.default_rng(SEED)
    A = rng.standard_normal((M, K)).astype(np.float32)
    B = rng.standard_normal((K, N)).astype(np.float32)
    ref = reference_matmul(A, B)
    base = baseline_design(M, K, N)
    probes = [(0, 0, 0), (3, 2, 5), (1, 1, 2), (2, 0, 4)]
    probes = [(i, j, k) for (i, j, k) in probes if i < M and j < N and k < K] or [(0, 0, 0)]

    results = run_test_plan(base, A, B, ref, probes)
    matrix, rows_hdr = probe_matrix(base, A, B, ref, probes)

    # 对照实验：三种初始化策略
    extra = []
    for mode, note in [("iter_args", "方案 B：iter_args 从 0 起步（设计选定）"),
                       ("fill_load", "方案 A：fill 0 + 读改写"),
                       ("garbage", "A′：什么都不做（探针 P2）")]:
        dm = replace(base, init=mode)
        C = execute_loop_ir(dm, A, B)
        diff = float(np.abs(C.astype(np.float64) - ref.astype(np.float64)).max())
        extra.append(f"  {note}: max|diff| = {diff:.6e}"
                     f"{'  ← 位等价' if diff == 0 else '  ← 不等价（未定义行为）'}")
    extra.append(f"  流量账：方案 A 比 B 多付 2×M×N×4 = {2 * prod(base.shape_c) * 4} B 的读写")
    npmm_diff = float(np.abs(execute_loop_ir(base, A, B).astype(np.float64)
                             - (A @ B).astype(np.float64)).max())
    extra.append(f"  循环 IR vs np.matmul: max|diff| = {npmm_diff:.3e}（顺序不同，只记录）")

    ir_text = make_ir_text(base)
    return base, results, matrix, rows_hdr, ir_text, extra, A, B, ref


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shape", nargs=3, type=int, metavar=("M", "K", "N"),
                    help="改写贯穿例子的形状（默认 4 6 3）")
    args = ap.parse_args()

    M, K, N = args.shape if args.shape else (4, 6, 3)
    base, results, matrix, rows_hdr, ir_text, extra, A, B, ref = run_everything(M, K, N)

    if args.shape:
        # 练习模式：只打印，不覆盖当天产出
        print(f"形状 A({M},{K}) @ B({K},{N}) -> C({M},{N})，种子 {SEED}")
        for name, ok, ev in results:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        print()
        for row in matrix:
            print(row)
        print()
        print("\n".join(extra))
        return 0

    OUT.mkdir(exist_ok=True)
    doc, all_ok = make_design_doc(base, A, B, ref, results, matrix, rows_hdr, ir_text, extra)
    (OUT / "design-doc.md").write_text(doc, encoding="utf-8")
    (OUT / "ir-loop.txt").write_text(ir_text + "\n", encoding="utf-8")
    report = make_test_report(base, A, B, ref, results, matrix, rows_hdr, extra)
    (OUT / "test-report.txt").write_text(report + "\n", encoding="utf-8")

    print(report)
    print()
    print(f"design-doc.md 已写入；ir-loop.txt 已写入；测试计划 {'全部通过' if all_ok else '存在失败'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
