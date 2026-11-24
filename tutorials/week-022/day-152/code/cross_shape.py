#!/usr/bin/env python3
"""第 152 天：跨 Shape 验证——O2 收益的分布（≥6 shape）。"""
from __future__ import annotations
import ctypes, json, os, time
import numpy as np
from optimize import gen_naive_ir, build, md2, md1, Desc2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
LLVM = "/opt/homebrew/opt/llvm/bin"

SHAPES = [(32, 32, 32), (64, 64, 64), (96, 96, 96), (128, 128, 128),
          (160, 160, 160), (64, 160, 32), (32, 32, 160)]


def bench_shape(lib, M, K, N, rounds=3, inner=2):
    rng = np.random.default_rng(152)
    A = rng.standard_normal((M, K)).astype(np.float32)
    B = rng.standard_normal((K, N)).astype(np.float32)
    bias = rng.standard_normal(N).astype(np.float32)
    golden = np.maximum(A @ B + bias, 0).astype(np.float32)
    da, db, dbias = md2(A), md2(B), md1(bias)
    dc = Desc2()
    lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                 ctypes.byref(db), ctypes.byref(dbias))
    out = np.ctypeslib.as_array(ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
                                shape=(M, N)).copy()
    ok = np.allclose(out, golden, atol=1e-3)
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
    return med, 2*M*K*N/(med/1000)/1e9, ok


def main():
    os.makedirs(OUT, exist_ok=True)
    results = []
    print(f"{'shape':>14} {'O0 ms':>9} {'O2 ms':>9} {'加速':>7} {'O0 GF':>7} {'O2 GF':>7} {'对':>3}")
    for (M, K, N) in SHAPES:
        lib0 = build(gen_naive_ir(M, K, N), f"cs-{M}x{K}x{N}-O0", "0")
        lib2 = build(gen_naive_ir(M, K, N), f"cs-{M}x{K}x{N}-O2", "2")
        m0, g0, ok0 = bench_shape(lib0, M, K, N, rounds=2, inner=1)
        m2, g2, ok2 = bench_shape(lib2, M, K, N, rounds=2, inner=2)
        sp = m0 / m2
        results.append({"shape": f"{M}x{K}x{N}", "o0_ms": round(m0, 2),
                        "o2_ms": round(m2, 2), "speedup": round(sp, 1),
                        "o0_gf": round(g0, 3), "o2_gf": round(g2, 3), "correct": ok0 and ok2})
        print(f"{M:>5}x{K}x{N:<5} {m0:>8.2f} {m2:>8.2f} {sp:>6.1f}× {g0:>6.3f} {g2:>6.3f} {'✓' if ok0 and ok2 else '✗'}")

    sps = [r["speedup"] for r in results]
    print(f"\n加速分布：最小 {min(sps)}×｜中位 {sorted(sps)[len(sps)//2]}×｜最大 {max(sps)}×")
    print(f"（三个数都要报——不能只报最好 {max(sps)}×）")
    json.dump(results, open(os.path.join(OUT, "cross-shape.json"), "w"),
              ensure_ascii=False, indent=2)
    ok = all(r["correct"] for r in results) and len(results) >= 6
    print(f"\n判定：{'PASS——跨 shape 分布入档' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
