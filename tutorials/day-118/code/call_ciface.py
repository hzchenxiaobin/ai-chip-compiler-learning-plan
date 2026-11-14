# 第 118 天路线 2：AOT 共享库 + ctypes 调用（进程外编译、进程内执行）
# 与 D116 的 ctypes 驱动一脉相承，但这次 .ll 来自真实 mlir-translate（D117 冻结），
# 库由 llc -filetype=obj + clang -shared 真实编译。
# C 合同（D115/D116/D117 三天共同的约定）：
#   void _mlir_ciface_gemm(desc_t* out, desc_t* a, desc_t* b)
#   desc_t = { float* alloc; float* aligned; i64 off; i64 sh[2]; i64 st[2]; }  // 56B
import ctypes
import sys

import numpy as np


class Desc(ctypes.Structure):
    _fields_ = [("alloc", ctypes.c_void_p),
                ("aligned", ctypes.c_void_p),
                ("off", ctypes.c_int64),
                ("sh", ctypes.c_int64 * 2),
                ("st", ctypes.c_int64 * 2)]


def make_desc(arr):
    """numpy 数组 -> 描述符（行主序、无偏移、无对齐差异）"""
    a = np.ascontiguousarray(arr)
    d = Desc()
    d.alloc = d.aligned = a.ctypes.data
    d.off = 0
    d.sh[0], d.sh[1] = a.shape
    d.st[0], d.st[1] = a.strides[0] // a.itemsize, a.strides[1] // a.itemsize
    return d, a  # 返回 a 防止 GC


def main(lib_path):
    lib = ctypes.CDLL(lib_path)
    ciface = lib._mlir_ciface_gemm
    ciface.restype = None
    ciface.argtypes = [ctypes.POINTER(Desc)] * 3

    A = np.array([[0.5, -1.0, 2.0, 0.0, 1.5, -0.5],
                  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                  [-2.0, 0.5, 0.0, 3.0, -1.0, 2.0],
                  [0.0, 0.0, 0.5, 0.5, 0.5, 0.5]], dtype=np.float32)
    B = np.array([[1.0, 2.0, 3.0],
                  [4.0, 5.0, 6.0],
                  [7.0, 8.0, 9.0],
                  [10.0, 11.0, 12.0],
                  [13.0, 14.0, 15.0],
                  [16.0, 17.0, 18.0]], dtype=np.float32)
    golden = A @ B

    for round_no in (1, 2):
        da, keep_a = make_desc(A)
        db, keep_b = make_desc(B)
        dc = Desc()
        ciface(ctypes.byref(dc), ctypes.byref(da), ctypes.byref(db))
        out = np.ctypeslib.as_array(
            ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
            shape=(12,)).reshape(4, 3).copy()
        same = np.array_equal(out, golden)   # bitwise
        tag = "第一轮" if round_no == 1 else "第二轮"
        print(f"{tag}: kernel 返回缓冲区 {'12/12 点 bitwise 一致' if same else '不一致!'}"
              f"（C[0][1]={out[0, 1]:.2f} vs golden {golden[0, 1]:.2f}）")
        if not same:
            sys.exit(1)
    print("同一进程两轮调用均 12/12：kernel 无状态、可复用")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "outputs/libgemm.dylib")
