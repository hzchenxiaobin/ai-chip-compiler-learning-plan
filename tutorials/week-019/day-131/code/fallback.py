#!/usr/bin/env python3
"""第 130 天核心模块：fallback.py——通用实现回退（三件套第三件）。

D129 的两层分发里，miss 是「没注册」——一条**正常**路径。今天的回退
（fallback）补上**异常**路径：

  回退场景 A：shape 校验失败（越界/非法）→ 拒收并诊断（fail-fast）
  回退场景 B：特化 kernel 执行异常 → 降级到动态版重试（try/except）
  回退场景 C：动态版也失败 → 上抛结构化错误（E3xx 运行期诊断）

计划条目："实现简单分发：命中特化配置则使用特化版本，否则走通用版本；
产出：Shape 分发逻辑和命中／未命中测试。"——D129 已做「分发」，今天
做「未命中之后的完整故事」＋运行期检查体系。
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

# E3xx：运行期诊断（D120 的 E1xx/E2xx 之后的第三层）
RT_DIAGS = {
    "E301": "运行期 shape 校验失败：{detail}",
    "E302": "特化 kernel 执行异常，已回退动态版：{detail}",
    "E303": "动态版也失败（不可恢复）：{detail}",
    "W301": "回退发生（性能降级）：{detail}",
}


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


class RuntimeWithFallback:
    """带回退的运行期分发器：校验→特化→异常回退→上抛。

    分发链（每一级失败降一级）：
      ① shape 校验（E301 fail-fast）
      ② 特化命中？→ 特化 kernel（异常→E302 回退动态）
      ③ 动态 kernel（失败→E303 上抛）
    """

    def __init__(self, dynamic_so: str):
        self.dynamic_lib = ctypes.CDLL(dynamic_so)
        self.dynamic_lib._mlir_ciface_kernel_dynamic.restype = None
        self.dynamic_lib._mlir_ciface_kernel_dynamic.argtypes = [ctypes.POINTER(Desc2)] * 3
        self.specialized: dict = {}
        self.stats = {"hit": 0, "miss": 0, "fallback": 0, "rejected": 0}
        self.events: list = []        # 运行期事件日志（回退的可观测性）

    def register(self, shape, so_path, func_name):
        if shape in self.specialized:
            return
        lib = ctypes.CDLL(so_path)
        f = getattr(lib, func_name)
        f.restype = None
        f.argtypes = [ctypes.POINTER(Desc2)] * 3
        self.specialized[shape] = (lib, f)

    # ── ① shape 校验（运行期检查——D128 实验 C 指出的缺口） ──
    def _validate(self, A, B):
        if A.ndim != 2 or B.ndim != 2:
            raise RtError("E301", f"A.ndim={A.ndim}, B.ndim={B.ndim}（只支持 2D）")
        if A.shape[1] != B.shape[0]:
            raise RtError("E301", f"内维不匹配 {A.shape[1]}≠{B.shape[0]}")
        if A.dtype != np.float32 or B.dtype != np.float32:
            raise RtError("E301", f"dtype 只支持 f32（{A.dtype}/{B.dtype}）")
        if min(A.shape[0], A.shape[1], B.shape[1]) < 1:
            raise RtError("E301", f"零维 shape {A.shape}@{B.shape}")

    def run(self, A, B):
        """分发链：校验→特化→（异常）回退动态→（失败）上抛。"""
        self._validate(A, B)                    # ① E301 fail-fast

        key = (A.shape[0], A.shape[1], B.shape[1])
        da, db = make_desc(A), make_desc(B)

        # ② 特化命中
        if key in self.specialized:
            _, f = self.specialized[key]
            dc = Desc2()
            try:
                f(ctypes.byref(dc), ctypes.byref(da), ctypes.byref(db))
                self.stats["hit"] += 1
                return self._read(dc)
            except Exception as e:
                # E302：特化失败 → 回退动态版重试
                self.stats["fallback"] += 1
                msg = RT_DIAGS["E302"].format(detail=str(e)[:80])
                self.events.append(msg)
                if not self.quiet:
                    print(f"  [W301] {RT_DIAGS['W301'].format(detail=f'{key} 特化异常→动态重试')}",
                          file=sys.stderr)
                # 落入 ③

        # ③ 动态兜底
        dc = Desc2()
        try:
            self.dynamic_lib._mlir_ciface_kernel_dynamic(
                ctypes.byref(dc), ctypes.byref(da), ctypes.byref(db))
            self.stats["miss"] += 0 if key in self.specialized else 1
            return self._read(dc)
        except Exception as e:
            # E303：不可恢复
            raise RtError("E303", f"动态版执行失败：{e}") from e

    quiet = True

    def _read(self, dc):
        return np.ctypeslib.as_array(
            ctypes.cast(dc.alloc, ctypes.POINTER(ctypes.c_float)),
            shape=(int(dc.sh[0]), int(dc.sh[1]))).copy()


class RtError(Exception):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(f"{code} {RT_DIAGS[code].format(detail=detail)}")


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(130)

    # 复用 D129 的产物
    dyn_so = os.path.join(OUT, "e2-dynamic", "libdyn.dylib")
    spec_so = os.path.join(OUT, "spec-4x6x3", "libkernel.dylib")
    if not os.path.exists(dyn_so):
        # 重建（invoke D128/129 的构建器）
        from dyn_shape import DYNAMIC_IR, run_pipeline
        r = run_pipeline(DYNAMIC_IR, "e2-dynamic")
        obj = os.path.join(OUT, "e2-dynamic", "dyn.o")
        subprocess.run([f"{LLVM}/llc", r["ll"], "-filetype=obj",
                        "-relocation-model=pic", "-o", obj], check=True)
        subprocess.run([f"{LLVM}/clang", "-shared", "-undefined",
                        "dynamic_lookup", obj, "-o", dyn_so], check=True)
        os.remove(obj)
    if not os.path.exists(spec_so):
        from specialize import build_kernel, gen_static_ir
        build_kernel(gen_static_ir(4, 6, 3), "spec-4x6x3", opt_o2=True)
        spec_so = os.path.join(OUT, "spec-4x6x3", "libkernel.dylib")

    rt = RuntimeWithFallback(dyn_so)
    rt.register((4, 6, 3), spec_so, "_mlir_ciface_kernel_s4x6x3")

    print("== E1 正常路径：命中与 miss（D129 行为保持）==")
    A1 = rng.standard_normal((4, 6)).astype(np.float32)
    B1 = rng.standard_normal((6, 3)).astype(np.float32)
    out = rt.run(A1, B1)
    ok1 = np.allclose(out, A1 @ B1, atol=1e-5)
    print(f"  4x6x3 命中特化: {'PASS' if ok1 else 'FAIL'}")
    A2 = rng.standard_normal((3, 5)).astype(np.float32)
    B2 = rng.standard_normal((5, 2)).astype(np.float32)
    out = rt.run(A2, B2)
    ok2 = np.allclose(out, A2 @ B2, atol=1e-5)
    print(f"  3x5x2 miss 动态: {'PASS' if ok2 else 'FAIL'}")

    print("\n== E2 校验路径：非法输入的 fail-fast（E301）==")
    bad_cases = [
        ("内维不匹配", lambda: rt.run(np.zeros((4, 5), np.float32),
                                        np.zeros((6, 3), np.float32))),
        ("dtype 非法", lambda: rt.run(np.zeros((4, 6), np.float64),
                                       np.zeros((6, 3), np.float64))),
        ("3D 输入", lambda: rt.run(np.zeros((2, 4, 6), np.float32),
                                    np.zeros((6, 3), np.float32))),
        ("零维", lambda: rt.run(np.zeros((0, 6), np.float32),
                                 np.zeros((6, 3), np.float32))),
    ]
    n_reject = 0
    for name, fn in bad_cases:
        try:
            fn()
            print(f"  {name}: FAIL（未拒收！）")
        except RtError as e:
            assert e.code == "E301"
            n_reject += 1
            print(f"  {name}: 拒收 ✓（E301: {e.detail[:40]}）")
    print(f"  四种非法输入全部 fail-fast（rejected={n_reject}）")

    print("\n== E3 回退路径：特化异常→动态重试（E302→W301）==")
    # 人为破坏特化 kernel：注册一个会崩的（用错误的函数地址模拟）
    class BombLib:
        """模拟执行异常的特化层。"""
        def __call__(self, *args):
            raise RuntimeError("模拟：特化 kernel 段错误")

    rt2 = RuntimeWithFallback(dyn_so)
    rt2.specialized[(4, 6, 3)] = (None, BombLib())    # 注入坏 kernel
    out = rt2.run(A1, B1)
    ok3 = np.allclose(out, A1 @ B1, atol=1e-5)
    print(f"  特化崩溃→动态重试: {'PASS（回退成功）' if ok3 else 'FAIL'}")
    print(f"  统计: {rt2.stats}")
    print(f"  事件: {rt2.events[0][:60] if rt2.events else '(无)'}")

    print("\n== E4 不可恢复路径：动态版也失败（E303 上抛）==")
    class BombDynamic:
        def __call__(self, *args):
            raise RuntimeError("模拟：动态版也崩了")

    rt3 = RuntimeWithFallback(dyn_so)
    rt3.dynamic_lib._mlir_ciface_kernel_dynamic = BombDynamic()
    try:
        rt3.run(A1, B1)
        print("  FAIL（未上抛！）")
    except RtError as e:
        assert e.code == "E303"
        print(f"  两层全崩→上抛 E303: {e.detail[:50]} ✓")

    assert ok1 and ok2 and ok3 and n_reject == 4
    print("\n四条路径全通：正常（hit/miss）→校验（E301）→回退（E302/W301）→上抛（E303）")
    print("三件套齐了：特化（D129）＋缓存（D129 E3）＋回退（今天）")


if __name__ == "__main__":
    main()
