#!/usr/bin/env python3
"""第 129 天核心模块：specialize.py——静态 Shape 特化＋运行期分发。

D128 证明了动态签名的代价（优化空间收缩：O2 敢展开 fmul 1→6 vs 动态
只到 2）。今天的答案是「两层分发」：

  通用层（动态 kernel）：任何 shape 都能跑——正确性兜底
  特化层（静态 kernel）：为热点 shape 编译专用版——性能主攻
  分发器（Dispatch）  ：运行期按 shape 选层

三个子实验：
  E1 特化收益实测   同一 shape 下静态 vs 动态 kernel 的 O2 差距
  E2 分发器实现     shape→kernel 的映射表＋miss 回退
  E3 缓存雏形       特化产物的按 shape 缓存（首次编译、后续复用）

计划条目："为两组常见 Shape 生成特化产物，并比较通用版本性能；
产出：特化产物、性能表和代码大小记录。"
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
LLVM = "/opt/homebrew/opt/llvm/bin"


# ──────────────────────────────────────────────────────────
# 特化 kernel 生成器：按 shape 生成静态签名 IR
# ──────────────────────────────────────────────────────────

def gen_static_ir(M: int, K: int, N: int) -> str:
    """生成 shape 特化的静态 kernel IR（复用 D128 的静态模板，参数化 shape）。"""
    return f"""module {{
  func.func @kernel_s{M}x{K}x{N}(%a: memref<{M}x{K}xf32, strided<[{K}, 1]>>,
                                    %b: memref<{K}x{N}xf32, strided<[{N}, 1]>>)
      -> memref<{M}x{N}xf32> attributes {{ llvm.emit_c_interface }} {{
    %c = memref.alloc() : memref<{M}x{N}xf32>
    %c0 = arith.constant 0 : index
    %cM = arith.constant {M} : index
    %cN = arith.constant {N} : index
    %cK = arith.constant {K} : index
    %c1 = arith.constant 1 : index
    %z = arith.constant 0.0 : f32
    scf.for %i = %c0 to %cM step %c1 {{
      scf.for %j = %c0 to %cN step %c1 {{
        %acc = scf.for %k = %c0 to %cK step %c1
                    iter_args(%acc = %z) -> (f32) {{
          %aij = memref.load %a[%i, %k] : memref<{M}x{K}xf32, strided<[{K}, 1]>>
          %bkj = memref.load %b[%k, %j] : memref<{K}x{N}xf32, strided<[{N}, 1]>>
          %p = arith.mulf %aij, %bkj : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }}
        memref.store %acc, %c[%i, %j] : memref<{M}x{N}xf32>
      }}
    }}
    func.return %c : memref<{M}x{N}xf32>
  }}
}}
"""


def build_kernel(ir_text: str, tag: str, opt_o2: bool = False) -> str:
    """IR → 共享库；返回 .dylib 路径（编译产物缓存雏形）。"""
    d = os.path.join(OUT, tag)
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "input.mlir")
    open(src, "w").write(ir_text)
    cur = src
    passes = [(["--canonicalize", "--cse"], "canon"),
              (["--convert-scf-to-cf"], "scfcf"),
              (["--finalize-memref-to-llvm"], "memref"),
              (["--convert-func-to-llvm"], "func"),
              (["--convert-cf-to-llvm"], "cf"),
              (["--convert-arith-to-llvm"], "arith"),
              (["--convert-index-to-llvm"], "index"),
              (["--reconcile-unrealized-casts"], "reconcile")]
    for i, (flags, name) in enumerate(passes):
        nxt = os.path.join(d, f"s{i}-{name}.mlir")
        subprocess.run([f"{LLVM}/mlir-opt", cur] + flags + ["-o", nxt],
                       check=True, capture_output=True)
        cur = nxt
    ll = os.path.join(d, "out.ll")
    subprocess.run([f"{LLVM}/mlir-translate", cur, "--mlir-to-llvmir", "-o", ll],
                   check=True, capture_output=True)
    if opt_o2:
        o2 = os.path.join(d, "out-O2.ll")
        subprocess.run([f"{LLVM}/opt", ll, "-O2", "-S", "-o", o2],
                       check=True, capture_output=True)
        ll = o2
    obj = os.path.join(d, "kernel.o")
    so = os.path.join(d, "libkernel.dylib")
    subprocess.run([f"{LLVM}/llc", ll, "-filetype=obj", "-relocation-model=pic",
                    "-o", obj], check=True, capture_output=True)
    subprocess.run([f"{LLVM}/clang", "-shared", "-undefined", "dynamic_lookup",
                    obj, "-o", so], check=True, capture_output=True)
    os.remove(obj)
    return so


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


def read_out(dc):
    return np.ctypeslib.as_array(
        ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
        shape=(int(dc.sh[0]), int(dc.sh[1]))).copy()


# ──────────────────────────────────────────────────────────
# E2：分发器（两层：特化层命中走专用，miss 走动态兜底）
# ──────────────────────────────────────────────────────────

class Dispatcher:
    """运行期 shape 分发器：特化表＋动态兜底＋缓存计数。"""

    def __init__(self, dynamic_so: str):
        self.dynamic_lib = ctypes.CDLL(dynamic_so)
        self.dynamic_lib._mlir_ciface_kernel_dynamic.restype = None
        self.dynamic_lib._mlir_ciface_kernel_dynamic.argtypes = [ctypes.POINTER(Desc2)] * 3
        self.specialized: dict = {}      # (M,K,N) -> (lib, func_name)
        self.stats = {"hit": 0, "miss": 0, "compiled": 0}

    def register(self, shape, so_path, func_name):
        if shape in self.specialized:
            return                      # 幂等：已注册不重复编译（E3 缓存语义）
        lib = ctypes.CDLL(so_path)
        f = getattr(lib, func_name)
        f.restype = None
        f.argtypes = [ctypes.POINTER(Desc2)] * 3
        self.specialized[shape] = (lib, f)
        self.stats["compiled"] += 1

    def run(self, A, B):
        key = (A.shape[0], A.shape[1], B.shape[1])
        da, db = make_desc(A), make_desc(B)
        dc = Desc2()
        if key in self.specialized:
            _, f = self.specialized[key]
            self.stats["hit"] += 1
        else:
            f = self.dynamic_lib._mlir_ciface_kernel_dynamic
            self.stats["miss"] += 1
        f(ctypes.byref(dc), ctypes.byref(da), ctypes.byref(db))
        return read_out(dc)


# ──────────────────────────────────────────────────────────
# 主实验
# ──────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(129)

    # ── E1 特化收益：同 shape 静态（O2）vs 动态（O2） ──
    print("== E1 特化收益：4x6x3 的静态 O2 vs 动态 O2 ==")
    static_o2 = build_kernel(gen_static_ir(4, 6, 3), "spec-4x6x3", opt_o2=True)
    # 动态版复用 D128 的产物
    dyn_so = os.path.join(HERE, "outputs", "e2-dynamic", "libdyn.dylib")
    if not os.path.exists(dyn_so):
        # 重建（D128 的 run_all 清理过）
        from dyn_shape import DYNAMIC_IR, run_pipeline
        r = run_pipeline(DYNAMIC_IR, "e2-dynamic")
        assert r["ok"]
        obj = os.path.join(OUT, "e2-dynamic", "dyn.o")
        subprocess.run([f"{LLVM}/llc", r["ll"], "-filetype=obj",
                        "-relocation-model=pic", "-o", obj], check=True)
        subprocess.run([f"{LLVM}/clang", "-shared", "-undefined",
                        "dynamic_lookup", obj, "-o", dyn_so], check=True)
        os.remove(obj)

    # 指令规模对照
    s_ll = open(os.path.join(OUT, "spec-4x6x3", "out-O2.ll")).read()
    d_ll = open(os.path.join(OUT, "e2-dynamic", "out.ll")).read()
    # 动态版也过 O2 再比
    d_o2_path = os.path.join(OUT, "e2-dynamic", "out-O2.ll")
    subprocess.run([f"{LLVM}/opt", os.path.join(OUT, "e2-dynamic", "out.ll"),
                    "-O2", "-S", "-o", d_o2_path], capture_output=True)
    d_o2 = open(d_o2_path).read()
    print(f"  静态+O2：fmul={s_ll.count('fmul')} phi={s_ll.count(' phi ')} 行={len([l for l in s_ll.splitlines() if l.strip()])}")
    print(f"  动态+O2：fmul={d_o2.count('fmul')} phi={d_o2.count(' phi ')} 行={len([l for l in d_o2.splitlines() if l.strip()])}")
    print(f"  → 特化让 O2 敢展开：fmul {d_o2.count('fmul')} → {s_ll.count('fmul')}")

    # ── E2 分发器 ──
    print("\n== E2 分发器：特化 4x6x3＋8x8x8，动态兜底 ==")
    disp = Dispatcher(dyn_so)
    disp.register((4, 6, 3), static_o2, "_mlir_ciface_kernel_s4x6x3")
    so8 = build_kernel(gen_static_ir(8, 8, 8), "spec-8x8x8", opt_o2=True)
    disp.register((8, 8, 8), so8, "_mlir_ciface_kernel_s8x8x8")

    # 命中/未命中验证
    A1 = rng.standard_normal((4, 6)).astype(np.float32)
    B1 = rng.standard_normal((6, 3)).astype(np.float32)
    out1 = disp.run(A1, B1)
    ok1 = np.allclose(out1, A1 @ B1, atol=1e-5)
    print(f"  4x6x3（命中特化）: {'PASS' if ok1 else 'FAIL'}")

    A2 = rng.standard_normal((8, 8)).astype(np.float32)
    B2 = rng.standard_normal((8, 8)).astype(np.float32)
    out2 = disp.run(A2, B2)
    ok2 = np.allclose(out2, A2 @ B2, atol=1e-5)
    print(f"  8x8x8（命中特化）: {'PASS' if ok2 else 'FAIL'}")

    A3 = rng.standard_normal((5, 7)).astype(np.float32)   # 未注册 shape
    B3 = rng.standard_normal((7, 2)).astype(np.float32)
    out3 = disp.run(A3, B3)
    ok3 = np.allclose(out3, A3 @ B3, atol=1e-5)
    print(f"  5x7x2（miss→动态兜底）: {'PASS' if ok3 else 'FAIL'}")

    print(f"  分发统计：{disp.stats}")
    print("  → 命中走特化（O2 展开）、miss 走动态（正确性兜底）——两层分发成立")

    # ── E3 缓存雏形 ──
    print("\n== E3 缓存雏形：特化产物的按 shape 复用 ==")
    # 第二次 register 同 shape 不会重编译（dict 幂等）
    n_before = disp.stats["compiled"]
    disp.register((4, 6, 3), static_o2, "_mlir_ciface_kernel_s4x6x3")
    print(f"  重复 register 4x6x3：compiled {n_before} → {disp.stats['compiled']}（幂等）")
    # 产物文件就是磁盘缓存（libkernel.dylib 按 shape 命名目录）
    sizes = {t: os.path.getsize(os.path.join(OUT, t, "libkernel.dylib"))
             for t in ("spec-4x6x3", "spec-8x8x8")}
    print(f"  特化产物大小：{sizes}（代码大小记录——计划条目要求）")

    assert ok1 and ok2 and ok3
    print("\n全链结论：特化层拿性能、动态层兜正确、分发器串两层——PyTorch 2.x 三件套的第一件")


if __name__ == "__main__":
    main()
