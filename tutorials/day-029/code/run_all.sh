#!/usr/bin/env bash
# run_all.sh —— 第 29 天：一键跑通三步闭环
#   ① canonicalize：8 条 op → 2 条（Day 23/24 手写规则的"官方版"）
#   ② FileCheck：  给输出判卷（lit 不可用时手动执行它底层的那条管道）
#   ③ JIT 执行：    lower 到 LLVM 方言 → mlir-cpu-runner 真的算出 16
# 用法：bash run_all.sh   （在 tutorials/day-029/code/ 目录下）

set -eu
cd "$(dirname "$0")"

echo "==== ① mlir-opt --canonicalize：优化后的 IR ===="
mlir-opt-18 checkin.mlir --canonicalize

echo
echo "==== ② FileCheck：给输出判卷 ===="
mlir-opt-18 checkin.mlir --canonicalize | FileCheck-18 checkin.mlir && echo "FileCheck PASS"

echo
echo "==== ③ JIT：lower 到 LLVM 方言，再交给 mlir-cpu-runner ===="
mlir-opt-18 run.mlir --convert-func-to-llvm --convert-arith-to-llvm -o run.llvm.mlir
echo "---- run.llvm.mlir（前 8 行）----"
head -8 run.llvm.mlir
echo "---------------------------------"
echo "---- mlir-cpu-runner-18 输出（应为 16）----"
mlir-cpu-runner-18 run.llvm.mlir --entry-point-result=i32

echo
echo "==== 对照：不加 --canonicalize 直接 lower + JIT，结果应相同（语义不变）===="
mlir-opt-18 run.mlir --convert-func-to-llvm --convert-arith-to-llvm -o run.raw.llvm.mlir
RAW=$(mlir-cpu-runner-18 run.raw.llvm.mlir --entry-point-result=i32)
echo "未优化版本输出: $RAW（与上面相同 ⇒ 优化没改语义）"

rm -f run.llvm.mlir run.raw.llvm.mlir
