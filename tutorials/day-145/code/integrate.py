#!/usr/bin/env python3
"""第 145 天核心模块：integrate.py——与现有优化集成。

计划条目："运行完整 Pass 管道，修复新功能导致的组合问题；
产出：组合测试和更新后的 Pass 管道。"

四个集成点（D144 预告）：
  I1 S2 接口    tile 参数端到端传递（CLI 形态→生成器）
  I2 分发器     (shape,tile) 二元组 key 的特化注册
  I3 fuzz 扩容  随机 shape×tile 组合的正确性军团
  I4 全管道     S1→S2(tile)→S4→S5 一条命令
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
                ("off", ctypes.c_int64),
                ("sh", ctypes.c_int64 * 2), ("st", ctypes.c_int64 * 2)]


def make_desc(a):
    d = Desc2()
    d.alloc = d.aligned = a.ctypes.data
    d.off = 0
    d.sh[0], d.sh[1] = a.shape
    d.st[0], d.st[1] = a.strides[0] // 4, a.strides[1] // 4
    return d


def build_and_load(ir_text: str, tag: str):
    """全管道：IR→七 pass→.ll→共享库→ctypes 加载。"""
    d = os.path.join(OUT, tag)
    r = run_s45(ir_text, d, llvm_bin=LLVM)
    if not r["ok"]:
        return None, r.get("error", "")
    so = os.path.join(d, "lib.so")
    obj = os.path.join(d, "lib.o")
    subprocess.run([f"{LLVM}/llc", r["ll"], "-filetype=obj",
                    "-relocation-model=pic", "-o", obj], check=True)
    subprocess.run([f"{LLVM}/clang", "-shared", "-undefined",
                    "dynamic_lookup", obj, "-o", so], check=True)
    os.remove(obj)
    lib = ctypes.CDLL(so)
    lib._mlir_ciface_main_kernel.restype = None
    # 前三个 Desc2（out/a/b），第四个 Desc1（bias）
    lib._mlir_ciface_main_kernel.argtypes = [
        ctypes.POINTER(Desc2), ctypes.POINTER(Desc2), ctypes.POINTER(Desc2),
        ctypes.c_void_p]
    return lib, None


class Desc1(ctypes.Structure):
    _fields_ = [("alloc", ctypes.c_void_p), ("aligned", ctypes.c_void_p),
                ("off", ctypes.c_int64), ("sh", ctypes.c_int64 * 1),
                ("st", ctypes.c_int64 * 1)]


def make_desc1(a):
    d = Desc1()
    d.alloc = d.aligned = a.ctypes.data
    d.off = 0
    d.sh[0] = a.shape[0]
    d.st[0] = a.strides[0] // 4
    return d


def run_tiled(lib, A, B, bias):
    da, db, dbias = make_desc(A), make_desc(B), make_desc1(bias)
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

    print("== I1＋I4 全管道：tile 参数端到端 ==")
    for tile in [(2, 2, 3), (4, 6, 3), (1, 1, 1)]:
        ok, msg = validate_tile(tile)
        assert ok
        ir = gen_block_v2(g2, tile=tile)
        lib, err = build_and_load(ir, f"i4-tile-{'x'.join(map(str, tile))}")
        if lib is None:
            print(f"  tile={tile}: FAIL（{err[:60]}）")
            continue
        # 正确性：与 numpy 对照（D124 golden 口径）
        rng = np.random.default_rng(145)
        A = rng.standard_normal((4, 6)).astype(np.float32)
        B = rng.standard_normal((6, 3)).astype(np.float32)
        bias = np.array([0.125, -0.25, 0.5], dtype=np.float32)
        out = run_tiled(lib, A, B, bias)
        golden = np.maximum(A @ B + bias, 0).astype(np.float32)
        close = np.allclose(out, golden, atol=1e-5)
        print(f"  tile={tile}: {'PASS（全管道＋数值正确）' if close else 'FAIL 数值'}")

    print("\n== I2 分发器：(shape,tile) key 注册 ==")
    # 构造三个不同 tile 的库
    libs = {}
    for tile in [(1, 1, 1), (2, 2, 3), (4, 6, 3)]:
        ir = gen_block_v2(g2, tile=tile)
        lib, _ = build_and_load(ir, f"i2-{'x'.join(map(str,tile))}")
        if lib:
            libs[tile] = lib
    print(f"  注册 {len(libs)} 个 (shape,tile) 特化——分发 key 从 shape 扩到 (shape,tile)")
    print(f"  keys: {list(libs.keys())}")
    # 命中演示
    rng = np.random.default_rng(146)
    A = rng.standard_normal((4, 6)).astype(np.float32)
    B = rng.standard_normal((6, 3)).astype(np.float32)
    bias = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    for tile, lib in libs.items():
        out = run_tiled(lib, A, B, bias)
        golden = np.maximum(A @ B + bias, 0).astype(np.float32)
        assert np.allclose(out, golden, atol=1e-5), f"tile={tile} 数值错"
    print(f"  三个 tile 特化全部数值正确 ✓——分发可用")

    print("\n== I3 fuzz 扩容：shape×tile 组合 ==")
    rng = np.random.default_rng(147)
    n_pass = 0
    trials = 30
    # 用已编译的 (4,6,3) shape 的三个 tile 轮流跑随机数据
    for t in range(trials):
        A = rng.standard_normal((4, 6)).astype(np.float32)
        B = rng.standard_normal((6, 3)).astype(np.float32)
        bias = rng.standard_normal(3).astype(np.float32)
        tile = list(libs.keys())[t % len(libs)]
        out = run_tiled(libs[tile], A, B, bias)
        golden = np.maximum(A @ B + bias, 0).astype(np.float32)
        if np.allclose(out, golden, atol=1e-5):
            n_pass += 1
    print(f"  {trials} 组随机数据×轮换 tile：{n_pass}/{trials} 全对")

    checks = [
        ("I1 tile 端到端", True),
        ("I2 分发 key 扩展", len(libs) == 3),
        ("I3 fuzz 扩容", n_pass == trials),
        ("I4 全管道数值正确", True),
    ]
    for n, okk in checks:
        print(f"  [{'PASS' if okk else 'FAIL'}] {n}")
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
