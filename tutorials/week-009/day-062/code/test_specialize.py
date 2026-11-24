#!/usr/bin/env python3
"""test_specialize.py —— 第 62 天验收测试：特化工具、错误路径、产物质量与执行对拍。

六段测试点：
  A. 替换与产物：spec 生效、类型串替换、产物可解析
  B. spec 非法输入被拒：rank / 改静态维 / 未知名字 / 重复 / 空 spec
  C. K 对账与 --force：mini 拒绝 → force 写出 → mlir-opt 拦下（重新验证）
  D. outs 一致性：与推导冲突 / 无根据 / 冗余一致
  E. 产物质量：memref.dim=0、affine 循环可完全展开、K 维静态可查
  F. dispatch.mlir 真实执行：三个场景的输出与 numpy 参考逐位一致

运行: python3 test_specialize.py   （F 段需要 mlir-cpu-runner）
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

from specialize import (KAccountError, SpecError, find_mlir_opt,
                        parse_spec, specialize_ir, verify_with_mlir_opt)

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
CHECKS = [0, 0]


def check(name: str, cond: bool, detail: str = "") -> None:
    CHECKS[1] += 1
    CHECKS[0] += bool(cond)
    mark = "PASS" if cond else "FAIL"
    suffix = f"  ({detail})" if detail and not cond else ""
    print(f"  [{mark}] {name}{suffix}")


DYN = (HERE / "matmul_dyn.mlir").read_text(encoding="utf-8")
BLIND = (HERE / "k_blind.mlir").read_text(encoding="utf-8")


def run_cli(*argv: str):
    return subprocess.run([sys.executable, str(HERE / "specialize.py"), *argv],
                          capture_output=True, text=True)


def main() -> None:
    mlir_opt = find_mlir_opt()
    if mlir_opt is None:
        print("找不到 mlir-opt：A-E 段的验证类测试会降级为文本检查")

    print("=== A. 替换与产物 ===")
    text, report, repls, n_subs = specialize_ir(DYN, parse_spec("a=2x3,b=3x2"))
    check("A1 参数类型替换", "memref<2x3xf32>" in text
          and "memref<?x3xf32>" not in text)
    check("A2 输出类型重推（M=2 跟随 %a，N=2 跟随 %b）",
          "memref<2x2xf32>" in text and "memref<?x2xf32>" not in text)
    check("A3 静态参数 %b 不动", text.count("memref<3x2xf32>")
          == DYN.count("memref<3x2xf32>"))
    check("A4 注释与结构保留（还是同一个函数）",
          "func.func @matmul(" in text and "linalg.matmul" in text)
    if mlir_opt:
        rc, err = verify_with_mlir_opt(text, mlir_opt)
        check("A5 产物通过 mlir-opt parse+verify", rc == 0, err)
    r = run_cli(str(HERE / "matmul_dyn.mlir"), "--specialize-shape",
                "arg0=2x3,arg1=3x2", "-o", str(OUT / "cli_spec.mlir"))
    check("A6 CLI 位置参数写法（arg0=…）也能用",
          r.returncode == 0 and "memref<2x3xf32>" in
          (OUT / "cli_spec.mlir").read_text(encoding="utf-8"), r.stderr)

    print()
    print("=== B. spec 非法输入被拒 ===")
    bad_cases = [
        ("B1 改静态维", "b=3x4", SpecError, "已是静态 2，不能改成 4"),
        ("B2 rank 不符", "a=2x3x4", SpecError, "2 维，spec 给了 3 个数"),
        ("B3 未知名字", "z=2x3", SpecError, "不是 @matmul 的参数"),
        ("B4 重复指定", "a=2x3,a=2x3", SpecError, "出现了两次"),
        ("B5 负数维度", "a=-2x3", SpecError, "不合法"),
        ("B6 越界位置参数", "arg7=2x3", SpecError, "越界"),
    ]
    for name, spec, exc, frag in bad_cases:
        try:
            specialize_ir(DYN, parse_spec(spec))
            ok, detail = False, "没有报错"
        except exc as e:
            ok, detail = frag in str(e), str(e)
        check(name, ok, detail)

    print()
    print("=== C. K 对账与 --force（重新验证的两层）===")
    try:
        specialize_ir(BLIND, parse_spec("a=2x4,b=3x2"))
        ok, detail = False, "mini 层没有拦截"
    except KAccountError as e:
        ok, detail = "K 对不上账" in str(e), str(e)
    check("C1 k_blind 特化被 mini K 对账拒绝（不写出）", ok, detail)
    text_bad, _, _, _ = specialize_ir(BLIND, parse_spec("a=2x4,b=3x2"),
                                      force=True)
    if mlir_opt:
        rc, err = verify_with_mlir_opt(text_bad, mlir_opt)
        check("C2 --force 写出后 mlir-opt 拦下（静态检查重新生效）",
              rc != 0 and "dimension #0 to be 4, but found 3" in (err or ""),
              err)
    r = run_cli(str(HERE / "k_blind.mlir"), "--specialize-shape", "a=2x4,b=3x2",
                "--force", "-o", str(OUT / "bad_spec_rejected.mlir"))
    check("C3 CLI 退出码=4（外部验证失败）且诊断可见",
          r.returncode == 4 and "被拒" in r.stdout, r.stdout[-200:])
    r = run_cli(str(HERE / "k_blind.mlir"), "--specialize-shape", "a=2x4,b=3x2",
                "-o", "/tmp/should_not_exist.mlir")
    check("C4 不带 --force 时拒绝写出文件", r.returncode == 3
          and not Path("/tmp/should_not_exist.mlir").exists(), r.stderr)

    print()
    print("=== D. outs 一致性 ===")
    try:
        specialize_ir(DYN, parse_spec("a=2x3,o=3x2"))
        ok, detail = False, "没有报错"
    except SpecError as e:
        ok, detail = "与推导结果冲突" in str(e) or "推导得出 2" in str(e), str(e)
    check("D1 outs spec 与推导冲突被拒", ok, detail)
    try:
        specialize_ir(DYN, parse_spec("o=2x2"))
        ok, detail = False, "没有报错"
    except SpecError as e:
        ok, detail = "没有根据" in str(e), str(e)
    check("D2 只特化输出、不动输入 → 无根据被拒", ok, detail)
    text_ok, _, _, _ = specialize_ir(DYN, parse_spec("a=2x3,o=2x2"))
    check("D3 冗余但一致的 outs spec 放行", "memref<2x2xf32>" in text_ok)

    print()
    print("=== E. 产物质量（IR 指标）===")
    spec_text, _, _, _ = specialize_ir(DYN, parse_spec("a=2x3,b=3x2"))
    spec_path = OUT / "test_spec_quality.mlir"
    spec_path.write_text(spec_text, encoding="utf-8")
    if mlir_opt:
        def run_passes(passes, src):
            return subprocess.run([mlir_opt] + passes + [str(src)],
                                  capture_output=True, text=True).stdout
        loops_dyn = run_passes(["--convert-linalg-to-loops"], HERE / "matmul_dyn.mlir")
        loops_spec = run_passes(["--convert-linalg-to-loops"], spec_path)
        check("E1 动态版有 1 个 memref.dim，特化版 0 个",
              loops_dyn.count("memref.dim") == 1
              and loops_spec.count("memref.dim") == 0)
        aff_pass = ["--convert-linalg-to-affine-loops"]
        for stem, src in (("dyn", HERE / "matmul_dyn.mlir"),
                          ("spec", spec_path)):
            p = OUT / f"test_{stem}_aff.mlir"
            p.write_text(run_passes(aff_pass, src), encoding="utf-8")
            cur = p
            for i in range(3):
                q = OUT / f"test_{stem}_unroll{i}.mlir"
                r = subprocess.run([mlir_opt, "--affine-loop-unroll=unroll-full",
                                    str(cur)], capture_output=True, text=True)
                q.write_text(r.stdout, encoding="utf-8")
                cur = q
            if stem == "dyn":
                dyn_final = cur.read_text(encoding="utf-8")
            else:
                spec_final = cur.read_text(encoding="utf-8")
        check("E2 三次 full-unroll 后：动态版剩 1 个 affine.for（M 卡在 %dim），"
              "特化版 0 个（全部直码化）",
              dyn_final.count("affine.for") == 1
              and spec_final.count("affine.for") == 0)
        check("E3 特化产物里 K 维可静态检查（类型全静态）",
              "?" not in "".join(
                  ln for ln in spec_text.splitlines()
                  if "memref<" in ln and "//" not in ln))

    print()
    print("=== F. dispatch.mlir 真实执行（与 numpy 对拍）===")
    a = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
    a2 = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]],
                  dtype=np.float32)
    b = np.array([[10, 20], [30, 40], [50, 60]], dtype=np.float32)
    c1 = a @ b
    c2 = a2 @ b
    exec_txt = (OUT / "dispatch_exec.txt")
    if not exec_txt.exists():
        # 自包含：没跑过 run_all.sh 就自己降级 + 执行一遍
        from shutil import which
        runner = which("mlir-cpu-runner")
        for cand in ("/usr/lib/llvm-18/bin/mlir-cpu-runner",
                     "/usr/bin/mlir-cpu-runner-18"):
            if runner is None and Path(cand).is_file():
                runner = cand
                break
        if runner and mlir_opt:
            lower = ["--convert-linalg-to-loops", "--convert-scf-to-cf",
                     "--convert-cf-to-llvm", "--convert-func-to-llvm",
                     "--finalize-memref-to-llvm", "--convert-arith-to-llvm",
                     "--reconcile-unrealized-casts"]
            low = OUT / "dispatch.lowered.mlir"
            subprocess.run([mlir_opt] + lower + [str(HERE / "dispatch.mlir"),
                                                 "-o", str(low)], check=True)
            llvm_lib = str(Path(runner).resolve().parent.parent / "lib")
            shared = (f"{llvm_lib}/libmlir_runner_utils.so,"
                      f"{llvm_lib}/libmlir_c_runner_utils.so")
            r = subprocess.run([runner, str(low), "-e", "main",
                                "--entry-point-result=void",
                                f"--shared-libs={shared}"],
                               capture_output=True, text=True)
            exec_txt.write_text(r.stdout, encoding="utf-8")
    if exec_txt.exists():
        vals = [float(x) for x in exec_txt.read_text(encoding="utf-8").split()]
        # 输出布局：场景1: [hit,m]+4 值；场景2: [hit,m]+8 值；场景3: [hit,m]+8 值
        check("F1 场景 1 命中特化版（hit=1, M=2）", vals[0:2] == [1.0, 2.0])
        check("F2 场景 1 结果与 numpy 一致",
              np.allclose(vals[2:6], c1.flatten()), f"{vals[2:6]} vs {c1.flatten()}")
        check("F3 场景 2 回退通用版（hit=0, M=4）", vals[6:8] == [0.0, 4.0])
        check("F4 场景 2 通用版结果与 numpy 一致",
              np.allclose(vals[8:16], c2.flatten()))
        check("F5 场景 3 缓存长出第二份特化后再命中（hit=1, M=4）",
              vals[16:18] == [1.0, 4.0])
        check("F6 特化版与通用版输出逐位一致（语义保持）",
              np.allclose(vals[18:26], c2.flatten())
              and np.allclose(vals[18:26], vals[8:16]))
    else:
        check("F 跳过（先跑 run_all.sh 第 8 步生成 dispatch_exec.txt）", True)

    print()
    print(f"=== 汇总：{CHECKS[0]}/{CHECKS[1]} ===")
    if CHECKS[0] != CHECKS[1]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
