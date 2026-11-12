#!/usr/bin/env python3
"""test_dynamic.py —— 第 61 天独立验收测试：动态 Shape 表示与约束。

分五段验收：
  A. 表示基础：int / Sym / None 三档的构造、相等、非法输入
  B. MatMul 推导：判定表 15 组（含错误口径）
  C. 约束三档：bindings / renames / runtime + 图级冲突 + 特化替换
  D. 运行期模拟：合法放行、违规拦截、无检查滑过、numpy 对拍
  E. 压力与 IR：随机 300 组零崩溃；8 房间 IR 文本可被 mlir-opt 验证（若可用）

运行: python3 test_dynamic.py
"""

from __future__ import annotations

import random
import shutil
import subprocess
import sys

import numpy as np

from dynamic_lab import (Constraints, RuntimeShapeError, ShapeError, Sym,
                          check_runtime, clean_shape, fuzz, gen_test_ir,
                          ir_tensor, matmul_shape, materialize, rand_arr,
                          simulate, specialize)

PASS = [0, 0]


def ok(name, cond, detail=""):
    PASS[1] += 1
    PASS[0] += bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f"  ({detail})" if detail and not cond else ""))


def s(n):
    return Sym(n)


# ============================================================
# A. 表示基础
# ============================================================

def section_a():
    print("=== A. 表示基础 ===")
    ok("A1 Sym 同名相等", s("k") == s("k") and not (s("k") == s("j")))
    ok("A2 Sym 可哈希（能当 dict 键）", len({s("k"), s("k"), s("j")}) == 2)
    ok("A3 Sym 无名字报错",
       _raises(lambda: Sym(""), ShapeError))
    ok("A4 -1 是非法维度不是未知",
       _raises(lambda: clean_shape((2, -1)), ShapeError,
               "negative dimensions"))
    ok("A5 布尔维度被拒", _raises(lambda: clean_shape((True, 2)), ShapeError))
    ok("A6 字符串维度被拒", _raises(lambda: clean_shape(("2", 3)), ShapeError))
    ok("A7 None/Sym/自然数都合法",
       clean_shape((None, s("k"), 3, 0)) == (None, s("k"), 3, 0))


def _raises(fn, exc_type, needle=None):
    try:
        fn()
        return False
    except exc_type as e:
        return needle is None or needle in str(e)


# ============================================================
# B. MatMul 推导判定
# ============================================================

B_CASES = [
    # (名称, A, B, 输出, 绑定, 改名, 运行期)
    ("B1  全静态", (2, 3), (3, 2), (2, 2), {}, {}, []),
    ("B2  M 未知", (None, 3), (3, 2), (None, 2), {}, {}, []),
    ("B3  N 未知", (2, 3), (3, None), (2, None), {}, {}, []),
    ("B4  K 未知对静态", (2, None), (3, 2), (2, 2), {}, {},
     ["dim(A,1) == dim(B,0)"]),
    ("B5  K 双未知", (None, None), (None, None), (None, None), {}, {},
     ["dim(A,1) == dim(B,0)"]),
    ("B6  M 符号", (s("m"), 3), (3, 2), (s("m"), 2), {}, {}, []),
    ("B7  N 符号", (2, 3), (3, s("n")), (2, s("n")), {}, {}, []),
    ("B8  K 符号绑定", (2, s("k")), (3, 2), (2, 2), {"k": 3}, {}, []),
    ("B9  K 符号绑定（对侧）", (2, 3), (s("k"), 2), (2, 2), {"k": 3}, {}, []),
    ("B10 K 双符号同名", (s("m"), s("k")), (s("k"), 2), (s("m"), 2),
     {}, {}, []),
    ("B11 K 双符号异名", (2, s("k1")), (s("k2"), 2), (2, 2),
     {}, {"k2": "k1"}, []),
    ("B12 K 未知对符号", (2, None), (s("k"), 2), (2, 2), {}, {},
     ["dim(A,1) == dim(B,0)"]),
    ("B13 M 符号 + K 未知", (s("m"), None), (None, s("n")), (s("m"), s("n")),
     {}, {}, ["dim(A,1) == dim(B,0)"]),
]


def section_b():
    print("=== B. MatMul 推导判定 ===")
    for name, a, b, w_out, w_bind, w_ren, w_rt in B_CASES:
        out, ctx = matmul_shape(a, b)
        ok(name,
           out == w_out and ctx.bindings == w_bind
           and ctx.renames == w_ren and ctx.runtime == w_rt,
           f"得到 {out!r} / {ctx}")
    ok("B14 秩错误：一维 × 二维",
       _raises(lambda: matmul_shape((3,), (3, 2)), ShapeError, "二维"))
    ok("B15 静态 K 失配被拒",
       _raises(lambda: matmul_shape((2, 3), (4, 2)), ShapeError, "K 对不上"))


# ============================================================
# C. 约束三档与特化
# ============================================================

def section_c():
    print("=== C. 约束三档与特化 ===")
    out, ctx = matmul_shape((2, s("k")), (3, 2))
    ok("C1 绑定可特化", specialize(out, ctx.bindings, ctx.renames) == (2, 2))

    out, ctx = matmul_shape((s("M"), s("k1")), (s("k2"), 5))
    ok("C2 改名保留未绑定符号",
       specialize(out, ctx.bindings, ctx.renames) == (s("M"), 5))

    graph = Constraints()
    matmul_shape((2, s("k")), (3, 2), ctx=graph)
    ok("C3 图级绑定：先 3 后 4 冲突",
       _raises(lambda: matmul_shape((2, s("k")), (4, 2), ctx=graph),
               ShapeError, "已绑定 3"))
    ok("C4 图级绑定：同值不冲突",
       _not_raises(lambda: matmul_shape((2, s("k")), (3, 2), ctx=graph)))

    graph2 = Constraints()
    out1, _ = matmul_shape((s("m"), s("k")), (s("k"), s("n")), ctx=graph2)
    out2, _ = matmul_shape(out1, (out1[1], 4), ctx=graph2)
    ok("C5 链式推导：符号沿图传播", (out1, out2) == ((s("m"), s("n")),
                                                   (s("m"), 4)))

    ok("C6 renames 解析到底", _resolve_chain())


def _not_raises(fn):
    try:
        fn()
        return True
    except Exception:
        return False


def _resolve_chain():
    c = Constraints()
    c.rename("c", "b")
    c.rename("b", "a")
    return c.resolve(Sym("c")) == Sym("a")


# ============================================================
# D. 运行期模拟
# ============================================================

def section_d():
    print("=== D. 运行期模拟 ===")
    rng = random.Random(615)

    out, _, _ = simulate((2, None), (None, 2), rng, checked=True,
                         a_real=(2, 3), b_real=(3, 2))
    ok("D1 合法动态输入放行且输出 (2,2)", out == (2, 2))

    ok("D2 K 失配被运行期拦下",
       _raises(lambda: simulate((2, None), (None, 2), rng, checked=True,
                                a_real=(2, 3), b_real=(5, 2)),
               RuntimeShapeError, "dim(A,1) == dim(B,0)"))

    out, res, (ar, br) = simulate((2, None), (None, 2), rng, checked=False,
                                  a_real=(2, 3), b_real=(5, 2))
    ok("D3 无检查时同样数据静默算完", out == (2, 2) and br == (5, 2))

    out, res, _ = simulate((None, 3), (3, None), rng, checked=True,
                           a_real=(4, 3), b_real=(3, 7))
    ok("D4 M/N 动态维运行期回填", out == (4, 7))

    # numpy 对拍：同一份随机数据，模拟 vs 参考实现
    same = True
    for seed in range(1, 6):
        r = random.Random(seed)
        env = {}
        a_real = materialize((None, 3), env, r)
        b_real = materialize((3, None), env, r)
        av, bv = rand_arr(r, a_real), rand_arr(r, b_real)
        want = np.matmul(av, bv)
        got_out, got, _ = simulate((None, 3), (3, None), r, checked=True,
                                  a_real=a_real, b_real=b_real, env=env,
                                  data=(av, bv))
        same &= got_out == want.shape and np.allclose(got, want)
    ok("D5 numpy 对拍 5 组逐位一致", same)

    # 符号场景：?m 出现在两处，运行期必须同值
    env = {}
    a_real = materialize((s("m"), 3), env, random.Random(9))
    b_real = materialize((3, s("m")), env, random.Random(9))
    ok("D6 同名符号同一值", a_real[0] == b_real[1] and env["m"] == a_real[0])


# ============================================================
# E. 压力与 IR
# ============================================================

def section_e():
    print("=== E. 压力与 IR ===")
    stats = fuzz(300, 61)
    ok("E1 300 组零崩溃", stats["other_exception"] == 0
       and stats["bad_result"] == 0
       and sum(stats.values()) == 300)
    ok("E2 ok + error = 300", stats["ok"] + stats["shape_error"] == 300)

    ir = gen_test_ir()
    ok("E3 8 房间", ir.count("func.func @room_") == 8)
    ok("E4 函数名不含 ?", "?_" not in ir and "N?" not in ir)
    ok("E5 K 全静态房间无 ?",
       "room_0_M2_K3_N2(%a: tensor<2x3xf32>" in ir)
    ok("E6 全动态房间输出 ?x?xf32",
       "room_7_Mdyn_Kdyn_Ndyn(%a: tensor<?x?xf32>" in ir)

    mlir_opt = shutil.which("mlir-opt") or "/usr/lib/llvm-18/bin/mlir-opt"
    if not shutil.which(mlir_opt):
        print("  [SKIP] mlir-opt 不可用，跳过 IR 实测（run_all.sh 里有完整版）")
        return
    with open("generated_dynamic_tests.mlir", "w", encoding="utf-8") as f:
        f.write(ir)
    r = subprocess.run([mlir_opt, "generated_dynamic_tests.mlir"],
                       capture_output=True, text=True)
    ok("E7 mlir-opt 解析+验证 8 房间通过", r.returncode == 0,
       r.stderr[:200])


def main():
    section_a()
    section_b()
    section_c()
    section_d()
    section_e()
    print(f"\ntest_dynamic: {PASS[0]}/{PASS[1]}")
    if PASS[0] != PASS[1]:
        sys.exit(1)


if __name__ == "__main__":
    main()
