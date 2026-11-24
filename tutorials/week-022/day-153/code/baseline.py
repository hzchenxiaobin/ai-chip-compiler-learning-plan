#!/usr/bin/env python3
"""第 148 天核心模块：baseline.py——选择慢用例并建立基线。

计划条目："选择一个明显较慢的 Shape，记录基线时间、GFLOPS、编译
配置和运行环境；产出：基线性能表和可复现命令。"

用较大 shape 的朴素 kernel 做慢用例（教学版可测的"慢"）：
  B1 选型     候选 shape 扫描——选出"明显慢"的那个
  B2 基线     多轮计时（中位数口径）＋GFLOPS＋环境记录
  B3 复现     一条命令重现（含全部参数）
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
import time

import numpy as np

import graph_passes as gp
from loop_lower import run_s45
from e2e import gen_loop_ir_full

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
LLVM = "/opt/homebrew/opt/llvm/bin"


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


def build_naive(M, K, N):
    """编译朴素 matmul+bias+relu kernel（无 tile——慢用例的形态）。"""
    ir = f"""module {{
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
    tag = f"naive-{M}x{K}x{N}"
    d = os.path.join(OUT, tag)
    r = run_s45(ir, d, llvm_bin=LLVM)
    if not r["ok"]:
        return None, ir
    so = os.path.join(d, "lib.so")
    obj = so.replace(".so", ".o")
    subprocess.run([f"{LLVM}/llc", r["ll"], "-O0", "-filetype=obj", "-relocation-model=pic",
                    "-o", obj], check=True)
    subprocess.run([f"{LLVM}/clang", "-shared", "-undefined", "dynamic_lookup",
                    obj, "-o", so], check=True)
    os.remove(obj)
    lib = ctypes.CDLL(so)
    lib._mlir_ciface_main_kernel.restype = None
    lib._mlir_ciface_main_kernel.argtypes = [ctypes.c_void_p] * 4
    return lib, ir


def bench(lib, M, K, N, rounds=5, inner=3):
    """kernel 级计时：rounds 轮×inner 次取中位（D125 口径）。"""
    rng = np.random.default_rng(148)
    A = rng.standard_normal((M, K)).astype(np.float32)
    B = rng.standard_normal((K, N)).astype(np.float32)
    bias = rng.standard_normal(N).astype(np.float32)
    da, db, dbias = md2(A), md2(B), md1(bias)
    sink = np.zeros(1, dtype=np.float32)
    # 预热
    for _ in range(2):
        dc = Desc2()
        lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                     ctypes.byref(db), ctypes.byref(dbias))
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for _ in range(inner):
            dc = Desc2()
            lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                         ctypes.byref(db), ctypes.byref(dbias))
            sink[0] = dc.alloc and 1 or 0
        times.append((time.perf_counter() - t0) / inner * 1000)  # ms
    times.sort()
    med = times[len(times)//2]
    flops = 2 * M * K * N
    gflops = flops / (med / 1000) / 1e9
    return med, gflops


def main():
    os.makedirs(OUT, exist_ok=True)
    print("== B1 选型：候选 shape 扫描（朴素 kernel）==")
    candidates = [(128, 128, 128), (160, 160, 160), (96, 160, 160)]
    results = {}
    for (M, K, N) in candidates:
        lib, _ = build_naive(M, K, N)
        if lib is None:
            print(f"  {M}x{K}x{N}: 编译失败")
            continue
        med, gf = bench(lib, M, K, N, rounds=3, inner=1)
        results[(M, K, N)] = (med, gf)
        print(f"  {M}x{K}x{N}: {med:.1f} ms｜{gf:.3f} GFLOPS")
    # 选最慢且可重复的
    chosen = max(results, key=lambda k: results[k][0])
    print(f"\n  选定慢用例：{chosen}（{results[chosen][0]:.1f} ms）")

    print("\n== B2 基线：多轮计时（中位数）＋GFLOPS＋环境 ==")
    M, K, N = chosen
    lib, ir = build_naive(M, K, N)
    med, gf = bench(lib, M, K, N, rounds=7, inner=3)
    env = {
        "machine": f"{platform.machine()} {platform.system()}",
        "python": platform.python_version(),
        "llvm": subprocess.run([f"{LLVM}/clang", "--version"],
                               capture_output=True, text=True).stdout.split("\n")[0],
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    print(f"  中位数：{med:.2f} ms｜GFLOPS：{gf:.4f}")
    print(f"  环境：{env['machine']}｜{env['llvm']}")
    baseline = {
        "shape": f"{M}x{K}x{N}", "median_ms": round(med, 2),
        "gflops": round(gf, 4), "kernel": "naive matmul+bias+relu（无 tile）",
        "rounds": 7, "inner_calls": 3, "env": env,
        "repro": f"cd tutorials/week-022/day-148/code && python3 baseline.py",
    }
    json.dump(baseline, open(os.path.join(OUT, "baseline.json"), "w"),
              ensure_ascii=False, indent=2)
    print("\n== B3 复现 ==")
    print(f"  {baseline['repro']}")
    print(f"  基线落盘 baseline.json")

    ok = med > 1.0 and gf < 10   # "明显慢"的教学判据：朴素 O0 kernel（GFLOPS << 峰值）
    print(f"\n判定：{'选定成立（明显慢——第 22 周的归因对象）' if ok else '重选'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
