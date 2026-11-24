#!/usr/bin/env python3
"""products_lab.py —— 第 62 天：特化的收益、产物数量与通用回退（全部实测）。

四段实验：
  1. 特化一份的收益：matmul_dyn.mlir vs 特化产物（memref.dim 计数、
     可完全展开性、代码体积——降 scf 循环 / 降 affine 循环 + full-unroll）。
  2. 产物数量与编译时间：12 次调用的 batch 轨迹（5 个不同 M），
     每个不同 Shape 特化一份产物，实测每份的编译耗时与体积；
     通用版只编译一份。代价 = 产物数 × 编译时间。
  3. 分发模拟：全通用 / miss 时 JIT / 预编译三种策略，
     用第 2 段的实测编译时间做推演（只推演次数与耗时，不伪造运行时数据）。
  4. 汇总断言。

运行: python3 products_lab.py   （需要 mlir-opt；产物与数据写到 outputs/）
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from specialize import find_mlir_opt, parse_spec, specialize_ir, \
    verify_with_mlir_opt

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

CHECKS = [0, 0]


def check(name: str, cond: bool, detail: str = "") -> None:
    CHECKS[1] += 1
    CHECKS[0] += bool(cond)
    mark = "PASS" if cond else "FAIL"
    suffix = f"  ({detail})" if detail and not cond else ""
    print(f"  [{mark}] {name}{suffix}")


def run_opt(mlir_opt: str, passes: list[str], src: Path, dst: Path | None = None):
    """跑 mlir-opt；返回 (returncode, stdout 文本)。"""
    cmd = [mlir_opt] + passes + [str(src)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    text = r.stdout
    if dst is not None and r.returncode == 0:
        dst.write_text(text, encoding="utf-8")
    return r.returncode, text


def time_opt(ms: float, mlir_opt: str, passes: list[str], src: Path, reps=3):
    """实测编译耗时（中位数，毫秒）；返回 (毫秒 或 None, returncode)。"""
    times, rc = [], 1
    for _ in range(reps):
        t0 = time.perf_counter()
        r = subprocess.run([mlir_opt] + passes + [str(src)],
                           capture_output=True, text=True)
        times.append((time.perf_counter() - t0) * 1000)
        rc = r.returncode
    times.sort()
    return (times[len(times) // 2] if rc == 0 else None), rc


def count(text: str, pat: str) -> int:
    return sum(1 for line in text.splitlines() if pat in line)


def main() -> None:
    mlir_opt = find_mlir_opt()
    if mlir_opt is None:
        print("找不到 mlir-opt，products_lab 无法运行（请装 LLVM/MLIR）")
        raise SystemExit(2)
    print(f"mlir-opt: {mlir_opt}")

    dyn_src = HERE / "matmul_dyn.mlir"
    dyn_text = dyn_src.read_text(encoding="utf-8")

    # ==========================================================
    print("=== 1. 特化一份的收益：动态版 vs 特化版（IR 指标实测）===")
    spec_text, report, repls, n_subs = specialize_ir(
        dyn_text, parse_spec("a=2x3,b=3x2"))
    spec_path = OUT / "matmul_spec.mlir"
    spec_path.write_text(spec_text, encoding="utf-8")
    for line in report:
        print("  " + line)

    rc_dyn, _ = verify_with_mlir_opt(dyn_text, mlir_opt)
    rc_spec, _ = verify_with_mlir_opt(spec_text, mlir_opt)
    print(f"  重新验证：动态版 exit={rc_dyn}，特化版 exit={rc_spec}")

    rows = []
    for tag, src in (("动态版", dyn_src), ("特化版", spec_path)):
        stem = "dyn" if tag == "动态版" else "spec"
        # a) 降 scf 循环
        rc, txt = run_opt(mlir_opt, ["--convert-linalg-to-loops"], src,
                          OUT / f"{stem}_scf_loops.mlir")
        n_dim = count(txt, "memref.dim")
        n_for = count(txt, "scf.for")
        # b) 降 affine 循环 + 三次 full-unroll
        rc2, aff = run_opt(mlir_opt, ["--convert-linalg-to-affine-loops"],
                           src, OUT / f"{stem}_affine.mlir")
        aff_path = OUT / f"{stem}_affine.mlir"
        un_pass = ["--affine-loop-unroll=unroll-full"]
        cur = aff
        for i in range(3):
            p = OUT / f"{stem}_unroll{i}.mlir"
            rc3, cur = run_opt(mlir_opt, un_pass, aff_path, p)
            aff_path = p
        n_afor = count(cur, "affine.for")
        n_load = count(cur, "affine.load")
        rows.append((tag, n_dim, n_for, n_afor, n_load,
                     len(cur.splitlines()), aff_path.stat().st_size))
    print(f"  {'':<6}{'memref.dim':>11}{'scf.for':>8}{'unroll后affine.for':>19}"
          f"{'unroll后load':>13}{'行数':>6}{'字节':>8}")
    for tag, n_dim, n_for, n_afor, n_load, lines, size in rows:
        print(f"  {tag:<6}{n_dim:>11}{n_for:>8}{n_afor:>19}{n_load:>13}"
              f"{lines:>6}{size:>8}")
    (t_dyn, t_spec) = rows
    check("特化后 memref.dim 归零", t_dyn[1] == 1 and t_spec[1] == 0,
          f"{t_dyn[1]} → {t_spec[1]}")
    check("特化后循环可完全展开（动态版 M 循环卡在 %dim 上）",
          t_dyn[3] == 1 and t_spec[3] == 0, f"{t_dyn[3]} → {t_spec[3]}")
    check("语义不变的证据链：两版都通过验证，执行对拍见 dispatch.mlir",
          rc_dyn == 0 and rc_spec == 0)

    # ==========================================================
    print()
    print("=== 2. 产物数量与编译时间：12 次调用、5 个不同 batch（实测）===")
    trace = [2, 2, 4, 2, 8, 2, 4, 16, 2, 4, 2, 32]
    distinct = sorted(set(trace))
    print(f"  调用轨迹（M）：{trace}")
    print(f"  不同 M：{distinct}（{len(distinct)} 个）——"
          f"产物数量跟着「不同 Shape 数」走，不是调用次数")
    passes = ["--convert-linalg-to-loops"]
    compiles = []
    for m in distinct:
        text, _, _, _ = specialize_ir(dyn_text, parse_spec(f"a={m}x3"))
        p = OUT / f"spec_M{m}.mlir"
        p.write_text(text, encoding="utf-8")
        ms, rc = time_opt(0, mlir_opt, passes, p)
        rc_v, _ = verify_with_mlir_opt(text, mlir_opt)
        _, loops = run_opt(mlir_opt, passes, p)
        compiles.append((m, ms, rc, rc_v, count(loops, "memref.dim"),
                         p.stat().st_size))
        print(f"  特化 M={m:<3} 编译 {ms:6.1f} ms（中位数×3）  "
              f"verify exit={rc_v}  memref.dim={count(loops, 'memref.dim')}  "
              f"{p.stat().st_size} B")
    ms_generic, rc_g = time_opt(0, mlir_opt, passes, dyn_src)
    _, loops_g = run_opt(mlir_opt, passes, dyn_src, OUT / "generic_loops.mlir")
    print(f"  通用版     编译 {ms_generic:6.1f} ms（中位数×3）  "
          f"verify exit={rc_g}  memref.dim={count(loops_g, 'memref.dim')}  "
          f"{dyn_src.stat().st_size} B")
    total_spec_ms = sum(c[1] for c in compiles)
    n_products = len(distinct) + 1
    print(f"  合计：{len(distinct)} 份特化产物 + 1 份通用回退 = {n_products} 个产物；"
          f"特化编译总耗时 {total_spec_ms:.1f} ms")
    check("每个不同 M 都得到一份通过验证的产物",
          all(c[3] == 0 for c in compiles))
    check("所有特化产物 memref.dim=0，通用版=1",
          all(c[4] == 0 for c in compiles) and count(loops_g, "memref.dim") == 1)
    check("产物数 = 不同 Shape 数 + 1（通用回退）", n_products == 6)

    # ==========================================================
    print()
    print("=== 3. 分发模拟：三种策略（编译耗时用第 2 段实测值）===")
    jit = dict((c[0], c[1]) for c in compiles)
    strategies = [
        ("A 全通用（不特化）", 1, ms_generic,
         "每次调用都带 memref.dim + 运行期 K 检查"),
        ("B miss 时 JIT 特化", 1 + len(distinct), ms_generic + total_spec_ms,
         "5 次首见触发编译（延迟尖峰），7 次命中缓存"),
        ("C 预编译出现过的 Shape", 1 + len(distinct), ms_generic + total_spec_ms,
         "编译全在启动前，服务期 12 次全命中"),
    ]
    print(f"  {'策略':<22}{'编译次数':>9}{'实测编译耗时':>13}   说明")
    for name, n, ms, note in strategies:
        print(f"  {name:<22}{n:>9}{ms:>10.1f} ms   {note}")
    hits = len(trace) - len(distinct)
    print(f"  轨迹 12 次调用中：首见 {len(distinct)} 次（触发 JIT 或回退），"
          f"命中 {hits} 次")
    print("  —— 注意：M 的取值没有上界，不可能预编译「所有」Shape，")
    print("     所以任何特化系统都必须留一条通用回退路径（策略 A 的那份产物）")
    check("命中次数 = 调用次数 - 不同 Shape 数", hits == 12 - 5)
    check("JIT 与预编译编译总量相同，差别只在发生时机",
          abs(strategies[1][2] - strategies[2][2]) < 1e-9)

    # ==========================================================
    print()
    print(f"=== 4. 汇总：{CHECKS[0]}/{CHECKS[1]} ===")
    if CHECKS[0] != CHECKS[1]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
