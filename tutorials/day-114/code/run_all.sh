#!/usr/bin/env bash
# 第 114 天一键复现：约 10 秒（本机实测）。
# 依赖：python3 + numpy + llvmlite（pip install llvmlite，内嵌 LLVM 22.1.0）。
set -euo pipefail
cd "$(dirname "$0")"

echo "== 环境 =="
python3 - <<'PY'
import platform
print("python      :", platform.python_version(), "|", platform.machine())
try:
    import numpy
    print("numpy       :", numpy.__version__)
except ImportError:
    print("numpy       : 不可用")
try:
    import llvmlite
    from llvmlite import binding as llvm
    print("llvmlite    :", llvmlite.__version__,
          "（LLVM " + ".".join(map(str, llvm.llvm_version_info)) + "）")
except ImportError:
    print("llvmlite    : 不可用（TP6 将跳过）")
PY

echo
echo "== 步骤 1：生成输入源 IR（loop_ir.mlir，4×6×3）=="
python3 final_lowering.py --emit-src

echo
echo "== 步骤 2：主运行——类型表 / 合法性清单 / 两种驱动 / 探针 / 对照实验 A+B =="
python3 final_lowering.py

echo
echo "== 步骤 3：对照实验 C——换形状 2×3×2 再跑全套 =="
python3 final_lowering.py --shape 2 3 2 --tag s233

echo
echo "== 完成：产出清单 =="
ls -1 outputs/
