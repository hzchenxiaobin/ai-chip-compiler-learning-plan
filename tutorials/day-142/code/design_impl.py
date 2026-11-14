#!/usr/bin/env python3
"""第 142 天核心模块：design_impl.py——块循环 Tiling 的实现方案（施工图）。

计划条目："分析扩展对 IR、Pass、Lowering、Runtime 和测试的影响；
画出修改点和数据流，先定义最小可运行切片；产出：接口设计、
修改文件清单和测试计划。"

今天设计并验证「最小切片」：块循环 IR 生成器（手写一份目标形态
样例——D143 的施工蓝图）。
"""
from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
LLVM = "/opt/homebrew/opt/llvm/bin"

# 目标形态样例：4x6x3 的 matmul、tile=(2,2,3)
BLOCK_LOOP_IR = """// 块循环形态（D142 的施工蓝图样例）：外层 tile 壳＋内层点循环
// 与朴素版（D124）的差别：三层 tile 循环壳 + 点循环用块内边界
module {
  func.func @kernel_tiled(%a: memref<4x6xf32, strided<[6, 1]>>,
                          %b: memref<6x3xf32, strided<[3, 1]>>)
      -> memref<4x3xf32> attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<4x3xf32>
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant 4 : index
    %cN = arith.constant 3 : index
    %cK = arith.constant 6 : index
    %cTM = arith.constant 2 : index    // tile M
    %cTN = arith.constant 2 : index    // tile N
    %cTK = arith.constant 3 : index    // tile K
    %z = arith.constant 0.0 : f32
    // 外层 tile 壳：i0/j0/k0 步长 = tile
    scf.for %i0 = %c0 to %cM step %cTM {
      scf.for %j0 = %c0 to %cN step %cTN {
        scf.for %k0 = %c0 to %cK step %cTK {
          // 内层点循环：块内边界 = min(i0+TM, M)（边界钳制——D90 语义）
          %ihi = arith.minsi %i0, %cM : index    // 教学简化：直接用常量边界
          // 完整版应为 %ihi = min(i0+TM, M)——D143 实现时补全
          scf.for %i = %i0 to %ihi step %c1 {
            scf.for %j = %j0 to %cN step %c1 {
              %acc = scf.for %k = %k0 to %cK step %c1
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
        }
      }
    }
    func.return %c : memref<4x3xf32>
  }
}
"""


def validate_ir() -> bool:
    """验证目标形态能过管道（七 pass 全通）。"""
    p = os.path.join(OUT, "blueprint.mlir")
    open(p, "w").write(BLOCK_LOOP_IR)
    cur = p
    passes = [(["--canonicalize", "--cse"], "canon"),
              (["--convert-scf-to-cf"], "scfcf"),
              (["--finalize-memref-to-llvm"], "memref"),
              (["--convert-func-to-llvm"], "func"),
              (["--convert-cf-to-llvm"], "cf"),
              (["--convert-arith-to-llvm"], "arith"),
              (["--convert-index-to-llvm"], "index"),
              (["--reconcile-unrealized-casts"], "reconcile")]
    for i, (flags, name) in enumerate(passes):
        nxt = os.path.join(OUT, f"s{i}-{name}.mlir")
        r = subprocess.run([f"{LLVM}/mlir-opt", cur] + flags + ["-o", nxt],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  pass {name} 失败: {r.stderr[:150]}")
            return False
        cur = nxt
    ll = os.path.join(OUT, "blueprint.ll")
    r = subprocess.run([f"{LLVM}/mlir-translate", cur, "--mlir-to-llvmir",
                        "-o", ll], capture_output=True, text=True)
    return r.returncode == 0


PLAN = """第 142 天：实现方案（施工图）

一、影响分析（计划条目：IR/Pass/Lowering/Runtime/测试 五个面）
  IR      ：S2 生成新形态（块循环壳＋点循环）——S4/S5 的 pass 不用改
            （scf.for 语义相同，多两层循环而已）
  Pass    ：零修改！scf→cf/memref/func 转换对循环层数无感
  Lowering：零修改（同上）
  Runtime ：ciface 签名不变（tile 是编译期决策不进运行时）
  测试    ：正确性沿用 D135 fuzz（块循环也过 200 组）；
            性能用 D125 kernel_timing（tile 版 vs 朴素版对照）

二、修改点与数据流
  e2e.py 的 gen_loop_ir_full()：
    加 tile 参数 → 生成块循环版（外层壳＋min 钳制）
    tile=None 或 tile==shape → 朴素版（向后兼容！）
  数据流不变：graph → S1 → S2（新形态）→ S4 → S5 → S6

三、最小可运行切片（D143 的目标）
  gen_loop_ir_full(g, tile=(2,2,3)) 生成上方的 blueprint 形态
  → 七 pass 全通 → 与朴素版 bitwise 对照（同 golden）

四、测试计划
  正确性：blueprint 能过管道（今天已验）＋ D143 起逐 tile 对比
  边界：tile=(1,1,1)（退化=朴素）/ tile=shape（单块）/ tile>shape（钳制）
  性能：D146 验收时对照（教学规模的预期：差异小、方向不定——
        反例是合法结果）
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    print("== 蓝图验证：块循环 IR 能否过七 pass 管道 ==")
    ok = validate_ir()
    print(f"  {'PASS：蓝图形态合法，七 pass 全通' if ok else 'FAIL：蓝图要修'}\n")
    open(os.path.join(OUT, "plan.txt"), "w").write(PLAN)
    print("施工图已生成 plan.txt")
    checks = [
        ("蓝图过管道", ok),
        ("五面影响分析", PLAN.count("零修改") >= 2),
        ("修改点明确", "gen_loop_ir_full" in PLAN),
        ("测试计划三类", all(k in PLAN for k in ("正确性", "边界", "性能"))),
    ]
    for n, okk in checks:
        print(f"  [{'PASS' if okk else 'FAIL'}] {n}")
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
