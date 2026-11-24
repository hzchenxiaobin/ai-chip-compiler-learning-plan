#!/usr/bin/env bash
# run_all.sh —— 第 67 天（Cast 消除）一键复跑。
#
# 流程：
#   1  环境
#   2  cast_elim_lab.py：主实验——类型全等判据 + 四类反例 + 位宽陷阱 + 方向终审 + MLIR 对表
#   3  test_cast_elim.py：验收测试（A–G 七段）
#   4  静态 IR 文件裁决（cast_chain.mlir 的 canonicalize 实测）
#
# 用法：bash run_all.sh   （在 day-067/code/ 目录下）

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"

echo "== 环境 =="
python3 --version
python3 -c "import numpy; print('numpy', numpy.__version__)"
if command -v mlir-opt >/dev/null 2>&1; then
  MLIR=mlir-opt
elif [ -x /usr/lib/llvm-18/bin/mlir-opt ]; then
  MLIR=/usr/lib/llvm-18/bin/mlir-opt
else
  MLIR=""
fi
if [ -n "$MLIR" ]; then
  "$MLIR" --version | head -1
else
  echo "mlir-opt 不可用（IR 裁决相关步骤将降级）"
fi
uname -m
echo

echo "== 1. cast_elim_lab.py：类型全等判据 + Cast 消除 Pattern + 位宽陷阱 + MLIR 对表 =="
python3 cast_elim_lab.py | tee "$OUT/cast_elim_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_cast_elim.py：验收测试（A–G 七段）=="
python3 test_cast_elim.py | tee "$OUT/test_cast_elim.txt"
echo "exit=$?"
echo

echo "== 3. 静态 IR 文件实测 =="
if [ -n "$MLIR" ]; then
  "$MLIR" cast_chain.mlir --canonicalize -o "$OUT/cast_chain.canon.mlir"
  echo "cast_chain.mlir --canonicalize exit=$?"
  echo "  输出中 cast op 个数：$(grep -cE 'arith\.(extf|truncf|extsi|extui|trunci|bitcast)' "$OUT/cast_chain.canon.mlir")（预期 6：@trunc_ext/@ext_trunc/@extsi_trunc 各 2 个）"
  echo "  return %arg0 个数：$(grep -c 'return %arg0' "$OUT/cast_chain.canon.mlir")（预期 3：@bitcast_same、@truncsi_extsi、@bitcast_chain 整体消除）"
  echo
  echo "  对照探针（同型扩展被 Verifier 拒——期望 exit=1）："
  printf 'module {\n  func.func @extf_same(%%x: f32) -> f32 {\n    %%r = arith.extf %%x : f32 to f32\n    return %%r : f32\n  }\n}\n' \
    | "$MLIR" --canonicalize - 2>"$OUT/extf_same.reject.txt"
  RC=$?
  echo "  extf f32->f32 exit=$RC（错误信息存 outputs/extf_same.reject.txt）"
else
  echo "mlir-opt 不可用，跳过"
fi
echo

echo "run_all: 全部完成"
