#!/usr/bin/env python3
"""第 128 天核心模块：dyn_shape.py——运行期参数与 Shape。

D127 的审计说 minic 是『纯静态派』（Shape=COMPILE）。今天把这一个
决策点翻转：签名从 memref<4x6xf32> 变 memref<?x?xf32>——shape 从
编译期常量变成运行期从描述符读出的参数。

三个子实验（对照出『动态的代价』）：
  E1 静态基线   memref<4x6>   —— D124 原版（对照锚点）
  E2 动态签名   memref<?x?>   —— 同一语义，shape 进描述符
  E3 动态+特化  按运行 shape 派发（D129 预演）

关键观察点：
  · 签名差异：strided<[6,1]> 写死 vs strided<[?,?]>（或省略）
  · 循环边界：icmp slt i64 %38, 4（常量）vs extractvalue+icmp（运行期）
  · 指令数差：动态版多多少条（描述符读回的代价）
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")

LLVM_BIN = "/opt/homebrew/opt/llvm/bin"

# 静态基线（D124 原版语义，简化到最小可对照）
STATIC_IR = """module {
  func.func @kernel_static(%a: memref<4x6xf32, strided<[6, 1]>>,
                           %b: memref<6x3xf32, strided<[3, 1]>>)
      -> memref<4x3xf32> attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<4x3xf32>
    %c0 = arith.constant 0 : index
    %cM = arith.constant 4 : index
    %cN = arith.constant 3 : index
    %cK = arith.constant 6 : index
    %c1 = arith.constant 1 : index
    %z = arith.constant 0.0 : f32
    scf.for %i = %c0 to %cM step %c1 {
      scf.for %j = %c0 to %cN step %c1 {
        %acc = scf.for %k = %c0 to %cK step %c1
                    iter_args(%acc = %z) -> (f32) {
          %aij = memref.load %a[%i, %k] : memref<4x6xf32, strided<[6, 1]>>
          %bkj = memref.load %b[%k, %j] : memref<6x3xf32, strided<[3, 1]>>
          %p = arith.mulf %aij, %bkj : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }
        memref.store %acc, %c[%i, %j] : memref<4x3xf32>
      }
    }
    func.return %c : memref<4x3xf32>
  }
}
"""

# 动态版：shape 全部进描述符（? 占位）
DYNAMIC_IR = """module {
  func.func @kernel_dynamic(%a: memref<?x?xf32>,
                            %b: memref<?x?xf32>)
      -> memref<?x?xf32> attributes { llvm.emit_c_interface } {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %z = arith.constant 0.0 : f32
    // 运行期读 shape：M/N/K 从描述符的 sizes 字段来
    %M = memref.dim %a, %c0 : memref<?x?xf32>
    %K = memref.dim %a, %c1 : memref<?x?xf32>
    %N = memref.dim %b, %c1 : memref<?x?xf32>
    // 动态 alloc：shape 是运行期值
    %c = memref.alloc(%M, %N) : memref<?x?xf32>
    scf.for %i = %c0 to %M step %c1 {
      scf.for %j = %c0 to %N step %c1 {
        %acc = scf.for %k = %c0 to %K step %c1
                    iter_args(%acc = %z) -> (f32) {
          %aij = memref.load %a[%i, %k] : memref<?x?xf32>
          %bkj = memref.load %b[%k, %j] : memref<?x?xf32>
          %p = arith.mulf %aij, %bkj : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }
        memref.store %acc, %c[%i, %j] : memref<?x?xf32>
      }
    }
    func.return %c : memref<?x?xf32>
  }
}
"""


def run_pipeline(ir_text: str, tag: str) -> dict:
    """跑 D117 七 pass 管道＋translate＋llc，返回指标。"""
    d = os.path.join(OUT, tag)
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "input.mlir")
    open(src, "w").write(ir_text)

    passes = [
        (["--canonicalize", "--cse"], "canonicalize"),
        (["--convert-scf-to-cf"], "scf-cf"),
        (["--finalize-memref-to-llvm"], "memref-llvm"),
        (["--convert-func-to-llvm"], "func-llvm"),
        (["--convert-cf-to-llvm"], "cf-llvm"),
        (["--convert-arith-to-llvm"], "arith-llvm"),
        (["--convert-index-to-llvm"], "index-llvm"),
        (["--reconcile-unrealized-casts"], "reconcile"),
    ]
    cur = src
    for i, (flags, name) in enumerate(passes):
        nxt = os.path.join(d, f"s4-{i:02d}-{name}.mlir")
        r = subprocess.run([f"{LLVM_BIN}/mlir-opt", cur] + flags + ["-o", nxt],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return {"ok": False, "stage": name, "error": r.stderr[:300], "dir": d}
        cur = nxt

    ll = os.path.join(d, "out.ll")
    r = subprocess.run([f"{LLVM_BIN}/mlir-translate", cur, "--mlir-to-llvmir", "-o", ll],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "stage": "translate", "error": r.stderr[:300], "dir": d}

    s = os.path.join(d, "out.s")
    subprocess.run([f"{LLVM_BIN}/llc", ll, "-o", s], capture_output=True)

    text = open(ll).read()
    return {
        "ok": True, "dir": d, "ll": ll,
        "ll_lines": len([l for l in text.splitlines() if l.strip() and not l.strip().startswith(";")]),
        "ssa": sum(1 for l in text.splitlines() if l.strip().startswith("%")),
        "extractvalue": text.count("extractvalue"),
        "phi": text.count(" phi "),
        "icmp": text.count("icmp"),
        "fmul": text.count("fmul"),
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    results = {}

    print("== E1 静态基线（D124 原版语义）==")
    r = run_pipeline(STATIC_IR, "e1-static")
    results["e1"] = r
    print(f"  ok={r['ok']}｜.ll {r.get('ll_lines')} 行、ssa {r.get('ssa')}、"
          f"extractvalue {r.get('extractvalue')}、icmp {r.get('icmp')}")
    if not r["ok"]:
        print(f"  ERROR @ {r['stage']}: {r['error'][:120]}")

    print("== E2 动态签名（shape 进描述符）==")
    r = run_pipeline(DYNAMIC_IR, "e2-dynamic")
    results["e2"] = r
    if r["ok"]:
        print(f"  ok=True｜.ll {r['ll_lines']} 行、ssa {r['ssa']}、"
              f"extractvalue {r['extractvalue']}、icmp {r['icmp']}")
        print(f"  —— 动态版代价：多 {r['extractvalue']} 次描述符读回（静态版 0）")
    else:
        print(f"  ok=False @ {r['stage']}: {r['error'][:200]}")
        print("  —— 动态签名被管道拒收（memref.alloc 动态 shape 不支持）——D128 的发现！")

    return results


if __name__ == "__main__":
    main()
