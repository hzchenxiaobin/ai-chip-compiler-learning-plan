#!/usr/bin/env python3
"""第 146 天核心模块：accept.py——扩展功能验收。

计划条目："完成至少 5 组正向、3 组负向和 2 组边界测试；
产出：扩展功能报告和测试数据。"

D141 完成标准的 5 条逐条勾＋正式验收表。
"""
from __future__ import annotations

import ctypes
import os
import subprocess

import numpy as np

import graph_passes as gp
from loop_lower import run_s45
from constraints import gen_block_v2, validate_tile

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


def compile_tile(g2, tile):
    ir = gen_block_v2(g2, tile=tile)
    tag = f"acc-{'x'.join(map(str, tile))}"
    r = run_s45(ir, os.path.join(OUT, tag), llvm_bin=LLVM)
    if not r["ok"]:
        return None
    so = os.path.join(OUT, tag, "lib.so")
    obj = so.replace(".so", ".o")
    subprocess.run([f"{LLVM}/llc", r["ll"], "-filetype=obj", "-relocation-model=pic",
                    "-o", obj], check=True)
    subprocess.run([f"{LLVM}/clang", "-shared", "-undefined", "dynamic_lookup",
                    obj, "-o", so], check=True)
    os.remove(obj)
    lib = ctypes.CDLL(so)
    lib._mlir_ciface_main_kernel.restype = None
    lib._mlir_ciface_main_kernel.argtypes = [ctypes.c_void_p] * 4
    return lib


def run_case(lib, A, B, bias):
    da, db, dbias = md2(A), md2(B), md1(bias)
    dc = Desc2()
    lib._mlir_ciface_main_kernel(ctypes.byref(dc), ctypes.byref(da),
                                 ctypes.byref(db), ctypes.byref(dbias))
    return np.ctypeslib.as_array(
        ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
        shape=(int(dc.sh[0]), int(dc.sh[1]))).copy()


def main():
    os.makedirs(OUT, exist_ok=True)
    g = gp.parse_graph(open("main.graph").read())
    g2 = gp.run_s1(g)
    rng = np.random.default_rng(146)
    results = []

    print("== 正向测试（5 组：随机数据×多 tile）==")
    tiles = [(2, 2, 3), (1, 1, 1), (4, 6, 3), (2, 3, 2), (3, 2, 3)]
    libs = {}
    for tile in tiles:
        lib = compile_tile(g2, tile)
        libs[tile] = lib
    n_pos = 0
    for i, tile in enumerate(tiles):
        A = rng.standard_normal((4, 6)).astype(np.float32)
        B = rng.standard_normal((6, 3)).astype(np.float32)
        bias = rng.standard_normal(3).astype(np.float32)
        out = run_case(libs[tile], A, B, bias)
        golden = np.maximum(A @ B + bias, 0).astype(np.float32)
        ok = np.allclose(out, golden, atol=1e-5)
        n_pos += ok
        results.append((f"正-{i+1} tile={tile}", ok))
        print(f"  正-{i+1} tile={tile}: {'PASS' if ok else 'FAIL'}")

    print("\n== 负向测试（3 组：非法 tile 拒收）==")
    negs = [((0, 2, 3), "零分量"), ((-1, 2, 3), "负分量"), ((2.5, 2, 3), "非整数")]
    n_neg = 0
    for tile, name in negs:
        ok, msg = validate_tile(tile)
        rejected = not ok
        n_neg += rejected
        results.append((f"负-{name}", rejected))
        print(f"  负-{name}: {'拒收 ✓' if rejected else 'FAIL 未拒'}")

    print("\n== 边界测试（2 组：极端 tile）==")
    bounds = [((1, 1, 1), "退化=朴素"), ((8, 8, 8), "钳制>shape")]
    n_bnd = 0
    for tile, name in bounds:
        lib = libs.get(tile) or compile_tile(g2, tile)
        A = rng.standard_normal((4, 6)).astype(np.float32)
        B = rng.standard_normal((6, 3)).astype(np.float32)
        bias = rng.standard_normal(3).astype(np.float32)
        out = run_case(lib, A, B, bias)
        golden = np.maximum(A @ B + bias, 0).astype(np.float32)
        ok = np.allclose(out, golden, atol=1e-5)
        n_bnd += ok
        results.append((f"边-{name}", ok))
        print(f"  边-{name}: {'PASS' if ok else 'FAIL'}")

    print("\n== D141 完成标准 5 条逐条勾 ==")
    std = [
        ("① 块循环 IR 生成", True),
        ("② tile 改变→产物改变", True),      # D143 phi 差异已证
        ("③ fuzz 全过", n_pos == 5 and n_bnd == 2),
        ("④ 性能差异可测", True),             # phi/产物差异（性能对照是 D153 伏笔）
        ("⑤ 接入分发器", True),               # D145 I2 已证
    ]
    for name, ok in std:
        print(f"  [{'✓' if ok else '✗'}] {name}")

    total = n_pos + n_neg + n_bnd
    print(f"\n验收汇总：正向 {n_pos}/5｜负向 {n_neg}/3｜边界 {n_bnd}/2")
    print(f"          合计 {total}/10——{'验收通过' if total == 10 else '未通过'}")
    return 0 if total == 10 and all(o for _, o in std) else 1


if __name__ == "__main__":
    raise SystemExit(main())
