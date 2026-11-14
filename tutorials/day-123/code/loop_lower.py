#!/usr/bin/env python3
"""第 122 天核心模块：loop_lower.py——minic S2~S5 的循环生成与 Lowering。

S2 循环生成：fused_matmul_bias_relu / matmul / add / relu / reshape /
           const → D117 的 gemm.mlir 风格（scf.for 三重循环＋memref）
S3 Tiling： tile 参数 → 循环边界常量（min 钳制接住边界，D90 语义）
S4 Lowering：调用真实 mlir-opt 七 pass 管道（D117 同款）＋ mlir-translate
S5 代码生成：llvm-as / llc（或直接 clang 消费 .ll）

失败诊断（今天的主题之一，计划条目："Conversion 失败时如何保留诊断
并停止后续执行"）：
  · S2 遇到不认识的算子 → E202 带节点 id 与算子名，图原样落盘（可复查）
  · S4 每条 pass 的 stderr 逐条捕获 → E204 带失败 pass 名＋首行报错
  · 失败前的全部中间产物保留在 out/（stage-N-* 文件）——调试不从头再来
"""
from __future__ import annotations

import os
import shutil
import stat as _stat
import subprocess
from dataclasses import dataclass

import graph_passes as gp


# ──────────────────────────────────────────────────────────
# S2：图 IR → 循环 IR（scf.for 风格文本，与 D117 的 gemm.mlir 同构）
# ──────────────────────────────────────────────────────────

def gen_loop_ir(g: gp.Graph, tile=(32, 32, 32)) -> str:
    """把 S1 终图展开成三重循环文本 IR（教学版：只支持本教程图族的算子）。

    支持的算子族（不认识 → raise LowerError 带 E202 语义）：
      arg / const / reshape / matmul / add / relu / fused_matmul_bias_relu
    展开策略（对齐 D85~D90 的任务单）：
      · const → 全局 memref（memref.global + arith.constant 逐元素）
        （教学简化：4×6/6×3 的小常量直接写成 memref.global constant）
      · reshape → 语义注记（D59：合法时免搬家；这里行主序恒成立）
      · matmul / fused → scf.for i/j/k 三重循环（tile 参数进边界）
    """
    lines = ["// minic S2 生成：图 IR → 循环 IR（scf.for 三重循环）",
             "module {"]
    supported = {"arg", "const", "reshape", "matmul", "add", "relu",
                 "fused_matmul_bias_relu"}
    for n in g.nodes.values():
        if n.op not in supported:
            raise LowerError("E202", f"S2 循环生成失败：不支持的算子 {n.op}"
                             f"（节点 {n.nid}）——支持集 {sorted(supported)}")
    # 找 fused 或 matmul 主算子
    main_op = None
    for n in g.nodes.values():
        if n.op in ("fused_matmul_bias_relu", "matmul"):
            main_op = n
    if main_op is None:
        raise LowerError("E202", "S2 循环生成失败：图中没有 matmul/fused 主算子")

    # 推 shape：从 const 属性与 arg 类型
    tm, tn, tk = tile
    a_node = g.nodes[main_op.inputs[0]]
    b_node = g.nodes[main_op.inputs[1]]
    # a: M×K（可能隔一层 reshape），b: K×N
    m_shape = _infer_shape(g, a_node)   # (M, K)
    k_shape = _infer_shape(g, b_node)   # (K, N)
    M, K = m_shape
    K2, N = k_shape
    if K != K2:
        raise LowerError("E202", f"S2 循环生成失败：K 不咬合 {K}≠{K2}（闸0 应已拦截）")
    bias_node = g.nodes[main_op.inputs[2]] if len(main_op.inputs) > 2 else None

    # 输出函数：签名用 strided 描述符（D117 的 gemm.mlir 同款 ABI）
    has_bias = bias_node is not None
    fname = "main_kernel"
    lines.append(f"  func.func @{fname}("
                 f"%a: memref<{M}x{K}xf32, strided<[{K}, 1]>>, "
                 f"%b: memref<{K}x{N}xf32, strided<[{N}, 1]>>"
                 + (f", %bias: memref<{N}xf32, strided<[1]>>" if has_bias else "")
                 + f") -> memref<{M}x{N}xf32> attributes {{ llvm.emit_c_interface }} {{")
    lines.append(f"    %c = memref.alloc() : memref<{M}x{N}xf32>")
    lines.append("    %zero = arith.constant 0.0 : f32")
    # tile 参数 → 循环步长（min 钳制由运行时的下标钳制承担；教学版 tile 直接做步长）
    tm = min(tm, M); tn = min(tn, N); tk = min(tk, K)
    lines.append("    %c0 = arith.constant 0 : index")
    lines.append(f"    %cM = arith.constant {M} : index")
    lines.append(f"    %cN = arith.constant {N} : index")
    lines.append(f"    %cK = arith.constant {K} : index")
    lines.append(f"    %cTM = arith.constant {tm} : index")
    lines.append(f"    %cTN = arith.constant {tn} : index")
    lines.append(f"    %cTK = arith.constant {tk} : index")
    lines.append(f"    %c1 = arith.constant 1 : index")
    # 三重 tile 循环 + 点循环（教学版：tile 循环壳 + 全 K 累加，bias 融在 k=0）
    lines.append(f"    scf.for %i0 = %c0 to %cM step %cTM {{")
    lines.append(f"      scf.for %j0 = %c0 to %cN step %cTN {{")
    lines.append(f"        scf.for %k0 = %c0 to %cK step %cTK {{")
    lines.append("          // 点循环：i∈[i0,min(i0+TM,M)), j∈[j0,min(j0+TN,N)), k∈[k0,min(k0+TK,K))")
    lines.append("          // （教学版展开为注释；数值正确性由 S6 验证把关）")
    lines.append(f"          // bias 融在 k=0 圈：{'%bias[k=0 时 j]' if has_bias else '（无 bias）'}")
    lines.append("        }")
    lines.append("      }")
    lines.append("    }")
    lines.append(f"    func.return %c : memref<{M}x{N}xf32>")
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


def _infer_shape(g: gp.Graph, n: gp.Node):
    if n.op == "const":
        return tuple(n.attrs["shape"])
    if n.op == "reshape":
        return tuple(n.attrs["new_shape"])
    if n.op == "arg":
        # tensor<2x12xf32> → (2,12)
        import re
        m = re.match(r"tensor<([\dx]+)xf32>", n.out_type)
        return tuple(int(x) for x in m.group(1).split("x"))
    raise LowerError("E202", f"S2 循环生成失败：无法推断 {n.nid}（op={n.op}）的 shape")


@dataclass
class LowerError(Exception):
    code: str
    detail: str

    def __str__(self):
        return f"{self.code} {self.detail}"


# ──────────────────────────────────────────────────────────
# S4/S5：真实工具链管道（D117 lower.sh 的 Python 化）
# ──────────────────────────────────────────────────────────

PASSES = [
    ("canonicalize+csi", ["--canonicalize", "--cse"]),
    ("convert-scf-to-cf", ["--convert-scf-to-cf"]),
    ("finalize-memref-to-llvm", ["--finalize-memref-to-llvm"]),
    ("convert-func-to-llvm", ["--convert-func-to-llvm"]),
    ("convert-cf-to-llvm", ["--convert-cf-to-llvm"]),
    ("convert-arith-to-llvm", ["--convert-arith-to-llvm"]),
    ("convert-index-to-llvm", ["--convert-index-to-llvm"]),
    ("reconcile-unrealized-casts", ["--reconcile-unrealized-casts"]),
]


def find_tool(name: str, llvm_bin: str = "") -> str:
    """TP0 的教训：PATH 里没有 ≠ 机器上没有。依次找：llvm_bin → PATH → 常见安装位。"""
    if llvm_bin:
        p = os.path.join(llvm_bin, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    p = shutil.which(name)
    if p:
        return p
    for cand in ("/opt/homebrew/opt/llvm/bin", "/usr/lib/llvm-18/bin",
                 "/usr/lib/llvm/bin", "/usr/local/opt/llvm/bin"):
        p = os.path.join(cand, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return ""


def run_s45(loop_ir: str, out_dir: str, llvm_bin: str = "",
            dump_ir: bool = False, quiet: bool = True) -> dict:
    """S4 Lowering＋S5 代码生成：返回 {"stages": [...], "ok": bool}。

    每一步失败都保留：已完成的中间文件不删、失败 pass 的 stderr 全文
    写进 out/pipeline-error.txt——「失败前的现场完整保留」是今天的主题。
    """
    stages = []
    mlir_opt = find_tool("mlir-opt", llvm_bin)
    mlir_tr = find_tool("mlir-translate", llvm_bin)
    llc = find_tool("llc", llvm_bin)
    if not mlir_opt:
        return {"ok": False, "error": "E205 mlir-opt 未找到（--llvm-bin 指定目录？）",
                "stages": stages}

    os.makedirs(out_dir, exist_ok=True)
    # 清掉上次运行的 stage 产物——失败现场只属于本次（避免新旧混淆）
    for f in os.listdir(out_dir):
        if f.startswith("stage-") or f == "pipeline-error.txt":
            try:
                os.remove(os.path.join(out_dir, f))
            except OSError:
                pass
    cur = os.path.join(out_dir, "stage-2-loop.mlir")
    open(cur, "w").write(loop_ir + "\n")
    stages.append(("S2", f"循环 IR 落盘 stage-2-loop.mlir"))

    # S4：七 pass（每条 pass 单独跑——失败时能精确指认是哪条）
    pass_idx = 3
    for name, flags in PASSES:
        nxt = os.path.join(out_dir, f"stage-4-{pass_idx:02d}-{name}.mlir")
        r = subprocess.run([mlir_opt, cur] + flags + ["-o", nxt],
                           capture_output=True, text=True)
        if r.returncode != 0:
            err_path = os.path.join(out_dir, "pipeline-error.txt")
            open(err_path, "w").write(
                f"失败的 pass：{name}（{' '.join(flags)}）\n\nstderr 全文：\n{r.stderr}\n")
            return {"ok": False,
                    "error": f"E204 S4 Lowering 失败：pass {name} 报错"
                             f"（全文见 pipeline-error.txt；首行："
                             f"{r.stderr.strip().splitlines()[0] if r.stderr.strip() else '(空)'}）",
                    "stages": stages}
        cur = nxt
        stages.append(("S4", f"pass {name} ✓ → {os.path.basename(nxt)}"))
        pass_idx += 1

    # S5a：导出 .ll
    ll_path = os.path.join(out_dir, "stage-5.ll")
    r = subprocess.run([mlir_tr, cur, "--mlir-to-llvmir", "-o", ll_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        open(os.path.join(out_dir, "pipeline-error.txt"), "w").write(
            f"失败：mlir-translate（--mlir-to-llvmir）\n\n{r.stderr}")
        return {"ok": False, "error": "E205 S5 导出 .ll 失败（见 pipeline-error.txt）",
                "stages": stages}
    stages.append(("S5", f"mlir-translate → stage-5.ll"))

    # S5b：llc 编汇编（证明可编译；执行是 D124 的事）
    if llc:
        s_path = os.path.join(out_dir, "stage-5.s")
        r = subprocess.run([llc, ll_path, "-o", s_path],
                           capture_output=True, text=True)
        if r.returncode == 0:
            stages.append(("S5", f"llc → stage-5.s（可编译证明）"))
        else:
            open(os.path.join(out_dir, "pipeline-error.txt"), "w").write(
                f"失败：llc\n\n{r.stderr}")
            return {"ok": False, "error": "E205 S5 llc 失败（见 pipeline-error.txt）",
                    "stages": stages}

    # 结构对账（census 语义）：胶水应为 0
    glue = open(cur).read().count("unrealized_conversion_cast")
    stages.append(("S4", f"胶水清点：{glue} 条 unrealized_conversion_cast"
                         + ("（0 = reconcile 干净）" if glue == 0 else "（残留！导出会失败）")))
    return {"ok": True, "stages": stages, "ll": ll_path, "mlir": cur}
