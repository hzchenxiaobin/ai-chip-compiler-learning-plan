#!/usr/bin/env bash
# run_all.sh —— 第 64 天（Transpose 的语义）一键复跑。
#
# 流程：
#   1  环境
#   2  transpose_lab.py：主实验——三种命运 + mini.transpose Verifier + MLIR 对表
#   3  test_transpose.py：验收测试（A–H 八段）
#   4  两个静态 IR 文件的 mlir-opt 裁决（合法 exit=0 / 非法 exit=1）
#
# 用法：bash run_all.sh   （在 day-064/code/ 目录下）

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"

echo "== 环境 =="
python3 --version
python3 -c "import numpy; print('numpy', numpy.__version__)"
if command -v mlir-opt >/dev/null 2>&1; then
  mlir-opt --version | head -1
elif [ -x /usr/lib/llvm-18/bin/mlir-opt ]; then
  /usr/lib/llvm-18/bin/mlir-opt --version | head -1
else
  echo "mlir-opt 不可用（IR 裁决相关步骤将降级）"
fi
uname -m
echo

echo "== 1. transpose_lab.py：三种命运 + 四关 Verifier + MLIR 对表 =="
python3 transpose_lab.py | tee "$OUT/transpose_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_transpose.py：验收测试（A–H 八段）=="
python3 test_transpose.py | tee "$OUT/test_transpose.txt"
echo "exit=$?"
echo

echo "== 3. 静态 IR 文件裁决 =="
if command -v mlir-opt >/dev/null 2>&1; then
  MLIR=mlir-opt
elif [ -x /usr/lib/llvm-18/bin/mlir-opt ]; then
  MLIR=/usr/lib/llvm-18/bin/mlir-opt
else
  MLIR=""
fi
if [ -n "$MLIR" ]; then
  "$MLIR" transpose_2d.mlir -o /dev/null 2>"$OUT/transpose_2d.verdict.txt"
  echo "transpose_2d.mlir  exit=$?（预期 0）"
  "$MLIR" bad_transpose.mlir -o /dev/null 2>"$OUT/bad_transpose.verdict.txt"
  echo "bad_transpose.mlir exit=$?（预期 1）；报错首行："
  grep -m1 "error:" "$OUT/bad_transpose.verdict.txt" | sed "s/^/    /"
else
  echo "mlir-opt 不可用，跳过"
fi
echo

echo "run_all: 全部完成"
