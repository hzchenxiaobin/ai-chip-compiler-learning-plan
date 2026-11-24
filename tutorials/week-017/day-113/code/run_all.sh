#!/usr/bin/env bash
# 第 113 天一键复现：约 10 秒（本机实测）。
# 依赖：python3 + llvmlite（pip install llvmlite，内嵌 LLVM 22.1.0）。
set -euo pipefail
cd "$(dirname "$0")"

echo "== 环境 =="
python3 - <<'PY'
import platform
from llvmlite import binding as llvm
print("python      :", platform.python_version(), "|", platform.machine())
print("llvmlite LLVM:", ".".join(map(str, llvm.llvm_version_info)))
PY

echo
echo "== 步骤 1：LLVM Dialect → LLVM IR（教学版 mlir-translate）=="
python3 mini_translate.py step.mlir -o outputs/step.ll

echo
echo "== 步骤 2：标注函数参数 / 返回值 / 基本块 + 概念对照表 =="
python3 annotate.py outputs/step.ll --mlir step.mlir

echo
echo "== 步骤 3：目标无关优化（IR→IR）+ 目标相关编译（IR→两个目标的汇编）=="
python3 pipeline.py outputs/step.ll --tag step

echo
echo "== 步骤 4：对照实验 A：乘数 4 → 5 =="
python3 mini_translate.py variants/step_const5.mlir -o outputs/step_const5.ll
python3 pipeline.py outputs/step_const5.ll --tag const5

echo
echo "== 步骤 5：对照实验 B：加一条从未使用的 %dead =="
python3 mini_translate.py variants/step_dead.mlir -o outputs/step_dead.ll
python3 pipeline.py outputs/step_dead.ll --tag dead

echo
echo "== 完成：产出清单 =="
ls -1 outputs/
