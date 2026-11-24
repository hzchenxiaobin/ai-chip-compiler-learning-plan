#!/usr/bin/env python3
"""第 124 天核心模块：e2e.py——端到端 MatMul+Bias+Relu：S2 点循环补全 + S6 golden 验证。

D122 的 S2 只写了循环壳（tile 层），点循环是注释；S6 是骨架。今天补全两块：

  1. gen_loop_ir_full：点循环真实展开（load/mulf/addf/store 逐点写全，
     bias 融在 k=0 圈——D85~90 任务单的语义；无 tile 壳简化为朴素三重循环，
     tile 壳版本留给 D125 对照）
  2. verify_e2e：编译产物（.ll 经 llc/clang 或直接 JIT）在真实数据上执行，
     与 numpy golden 逐点 bitwise 对照——S6 的第一份真实现

执行路线：AOT（clang 编 .ll + C driver，D118 路线 1 的自动化）。
贯穿数据：D118 的手算友好数据（A 0.5 倍数、B 整数、golden C[0][1]=24.5）。
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

import graph_passes as gp
from loop_lower import find_tool, LowerError, PASSES


# ──────────────────────────────────────────────────────────
# S2 完整版：点循环展开（朴素三重循环——今天的正确性基线）
# ──────────────────────────────────────────────────────────

def gen_loop_ir_full(g: gp.Graph) -> str:
    """把 S1 终图展开成**完整**的三重循环 IR（点循环真实写全）。

    与 D122 版的区别：点循环不再是注释——load/mulf/addf/store 逐点写全，
    bias 加在 k=0 圈（i/j 循环内先 bias 后累加，等价语义且免条件判断）。
    朴素版（无 tile 壳）＝正确性基线；tile 壳版本 D125 做。
    """
    supported = {"arg", "const", "reshape", "matmul", "add", "relu",
                 "fused_matmul_bias_relu"}
    for n in g.nodes.values():
        if n.op not in supported:
            raise LowerError("E202", f"S2 点循环展开：不支持的算子 {n.op}（节点 {n.nid}）")

    main_op = None
    for n in g.nodes.values():
        if n.op in ("fused_matmul_bias_relu", "matmul"):
            main_op = n
    if main_op is None:
        raise LowerError("E202", "S2：图中没有 matmul/fused 主算子")

    # --no-fuse 情形：matmul 的下游 add(bias) 与 relu 是独立节点——
    # 找到它们以便在同一条链里展开（否则语义不完整：D125 组 A 的教训）
    tail_bias = None
    tail_relu = False
    if main_op.op == "matmul":
        users = [u for u in g.nodes.values() if main_op.nid in u.inputs]
        for u in users:
            if u.op == "add":
                tail_bias = u      # add 的另一个输入应是 const bias
                for u2 in g.nodes.values():
                    if u2.op == "relu" and u.nid in u2.inputs:
                        tail_relu = True
            if u.op == "relu":
                tail_relu = True

    a_node = g.nodes[main_op.inputs[0]]
    b_node = g.nodes[main_op.inputs[1]]
    M, K = _shape(g, a_node)
    K2, N = _shape(g, b_node)
    if K != K2:
        raise LowerError("E202", f"S2：K 不咬合 {K}≠{K2}")
    if main_op.op == "fused_matmul_bias_relu":
        bias_node = g.nodes[main_op.inputs[2]]
    elif tail_bias is not None:
        # 独立 add：另一个输入是 const bias
        other = [i for i in tail_bias.inputs if i != main_op.nid]
        bias_node = g.nodes[other[0]] if other else None
    else:
        bias_node = None
    has_bias = bias_node is not None
    apply_relu = (main_op.op == "fused_matmul_bias_relu") or tail_relu

    L = []
    L.append("// minic S2 完整版：图 IR → 朴素三重循环（点循环写全）")
    L.append("// 语义：C = relu(A @ B + bias)（bias 融在 k=0 圈）")
    L.append("module {")
    L.append(f"  func.func @main_kernel(")
    L.append(f"      %a: memref<{M}x{K}xf32, strided<[{K}, 1]>>,")
    L.append(f"      %b: memref<{K}x{N}xf32, strided<[{N}, 1]>>")
    if has_bias:
        L.append(f"      , %bias: memref<{N}xf32, strided<[1]>>")
    L.append(f"    ) -> memref<{M}x{N}xf32> attributes {{ llvm.emit_c_interface }} {{")
    L.append(f"    %c = memref.alloc() : memref<{M}x{N}xf32>")
    L.append("    %c0 = arith.constant 0 : index")
    L.append(f"    %cM = arith.constant {M} : index")
    L.append(f"    %cN = arith.constant {N} : index")
    L.append(f"    %cK = arith.constant {K} : index")
    L.append("    %c1 = arith.constant 1 : index")
    # 逐点：直接三重循环（i 最外、k 最内——朴素序；顺序无关正确性）
    L.append("    scf.for %i = %c0 to %cM step %c1 {")
    L.append("      scf.for %j = %c0 to %cN step %c1 {")
    # bias 初值（k=0 语义：acc 从 bias[j] 开始）
    if has_bias:
        L.append(f"        %bj = memref.load %bias[%j] : memref<{N}xf32, strided<[1]>>")
        L.append("        %acc = scf.for %k = %c0 to %cK step %c1")
        L.append("                    iter_args(%acc = %bj) -> (f32) {")
    else:
        L.append("        %z = arith.constant 0.0 : f32")
        L.append("        %acc = scf.for %k = %c0 to %cK step %c1")
        L.append("                    iter_args(%acc = %z) -> (f32) {")
    L.append(f"          %aij = memref.load %a[%i, %k] : memref<{M}x{K}xf32, strided<[{K}, 1]>>")
    L.append(f"          %bkj = memref.load %b[%k, %j] : memref<{K}x{N}xf32, strided<[{N}, 1]>>")
    L.append("          %p = arith.mulf %aij, %bkj : f32")
    L.append("          %s = arith.addf %acc, %p : f32")
    L.append("          scf.yield %s : f32")
    L.append("        }")
    # relu（fused 语义）
    if apply_relu:
        L.append("        %pos = arith.constant 0.0 : f32")
        L.append("        %cond = arith.cmpf ogt %acc, %pos : f32".replace("ogt", '\\"ogt\\"', 1) if False else "        %cond = arith.cmpf ogt, %acc, %pos : f32")
        L.append("        %r = arith.select %cond, %acc, %pos : f32")
        L.append(f"        memref.store %r, %c[%i, %j] : memref<{M}x{N}xf32>")
    else:
        L.append(f"        memref.store %acc, %c[%i, %j] : memref<{M}x{N}xf32>")
    L.append("      }")
    L.append("    }")
    L.append(f"    func.return %c : memref<{M}x{N}xf32>")
    L.append("  }")
    L.append("}")
    return "\n".join(L)


def _shape(g, n):
    if n.op == "const":
        return tuple(n.attrs["shape"])
    if n.op == "reshape":
        return tuple(n.attrs["new_shape"])
    if n.op == "arg":
        import re
        m = re.match(r"tensor<([\dx]+)xf32>", n.out_type)
        return tuple(int(x) for x in m.group(1).split("x"))
    raise LowerError("E202", f"S2：无法推断 {n.nid} 的 shape")


# ──────────────────────────────────────────────────────────
# S6：golden 验证（AOT 执行路线）
# ──────────────────────────────────────────────────────────

# D118 的手算友好数据（C[0][1]=0.5×2−1×5+2×8+0+1.5×14−0.5×17=24.5 可手算）
A_DATA = [[0.5, -1.0, 2.0, 0.0, 1.5, -0.5],
          [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
          [-2.0, 0.5, 0.0, 3.0, -1.0, 2.0],
          [0.0, 0.0, 0.5, 0.5, 0.5, 0.5]]
B_DATA = [[1.0, 2.0, 3.0],
          [4.0, 5.0, 6.0],
          [7.0, 8.0, 9.0],
          [10.0, 11.0, 12.0],
          [13.0, 14.0, 15.0],
          [16.0, 17.0, 18.0]]
# D83 的 bias（add const）——但注意 S1 图里 bias 是 [0.125, -0.25, 0.5]
BIAS_DATA = [0.125, -0.25, 0.5]

DRIVER_C = r"""
/* minic S6 验证驱动（D118 路线 1 的自动化版） */
#include <stdio.h>
#include <stdint.h>
typedef struct { float *alloc; float *aligned; int64_t off; int64_t sh[2]; int64_t st[2]; } desc2_t;
typedef struct { float *alloc; float *aligned; int64_t off; int64_t sh[1]; int64_t st[1]; } desc1_t;
/* A/B 数据内嵌（与 e2e.py 的 A_DATA/B_DATA 一致） */
static float A[24] = {__A_DATA__};
static float B[18] = {__B_DATA__};
static float BIAS[3] = {__BIAS_DATA__};
static float C[12] = {0};
/* golden 内嵌（与 numpy 参考一致，编译时替换） */
static const float GOLDEN[12] = {__GOLDEN__};
extern void _mlir_ciface_main_kernel(desc2_t *out, desc2_t *a, desc2_t *b, desc1_t *bias);
int main(void) {
    desc2_t da = {A, A, 0, {4, 6}, {6, 1}};
    desc2_t db = {B, B, 0, {6, 3}, {3, 1}};
    desc1_t dbias = {BIAS, BIAS, 0, {3}, {1}};
    desc2_t dc = {0, 0, 0, {4, 3}, {3, 1}};
    _mlir_ciface_main_kernel(&dc, &da, &db, &dbias);
    if (dc.alloc == NULL) { printf("FAIL: null\n"); return 1; }
    int bad = 0;
    for (int k = 0; k < 12; k++) {
        printf("C[%d]=%.4f (golden %.4f)\n", k, dc.alloc[k], GOLDEN[k]);
        if (dc.alloc[k] != GOLDEN[k]) bad++;
    }
    printf("%s\n", bad == 0 ? "12/12 点 bitwise 一致" : "VERIFY FAIL");
    return bad == 0 ? 0 : 1;
}
"""


def golden_numpy():
    """numpy 参考：relu(A@B + bias)——与 S1 融合算子的语义完全一致。"""
    import numpy as np
    a = __import__("numpy").array(A_DATA, dtype=__import__("numpy").float32)
    b = __import__("numpy").array(B_DATA, dtype=__import__("numpy").float32)
    bias = __import__("numpy").array(BIAS_DATA, dtype=__import__("numpy").float32)
    # 注意：浮点语义——kernel 按 k 序累加（bias 先进 acc），numpy 的 @ 用
    # 分块/向量序——两者可能差 1ulp。bitwise 判据按「k 序参考」计算。
    M, N, K = 4, 3, 6
    c = numpy_zeros((M, N))
    for i in range(M):
        for j in range(N):
            acc = bias[j]                      # k=0 圈从 bias 开始
            for k in range(K):
                acc = acc + a[i, k] * b[k, j]  # k 序逐次舍入
            c[i, j] = max(acc, 0.0)
    return c


def numpy_zeros(shape):
    import numpy as np
    return np.zeros(shape, dtype=np.float32)


def verify_e2e(ll_path: str, out_dir: str, llvm_bin: str = "") -> dict:
    """S6：编译 .ll + 内嵌 golden 的 C driver → 执行 → bitwise 对照。

    返回 {"ok": bool, "detail": [...]}——driver 自己打印逐点对照。
    """
    import numpy as np
    clang = find_tool("clang", llvm_bin)
    if not clang:
        return {"ok": False, "detail": ["E205 clang 未找到"]}

    golden = golden_numpy()
    g_str = ", ".join(f"{v:.6f}f" for v in golden.flatten())
    a_str = ", ".join(f"{v}f" for row in A_DATA for v in row)
    b_str = ", ".join(f"{v}f" for row in B_DATA for v in row)
    bias_str = ", ".join(f"{v}f" for v in BIAS_DATA)

    driver = DRIVER_C.replace("__A_DATA__", a_str).replace("__B_DATA__", b_str) \
                     .replace("__BIAS_DATA__", bias_str).replace("__GOLDEN__", g_str)
    drv_path = os.path.join(out_dir, "verify_driver.c")
    open(drv_path, "w").write(driver)

    exe = os.path.join(out_dir, "verify_e2e")
    r = subprocess.run([clang, ll_path, drv_path, "-o", exe, "-O1"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "detail": [f"E205 编译失败: {r.stderr[:300]}"]}

    r = subprocess.run([exe], capture_output=True, text=True, timeout=30)
    lines = r.stdout.strip().splitlines()
    ok = r.returncode == 0 and any("12/12" in ln for ln in lines)
    return {"ok": ok, "detail": lines, "exit": r.returncode}
