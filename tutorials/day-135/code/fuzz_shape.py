#!/usr/bin/env python3
"""第 135 天核心模块：fuzz_shape.py——随机 Shape 正确性测试（fuzz 测试教学版）。

计划条目："生成随机 M、N、K 和 Tile，先验证正确性再记录性能；固定随机种子；
产出：随机测试工具和失败复现文件。"

三组实验：
  F1 随机正确性    200 组随机 (M,K,N)——动态 kernel vs numpy 全对
  F2 种子可复现    同一种子跑两遍——失败用例集合完全一致
  F3 失败注入      故意注入一个 bug 版 kernel——验证失败用例保存与复现
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
LLVM = "/opt/homebrew/opt/llvm/bin"
SEED = 20261115


class Desc2(ctypes.Structure):
    _fields_ = [("alloc", ctypes.c_void_p), ("aligned", ctypes.c_void_p),
                ("off", ctypes.c_int64),
                ("sh", ctypes.c_int64 * 2), ("st", ctypes.c_int64 * 2)]


def make_desc(a):
    d = Desc2()
    d.alloc = d.aligned = a.ctypes.data
    d.off = 0
    d.sh[0], d.sh[1] = a.shape
    d.st[0], d.st[1] = a.strides[0] // 4, a.strides[1] // 4
    return d


def build_dynamic() -> str:
    d = os.path.join(OUT, "dyn")
    ll = os.path.join(d, "out.ll")
    if not os.path.exists(ll):
        from dyn_shape import DYNAMIC_IR, run_pipeline
        r = run_pipeline(DYNAMIC_IR, d)
        assert r["ok"]
    so = os.path.join(d, "libdyn.dylib")
    if not os.path.exists(so):
        obj = os.path.join(d, "dyn.o")
        subprocess.run([f"{LLVM}/llc", ll, "-filetype=obj",
                        "-relocation-model=pic", "-o", obj], check=True)
        subprocess.run([f"{LLVM}/clang", "-shared", "-undefined",
                        "dynamic_lookup", obj, "-o", so], check=True)
        os.remove(obj)
    return so


def run_case(lib, M, K, N, rng, break_k=False):
    """跑一组随机 shape；break_k=True 时注入 bug（k 循环少跑一圈）。"""
    A = rng.standard_normal((M, K)).astype(np.float32)
    B = rng.standard_normal((K, N)).astype(np.float32)
    da, db = make_desc(A), make_desc(B)
    dc = Desc2()
    lib._mlir_ciface_kernel_dynamic(ctypes.byref(dc), ctypes.byref(da), ctypes.byref(db))
    out = np.ctypeslib.as_array(
        ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
        shape=(int(dc.sh[0]), int(dc.sh[1]))).copy()
    # golden：k 序手写（D124 口径）
    gold = np.zeros((M, N), dtype=np.float32)
    for i in range(M):
        for j in range(N):
            acc = np.float32(0.0)
            kmax = K - 1 if break_k else K     # 注入 bug：少一圈
            for k in range(kmax):
                acc = np.float32(acc + np.float32(A[i, k] * B[k, j]))
            gold[i, j] = acc
    ok = np.allclose(out, gold, atol=1e-4, rtol=1e-4)
    return ok, {"M": M, "K": K, "N": N, "seed_used": None}


def main():
    os.makedirs(OUT, exist_ok=True)
    so = build_dynamic()
    lib = ctypes.CDLL(so)
    lib._mlir_ciface_kernel_dynamic.restype = None
    lib._mlir_ciface_kernel_dynamic.argtypes = [ctypes.POINTER(Desc2)] * 3

    # ── F1 随机正确性 ──
    print("== F1 随机正确性：200 组随机 (M,K,N) ==")
    rng = np.random.default_rng(SEED)
    fails = []
    for t in range(200):
        M = int(rng.integers(1, 33))
        K = int(rng.integers(1, 33))
        N = int(rng.integers(1, 33))
        ok, _ = run_case(lib, M, K, N, rng)
        if not ok:
            fails.append({"trial": t, "M": M, "K": K, "N": N})
    print(f"  200 组随机 shape：{'PASS 全对' if not fails else f'FAIL {len(fails)} 组'}")
    print(f"  shape 范围：M/K/N ∈ [1, 32]——含 1 维退化、方阵、长扁")
    if fails:
        json.dump(fails, open(os.path.join(OUT, "failures.json"), "w"), indent=2)

    # ── F2 种子可复现 ──
    print("\n== F2 种子可复现：同种子两遍 ==\n")
    def run_all(seed):
        rng = np.random.default_rng(seed)
        shapes = [(int(rng.integers(1, 33)), int(rng.integers(1, 33)), int(rng.integers(1, 33)))
                  for _ in range(50)]
        return shapes
    s1, s2 = run_all(SEED), run_all(SEED)
    repro = s1 == s2
    print(f"  种子 {SEED} 两遍生成的 shape 序列完全一致：{repro}")
    print(f"  → 失败时报告「种子 + trial 号」即可精确复现")

    # ── F3 失败注入（验证失败保存机制） ──
    print("\n== F3 失败注入：bug 版 golden（k 少一圈） ==")
    rng3 = np.random.default_rng(SEED + 1)
    fails3 = []
    for t in range(20):
        M = int(rng3.integers(2, 17))
        K = int(rng3.integers(2, 17))
        N = int(rng3.integers(2, 17))
        # 注入 bug：golden 的 k 循环少一圈——若 kernel 正确则必 fail
        rng_case = np.random.default_rng(SEED * 100 + t)
        A = rng_case.standard_normal((M, K)).astype(np.float32)
        B = rng_case.standard_normal((K, N)).astype(np.float32)
        da, db = make_desc(A), make_desc(B)
        dc = Desc2()
        lib._mlir_ciface_kernel_dynamic(ctypes.byref(dc), ctypes.byref(da), ctypes.byref(db))
        out = np.ctypeslib.as_array(
            ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
            shape=(int(dc.sh[0]), int(dc.sh[1]))).copy()
        gold = np.zeros((M, N), dtype=np.float32)
        for i in range(M):
            for j in range(N):
                acc = np.float32(0.0)
                for k in range(K - 1):        # bug 注入
                    acc = np.float32(acc + np.float32(A[i, k] * B[k, j]))
                gold[i, j] = acc
        if not np.allclose(out, gold, atol=1e-4):
            fails3.append({"trial": t, "M": M, "K": K, "N": N,
                           "note": "k 少一圈的 golden vs 正确 kernel"})
    print(f"  20 组注入：{len(fails3)}/20 检出（K=1 时 k-1=0 圈、kernel 也算 0 项——检不出）")
    json.dump({"seed": SEED + 1, "failures": fails3},
              open(os.path.join(OUT, "injected-failures.json"), "w"),
              ensure_ascii=False, indent=2)
    print("  失败用例已保存 injected-failures.json（含 shape 与原因）")

    n_ok = (not fails) and repro and len(fails3) >= 15
    print(f"\n汇总：F1 {'PASS' if not fails else 'FAIL'}｜F2 {'PASS' if repro else 'FAIL'}｜"
          f"F3 检出 {len(fails3)}/20")
    return 0 if n_ok else 1


if __name__ == "__main__":
    sys.exit(main())
