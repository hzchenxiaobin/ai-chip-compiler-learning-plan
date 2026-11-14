#!/usr/bin/env python3
"""第 151 天核心模块：optimize.py——实施有依据的优化（验 H1/H2）。

计划条目："选择一种循环顺序、Tile、融合或内存策略进行修改；
产出：优化代码、IR 对照和正确性测试。"

D150 的三假设 → 今天的三个实验：
  A：O2 展开（验 H1：循环控制开销）——llc -O0 vs -O2
  B：tile 扫描（验 H2：数据复用）——朴素 vs 块循环
  C：组合（O2＋tile）——正交性检验
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
LLVM = "/opt/homebrew/opt/llvm/bin"
M = N = K = 160


class Desc2(ctypes.Structure):
    _fields_ = [("alloc", ctypes.c_void_p), ("aligned", ctypes.c_void_p),
                ("off", ctypes.c_int64), ("sh", ctypes.c_int64 * 2), ("st", ctypes.c_int64 * 2)]


class Desc1(ctypes.Structure):
    _fields_ = [("alloc", ctypes.c_void_p), ("aligned", ctypes.c_void_p),
                ("off", ctypes.c_int64), ("sh", ctypes.c_int64 * 1), ("st", ctypes.c_int64 * 1)]


def md2(a):
    d = Desc2(); d.alloc = d.aligned = a.ctypes.data; d.off = 0
    d.sh[0], d.sh[1] = a.shape
    d.st[0], d.st[1] = a.strides[0]//4, a.strides[1]//4
    return d


def md1(a):
    d = Desc1(); d.alloc = d.aligned = a.ctypes.data; d.off = 0
    d.sh[0] = a.shape[0]; d.st[0] = 1
    return d


def gen_naive_ir(M, K, N):
    return f"""module {{
  func.func @main_kernel(%a: memref<{M}x{K}xf32, strided<[{K}, 1]>>,
                         %b: memref<{K}x{N}xf32, strided<[{N}, 1]>>,
                         %bias: memref<{N}xf32, strided<[1]>>)
      -> memref<{M}x{N}xf32> attributes {{ llvm.emit_c_interface }} {{
    %c = memref.alloc() : memref<{M}x{N}xf32>
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant {M} : index
    %cN = arith.constant {N} : index
    %cK = arith.constant {K} : index
    scf.for %i = %c0 to %cM step %c1 {{
      scf.for %j = %c0 to %cN step %c1 {{
        %bj = memref.load %bias[%j] : memref<{N}xf32, strided<[1]>>
        %acc = scf.for %k = %c0 to %cK step %c1
                    iter_args(%acc = %bj) -> (f32) {{
          %aij = memref.load %a[%i, %k] : memref<{M}x{K}xf32, strided<[{K}, 1]>>
          %bkj = memref.load %b[%k, %j] : memref<{K}x{N}xf32, strided<[{N}, 1]>>
          %p = arith.mulf %aij, %bkj : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }}
        %pos = arith.constant 0.0 : f32
        %cond = arith.cmpf ogt, %acc, %pos : f32
        %r = arith.select %cond, %acc, %pos : f32
        memref.store %r, %c[%i, %j] : memref<{M}x{N}xf32>
      }}
    }}
    func.return %c : memref<{M}x{N}xf32>
  }}
}}
"""


def gen_tiled_ir(M, K, N, TM, TN, TK):
    """块循环版（k 从 0 完整累加——D145 修复版）。"""
    return f"""module {{
  func.func @main_kernel(%a: memref<{M}x{K}xf32, strided<[{K}, 1]>>,
                         %b: memref<{K}x{N}xf32, strided<[{N}, 1]>>,
                         %bias: memref<{N}xf32, strided<[1]>>)
      -> memref<{M}x{N}xf32> attributes {{ llvm.emit_c_interface }} {{
    %c = memref.alloc() : memref<{M}x{N}xf32>
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant {M} : index
    %cN = arith.constant {N} : index
    %cK = arith.constant {K} : index
    %cTM = arith.constant {TM} : index
    %cTN = arith.constant {TN} : index
    scf.for %i0 = %c0 to %cM step %cTM {{
      scf.for %j0 = %c0 to %cN step %cTN {{
        scf.for %i = %i0 to %cM step %c1 {{
          scf.for %j = %j0 to %cN step %c1 {{
            %bj = memref.load %bias[%j] : memref<{N}xf32, strided<[1]>>
            %acc = scf.for %k = %c0 to %cK step %c1
                        iter_args(%acc = %bj) -> (f32) {{
              %aij = memref.load %a[%i, %k] : memref<{M}x{K}xf32, strided<[{K}, 1]>>
              %bkj = memref.load %b[%k, %j] : memref<{K}x{N}xf32, strided<[{N}, 1]>>
              %p = arith.mulf %aij, %bkj : f32
              %s = arith.addf %acc, %p : f32
              scf.yield %s : f32
            }}
            %pos = arith.constant 0.0 : f32
            %cond = arith.cmpf ogt, %acc, %pos : f32
            %r = arith.select %cond, %acc, %pos : f32
            memref.store %r, %c[%i, %j] : memref<{M}x{N}xf32>
          }}
        }}
      }}
    }}
    func.return %c : memref<{M}x{N}xf32>
  }}
}}
"""


def build(ir, tag, opt_level="0"):
    from loop_lower import run_s45
    d = os.path.join(OUT, tag)
    r = run_s45(ir, d, llvm_bin=LLVM)
    if not r["ok"]:
        return None
    so = os.path.join(d, "lib.so")
    obj = so.replace(".so", ".o")
    subprocess.run([f"{LLVM}/llc", r["ll"], f"-O{opt_level}", "-filetype=obj",
                    "-relocation-model=pic", "-o", obj], check=True)
    subprocess.run([f"{LLVM}/clang", "-shared", "-undefined", "dynamic_lookup",
                    obj, "-o", so], check=True)
    os.remove(obj)
    lib = ctypes.CDLL(so)
    lib._mlir_ciface_main_kernel.restype = None
    lib._mlir_ciface_main_kernel.argtypes = [ctypes.c_void_p] * 4
    return lib


def bench(lib, rounds=5, inner=2):
    rng = np.random.default_rng(151)
    A = rng.standard_normal((M, K)).astype(np.float32)
    B = rng.standard_normal((K, N)).astype(np.float32)
    bias = rng.standard_normal(N).astype(np.float32)
    golden = np.maximum(A @ B + bias, 0).astype(np.float32)
    da, db, dbias = md2(A), md2(B), md1(bias)
    # 正确性
    dc = Desc2()
    lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                 ctypes.byref(db), ctypes.byref(dbias))
    out = np.ctypeslib.as_array(
        ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
        shape=(M, N)).copy()
    correct = np.allclose(out, golden, atol=1e-3)
    # 性能
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for _ in range(inner):
            dc = Desc2()
            lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                         ctypes.byref(db), ctypes.byref(dbias))
        times.append((time.perf_counter() - t0) / inner * 1000)
    times.sort()
    med = times[len(times)//2]
    gf = 2 * M * K * N / (med / 1000) / 1e9
    return med, gf, correct


def main():
    os.makedirs(OUT, exist_ok=True)
    results = {}

    print("== 基线（朴素＋O0——D148 复现）==")
    lib0 = build(gen_naive_ir(M, K, N), "e0-naive-O0", "0")
    med0, gf0, ok0 = bench(lib0)
    results["baseline"] = {"ms": round(med0, 2), "gflops": round(gf0, 3), "correct": ok0}
    print(f"  {med0:.2f} ms｜{gf0:.3f} GFLOPS｜{'✓' if ok0 else '✗'}")

    print("\n== 实验 A：O2 展开（验 H1：循环控制开销）==")
    libA = build(gen_naive_ir(M, K, N), "eA-naive-O2", "2")
    medA, gfA, okA = bench(libA)
    speedup_a = med0 / medA
    results["expA_O2"] = {"ms": round(medA, 2), "gflops": round(gfA, 3),
                          "speedup": round(speedup_a, 1), "correct": okA}
    print(f"  {medA:.2f} ms｜{gfA:.3f} GFLOPS｜加速 {speedup_a:.1f}×｜{'✓' if okA else '✗'}")
    print(f"  H1 判定：{'成立（循环开销确实是主因之一）' if speedup_a > 2 else '不成立'}")

    print("\n== 实验 B：tile 扫描（验 H2：数据复用）==")
    best_b = None
    for TM, TN in [(32, 32), (64, 64), (16, 16)]:
        libB = build(gen_tiled_ir(M, K, N, TM, TN, K), f"eB-tile{TM}x{TN}", "0")
        if libB is None:
            continue
        medB, gfB, okB = bench(libB, rounds=3, inner=1)
        print(f"  tile=({TM},{TN}): {medB:.2f} ms｜{gfB:.3f} GF｜{'✓' if okB else '✗'}")
        if okB and (best_b is None or medB < best_b[1]):
            best_b = ((TM, TN), medB, gfB)
    if best_b:
        speedup_b = med0 / best_b[1]
        results["expB_tile"] = {"best_tile": str(best_b[0]), "ms": round(best_b[1], 2),
                                "gflops": round(best_b[2], 3),
                                "speedup": round(speedup_b, 1)}
        print(f"  最佳 tile={best_b[0]}：{best_b[1]:.2f} ms｜加速 {speedup_b:.1f}×")
        print(f"  H2 判定：{'成立（复用有效）' if speedup_b > 1.2 else '部分/不成立（教学 tile 的重复计算抵消收益）'}")

    print("\n== 实验 C：组合（O2＋tile）==")
    if best_b:
        TM, TN = best_b[0]
        libC = build(gen_tiled_ir(M, K, N, TM, TN, K), f"eC-tile{TM}x{TN}-O2", "2")
        if libC:
            medC, gfC, okC = bench(libC, rounds=3, inner=1)
            speedup_c = med0 / medC
            results["expC_combo"] = {"ms": round(medC, 2), "gflops": round(gfC, 3),
                                     "speedup": round(speedup_c, 1), "correct": okC}
            print(f"  {medC:.2f} ms｜{gfC:.3f} GF｜加速 {speedup_c:.1f}×｜{'✓' if okC else '✗'}")
            print(f"  组合 vs 单独：{speedup_c:.1f}× vs A {speedup_a:.1f}×/B {med0/best_b[1]:.1f}×——"
                  f"{'正交收益' if speedup_c > max(speedup_a, med0/best_b[1]) else '非正交'}")

    json.dump(results, open(os.path.join(OUT, "optimize.json"), "w"),
              ensure_ascii=False, indent=2)
    ok = ok0 and okA and (best_b is not None)
    print(f"\n判定：{'PASS——H1/H2 实验完成（数据入档）' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
