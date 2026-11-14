#!/usr/bin/env python3
"""E3：动态 kernel 的多 shape 执行验证——同一份 .ll 跑两种 shape。"""
import ctypes
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LLVM = "/opt/homebrew/opt/llvm/bin"


def build_driver():
    """编译动态 kernel 为共享库。"""
    ll = os.path.join(HERE, "outputs", "e2-dynamic", "out.ll")
    obj = os.path.join(HERE, "outputs", "e3", "dyn.o")
    so = os.path.join(HERE, "outputs", "e3", "libdyn.dylib")
    os.makedirs(os.path.dirname(so), exist_ok=True)
    subprocess.run([f"{LLVM}/llc", ll, "-filetype=obj", "-relocation-model=pic",
                    "-o", obj], check=True)
    subprocess.run([f"{LLVM}/clang", "-shared", "-undefined", "dynamic_lookup",
                    obj, "-o", so], check=True)
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


def run_shape(lib, A, B):
    golden = A @ B
    da, db = make_desc(A), make_desc(B)
    dc = Desc2()
    ciface = lib._mlir_ciface_kernel_dynamic
    ciface.restype = None
    ciface.argtypes = [ctypes.POINTER(Desc2)] * 3
    ciface(ctypes.byref(dc), ctypes.byref(da), ctypes.byref(db))
    out = np.ctypeslib.as_array(
        ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
        shape=(int(dc.sh[0]), int(dc.sh[1]))).copy()
    return out, golden


def main():
    so = build_driver()
    lib = ctypes.CDLL(so)

    # shape 1: 4x6 @ 6x3（D118 数据）
    A1 = np.array([[0.5, -1, 2, 0, 1.5, -0.5], [1, 1, 1, 1, 1, 1],
                   [-2, 0.5, 0, 3, -1, 2], [0, 0, 0.5, 0.5, 0.5, 0.5]], dtype=np.float32)
    B1 = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12],
                   [13, 14, 15], [16, 17, 18]], dtype=np.float32)
    out1, gold1 = run_shape(lib, A1, B1)
    ok1 = np.array_equal(out1, gold1)
    print(f"shape 4x6@6x3: {'PASS' if ok1 else 'FAIL'}"
          f"（C[0][1]={out1[0,1]} vs golden {gold1[0,1]}）")

    # shape 2: 3x4 @ 4x2（不同 shape 同一份 kernel！）
    A2 = np.arange(12, dtype=np.float32).reshape(3, 4)
    B2 = np.array([[1, 0], [0, 1], [1, 1], [2, 1]], dtype=np.float32)
    out2, gold2 = run_shape(lib, A2, B2)
    ok2 = np.array_equal(out2, gold2)
    print(f"shape 3x4@4x2: {'PASS' if ok2 else 'FAIL'}"
          f"（C[0][1]={out2[0,1]} vs golden {gold2[0,1]}）")

    # shape 3: 8x8 @ 8x8（再大一点）
    A3 = np.eye(8, dtype=np.float32) * 2
    B3 = np.arange(64, dtype=np.float32).reshape(8, 8)
    out3, gold3 = run_shape(lib, A3, B3)
    ok3 = np.array_equal(out3, gold3)
    print(f"shape 8x8@8x8 : {'PASS' if ok3 else 'FAIL'}"
          f"（对角×2 缩放，C[3][5]={out3[3,5]} vs golden {gold3[3,5]}）")

    assert ok1 and ok2 and ok3
    print("三组 shape 全过：一份 .ll 吃三种 shape——「运行期参数」的实现证明")


if __name__ == "__main__":
    main()
