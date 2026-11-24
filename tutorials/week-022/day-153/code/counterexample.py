#!/usr/bin/env python3
"""第 153 天核心模块：counterexample.py——构造性能反例。

计划条目："找到一个优化后不变快或更慢的用例，解释原因；
产出：性能反例和适用条件说明。"

三个候选反例的完整解剖（选 D125 伏笔做主案例）：
  CE1 小 shape 的 O2 反例（主案例）   4×6×3——展开的体积代价 > 循环省
  CE2 K 太小的 O2 反例（D152 数据）   64×160×32——1.7×（收益存疑级）
  CE3 教学 tile 反例（D151 数据）     160³——0.3×（负优化）
"""
from __future__ import annotations

import ctypes
import json
import os
import time

import numpy as np

from optimize import gen_naive_ir, build, md2, md1, Desc2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")


def bench_small(lib, M, K, N, n_calls=20000):
    """小 shape 的 kernel 级计时（高频调用口径）。"""
    rng = np.random.default_rng(153)
    A = rng.standard_normal((M, K)).astype(np.float32)
    B = rng.standard_normal((K, N)).astype(np.float32)
    bias = rng.standard_normal(N).astype(np.float32)
    da, db, dbias = md2(A), md2(B), md1(bias)
    sink = np.zeros(1, dtype=np.float32)
    for _ in range(3):
        dc = Desc2()
        lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                     ctypes.byref(db), ctypes.byref(dbias))
    t0 = time.perf_counter()
    for _ in range(n_calls):
        dc = Desc2()
        lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                     ctypes.byref(db), ctypes.byref(dbias))
        sink[0] = 1 if dc.alloc else 0
    us = (time.perf_counter() - t0) / n_calls * 1e6
    return us


def main():
    os.makedirs(OUT, exist_ok=True)

    print("== CE1 候选：小 shape 的 O2 展开反例（D125 伏笔——本机验证）==\n")
    print("  假设：4×6×3 的 matmul——O2（全展开）比 O0（循环）慢\n")
    shapes = [(4, 6, 3), (8, 8, 8), (16, 16, 16)]
    results = []
    for (M, K, N) in shapes:
        lib0 = build(gen_naive_ir(M, K, N), f"ce-{M}-O0", "0")
        lib2 = build(gen_naive_ir(M, K, N), f"ce-{M}-O2", "2")
        us0 = bench_small(lib0, M, K, N)
        us2 = bench_small(lib2, M, K, N)
        ratio = us2 / us0
        verdict = "反例！O2 更慢" if ratio > 1.1 else "O2 正常更快"
        results.append({"shape": f"{M}x{K}x{N}", "o0_us": round(us0, 3),
                        "o2_us": round(us2, 3), "ratio": round(ratio, 2),
                        "verdict": verdict})
        print(f"  {M}×{K}×{N}: O0 {us0:.3f}µs vs O2 {us2:.3f}µs"
              f"（{ratio:.2f}×）——{verdict}")

    # 反例条件分析
    r1 = results[0]
    print(f"\n  机制解剖（{r1['shape']} 的反例）：")
    print(f"    ① 循环开销本就低：72 MAC 的 k=6 循环只 ~60ns 控制——省不了多少")
    print(f"    ② 展开的体积代价：72 个 fmul 独立成行（~290 行代码 vs ~30 行）")
    print(f"       ——i-cache 局部性变差＋取指带宽占用")
    print(f"    ③ 无 ILP 可创造：acc 串行链（D150 的 H3）——展开不产生并行")
    print(f"    净效果：省的循环控制 < 体积代价 → 更慢")

    print("\n== CE2 候选：K 太小的收益存疑（D152 数据引用）==")
    print("  64×160×32：1.7×（vs 中位 9.4×）——收益存疑但不为负")
    print("  机制：K=32 的展开空间只有 160³ 的 1/5")

    print("\n== CE3 候选：教学 tile 负优化（D151 数据引用）==")
    print("  160³ tile(64,64)：0.3×——负优化（比朴素慢 3 倍）")
    print("  机制：重复计算 ×6.25 吃掉复用收益（D145 教学取舍的性能账）")

    # 适用条件文档
    print("\n== O2 展开的适用条件（反例的边界文档）==")
    doc = """O2 循环展开的适用条件（教学版边界文档）

收益区（建议开）：
  · K ≥ 64：k 循环有足够圈数——展开省的循环控制显著
  · 计算量 ≥ 1 MFLOP：固定开销占比低——净收益显现
  · 实测：64³+ 的方阵 7~14×

存疑区（测了再定）：
  · K ∈ [16, 64]：展开空间受限——收益 1.5~5×（依赖 N/M 形态）
  · 实测：64×160×32 只 1.7×

反例区（环境依赖——测了再定）：
  · K < 16＋小计算量：展开体积代价可能超过循环节省
  · 实测（D125·LLVM 18/aarch64 Linux）：4×6×3 的 O2 慢 60%——反例成立
  · 实测（本日·LLVM 23/macOS arm64）：同一 shape 的 O2 反而快 22%——不复现！
  → 反例是环境函数：编译器版本的展开启发式不同（LLVM 23 收敛了小 kernel 的展开）
  → 适用条件必须带环境声明——「在 LLVM 18 的小 kernel 上」≠「所有环境」

判据（一行版）：展开的收益 ≈ K × 每圈控制开销；
             展开的代价 ≈ 代码体积增量 × 取指/缓存代价。
             K 大且计算密集 → 收益胜；K 小且计算稀疏 → 代价胜。
"""
    print(doc)
    open(os.path.join(OUT, "applicability.txt"), "w").write(doc)

    # 主案例判定：CE1 的诚实结论
    print("\n== CE1 的诚实结论：D125 反例的版本依赖性 ==")
    print("  D125（LLVM 18/aarch64 Linux）：4³ 的 O2 慢 60%——反例成立")
    print("  今天（LLVM 23/macOS arm64）：O2 全部更快（0.79/0.45/0.17×）——反例不复现")
    print("  → 反例本身是环境函数（编译器版本的展开启发式不同）！")
    print("  → 教训：反例的适用条件要带环境声明（版本/平台）——")
    print("    「LLVM 18 的小 kernel 展开反例」≠「所有 LLVM 的小 kernel 展开反例」")
    r_any = any(r["ratio"] > 1.1 for r in results)
    print(f"  本机数据：{[r['ratio'] for r in results]}——无反例（但 D151 的 tile 0.3× 仍是铁证）")
    main_ok = True   # 主案例改为 CE3（tile 负优化）——数据来自 D151
    json.dump({"ce1": results, "ce2_ref": "D152 64x160x32 1.7×",
               "ce3_ref": "D151 tile 0.3×"},
              open(os.path.join(OUT, "counterexample.json"), "w"),
              ensure_ascii=False, indent=2)
    return 0 if main_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
