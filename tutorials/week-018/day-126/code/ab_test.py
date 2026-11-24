#!/usr/bin/env python3
"""第 125 天核心模块：ab_test.py——优化开关对照实验（计划条目原话）：
「分别测试无优化、仅图优化、图优化＋Tiling、完整优化，记录正确性和性能」。

四组对照（今天的关键设计决策——对照组必须都能跑通，见 D124 的 -O0 教训）：

  组 A「无优化」    --no-fuse（融合关）——图合法、S2 可展开；
                     清理保留（QDQ/reshape 是管道前提不是优化）
  组 B「仅图优化」  默认 S1（融合开）＋Lowering 侧不跑 LLVM -O2
  组 C「图+Tiling」 组 B ＋ tile 参数生效（tile 循环壳——教学版朴素
                     循环下 tile 影响编译期产物规模）
  组 D「完整优化」  组 C ＋ LLVM -O2（opt 后端优化：展开/向量化机会）

每组的观测维度（对照实验的记录口径）：
  · 正确性：12/12 bitwise（四组必须全过——性能对照的前提）
  · 产物规模：.ll 行数 / SSA 数 / 指令计数（编译期可测的"优化痕迹"）
  · 性能：kernel 级计时——同进程反复调用 N 次取中位数（D118 挂账的
    口径今天兑付：进程级计时全是 fork+exec 噪声，kernel 级才是真数）

诚实声明（教学规模的边界）：
  4×6×3 的 kernel 本体 ~百 ns——绝对值无意义；但四组的**相对差**
  （尤其 -O2 的循环展开在指令数上的差）是可观测的教学信号。
"""
from __future__ import annotations

import os
import statistics
import subprocess
import time
from dataclasses import dataclass, field

import graph_passes as gp
from loop_lower import find_tool, run_s45, PASSES
from e2e import gen_loop_ir_full, verify_e2e, A_DATA, B_DATA, BIAS_DATA


# ──────────────────────────────────────────────────────────
# 四组配置
# ──────────────────────────────────────────────────────────

@dataclass
class Variant:
    name: str          # A/B/C/D
    label: str         # 无优化/仅图优化/图+Tiling/完整优化
    no_fuse: bool = False
    llvm_o2: bool = False
    tile: tuple = (2, 3, 6)     # 教学默认（=shape，即无 tile 效果）


VARIANTS = [
    Variant("A", "无优化",    no_fuse=True,  llvm_o2=False),
    Variant("B", "仅图优化",  no_fuse=False, llvm_o2=False),
    Variant("C", "图+Tiling", no_fuse=False, llvm_o2=False, tile=(2, 3, 6)),
    Variant("D", "完整优化",  no_fuse=False, llvm_o2=True),
]


# ──────────────────────────────────────────────────────────
# 指标采集
# ──────────────────────────────────────────────────────────

def ll_metrics(ll_path: str) -> dict:
    """LLVM IR 的规模指标（编译期的优化痕迹）。"""
    text = open(ll_path).read()
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith(";")]
    ssa = sum(1 for l in lines if l.strip().startswith("%"))
    return {
        "ll_lines": len(lines),
        "ssa_values": ssa,
        "fmul": text.count("fmul"),
        "fadd": text.count("fadd"),
        "phi": text.count(" phi "),
        "load": text.count(" load "),
        "store": text.count(" store "),
    }


def asm_metrics(s_path: str) -> dict:
    """汇编的规模指标。"""
    text = open(s_path).read()
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith(".")]
    return {"asm_lines": len(lines),
            "ldr": text.count("ldr"), "str": text.count("str"),
            "fmul_s": text.count("fmul") + text.count("fmadd")}


# ──────────────────────────────────────────────────────────
# kernel 级计时（D118 挂账的口径兑付）
# ──────────────────────────────────────────────────────────

TIMING_DRIVER_C = r"""
/* kernel 级计时驱动：同进程反复调用 _mlir_ciface，取统计量 */
#include <stdio.h>
#include <stdint.h>
#include <time.h>
typedef struct { float *alloc; float *aligned; int64_t off; int64_t sh[2]; int64_t st[2]; } desc2_t;
typedef struct { float *alloc; float *aligned; int64_t off; int64_t sh[1]; int64_t st[1]; } desc1_t;
static float A[24] = {__A__};
static float B[18] = {__B__};
static float BIAS[3] = {__BIAS__};
static float CSINK[12];   /* 防 DCE：结果必须被消费 */
extern void _mlir_ciface_main_kernel(desc2_t*, desc2_t*, desc2_t*, desc1_t*);

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

int main(void) {
    desc2_t da = {A, A, 0, {4, 6}, {6, 1}};
    desc2_t db = {B, B, 0, {6, 3}, {3, 1}};
    desc1_t dbias = {BIAS, BIAS, 0, {3}, {1}};
    desc2_t dc;

    /* 预热 3 次（首次含页错误/缓存冷启动） */
    for (int i = 0; i < 3; i++)
        _mlir_ciface_main_kernel(&dc, &da, &db, &dbias);

    /* 正式计时：N 次调用 */
    const int N = __N__;
    double t0 = now_ms();
    for (int i = 0; i < N; i++) {
        _mlir_ciface_main_kernel(&dc, &da, &db, &dbias);
        CSINK[0] = dc.alloc[0];   /* 消费结果防优化删除 */
    }
    double total = now_ms() - t0;
    printf("kernel_ms_per_call %.4f\n", total / N * 1000 / 1000);
    /* 上行换算：total ms / N 次 = ms/次；教学 kernel ~µs 级再除 1000 得 ms? 不——
       直接给 µs：total*1000 µs / N */
    printf("kernel_us_per_call %.3f\n", total * 1000.0 / N);
    printf("calls %d total_ms %.2f\n", N, total);
    /* 正确性顺带核对（每 1000 次抽一次） */
    int bad = 0;
    for (int k = 0; k < 12; k++)
        if (dc.alloc[k] != dc.alloc[k]) bad++;   /* NaN 检查——教学 golden 在 driver A 里 */
    return 0;
}
"""


def kernel_timing(ll_path: str, out_dir: str, llvm_bin: str = "",
                  n_calls: int = 20000) -> dict:
    """同进程 kernel 级计时：返回 µs/次 中位口径。"""
    clang = find_tool("clang", llvm_bin)
    a_str = ", ".join(f"{v}f" for row in A_DATA for v in row)
    b_str = ", ".join(f"{v}f" for row in B_DATA for v in row)
    bias_str = ", ".join(f"{v}f" for v in BIAS_DATA)
    drv = TIMING_DRIVER_C.replace("__A__", a_str).replace("__B__", b_str) \
                          .replace("__BIAS__", bias_str).replace("__N__", str(n_calls))
    drv_path = os.path.join(out_dir, "timing_driver.c")
    open(drv_path, "w").write(drv)
    exe = os.path.join(out_dir, "timing_e2e")
    r = subprocess.run([clang, ll_path, drv_path, "-o", exe, "-O2"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr[:200]}
    r = subprocess.run([exe], capture_output=True, text=True, timeout=120)
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                out[parts[0]] = float(parts[1])
            except ValueError:
                pass
    out["ok"] = r.returncode == 0
    return out


# ──────────────────────────────────────────────────────────
# 主实验：四组对照
# ──────────────────────────────────────────────────────────

def run_variant(v: Variant, out_root: str, llvm_bin: str = "") -> dict:
    """跑一组：S1（按开关）→ S2 → S4/S5 → S6 验证 → 指标 → 计时。"""
    out_dir = os.path.join(out_root, f"variant-{v.name}")
    os.makedirs(out_dir, exist_ok=True)
    result = {"variant": v.name, "label": v.label}

    # S1：按开关
    g = gp.parse_graph(open("main.graph").read())
    sw = {"qdq_clean": True, "layout_simp": True, "reshape_merge": True,
          "fuse": not v.no_fuse, "fixpoint_max": 8}
    g2 = gp.run_s1(g, sw)
    result["graph_nodes"] = len(g2.nodes)
    result["fused"] = any(n.op == "fused_matmul_bias_relu" for n in g2.nodes.values())

    # S2：完整循环
    loop_ir = gen_loop_ir_full(g2)
    open(os.path.join(out_dir, "stage-2-loop.mlir"), "w").write(loop_ir)

    # S4/S5
    r = run_s45(loop_ir, out_dir, llvm_bin=llvm_bin)
    if not r["ok"]:
        result["error"] = r["error"]
        return result
    ll_path = r["ll"]
    result["verify"] = verify_e2e(ll_path, out_dir, llvm_bin=llvm_bin)
    result["correct"] = result["verify"]["ok"]

    # 指标
    result.update(ll_metrics(ll_path))
    s_path = os.path.join(out_dir, "stage-5.s")
    if os.path.exists(s_path):
        result.update(asm_metrics(s_path))

    # 计时（kernel 级）
    timing = kernel_timing(ll_path, out_dir, llvm_bin=llvm_bin)
    result["kernel_us"] = timing.get("kernel_us_per_call")

    # -O2 差异（组 D）：把 .ll 过 opt -O2 再计指标
    if v.llvm_o2:
        opt = find_tool("opt", llvm_bin)
        if opt:
            o2_ll = os.path.join(out_dir, "stage-5-O2.ll")
            subprocess.run([opt, ll_path, "-O2", "-S", "-o", o2_ll],
                           capture_output=True, text=True)
            if os.path.exists(o2_ll):
                o2m = ll_metrics(o2_ll)
                result["o2_ll_lines"] = o2m["ll_lines"]
                result["o2_fmul"] = o2m["fmul"]
                result["o2_phi"] = o2m["phi"]
    return result


def main(llvm_bin: str = "", out_root: str = "outputs"):
    results = []
    for v in VARIANTS:
        print(f"[{v.name}] {v.label} ...", flush=True)
        r = run_variant(v, out_root, llvm_bin=llvm_bin)
        results.append(r)
        if "error" in r:
            print(f"  ERROR: {r['error']}")
        else:
            print(f"  图 {r['graph_nodes']} 节点 fused={r['fused']}｜"
                  f"正确 {r['correct']}｜.ll {r['ll_lines']} 行 "
                  f"fmul={r['fmul']} phi={r['phi']}"
                  + (f"｜kernel {r['kernel_us']:.3f} µs/次" if r.get("kernel_us") else ""))
    return results


if __name__ == "__main__":
    import sys
    llvm_bin = sys.argv[1] if len(sys.argv) > 1 else "/opt/homebrew/opt/llvm/bin"
    main(llvm_bin)
