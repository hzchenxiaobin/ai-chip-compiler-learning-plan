#!/usr/bin/env bash
# run_all.sh —— 第 58 天一键复跑：Python 布局实验 + MLIR 双布局三连（解析/折叠/真实执行）。
#
# 用法：bash run_all.sh
# 输出：屏幕打印全部结果，并把真实输出保存到 outputs/ 目录。

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"

MLIR_OPT="${MLIR_OPT:-mlir-opt}"
MLIR_RUNNER="${MLIR_RUNNER:-mlir-cpu-runner}"
if ! command -v "$MLIR_OPT" >/dev/null 2>&1; then
  for c in /usr/lib/llvm-18/bin/mlir-opt /usr/bin/mlir-opt-18; do
    [ -x "$c" ] && MLIR_OPT="$c" && break
  done
fi
if ! command -v "$MLIR_RUNNER" >/dev/null 2>&1; then
  for c in /usr/lib/llvm-18/bin/mlir-cpu-runner /usr/bin/mlir-cpu-runner-18; do
    [ -x "$c" ] && MLIR_RUNNER="$c" && break
  done
fi
LLVM_LIB="$(dirname "$MLIR_RUNNER")/../lib"
SHARED="$LLVM_LIB/libmlir_runner_utils.so,$LLVM_LIB/libmlir_c_runner_utils.so"

echo "== 环境 =="
python3 --version
"$MLIR_OPT" --version | head -1
python3 -c "import numpy; print('numpy', numpy.__version__)"
uname -m
echo

echo "== 1. layout_lab.py（Layout 对照表 + 访存序列 + 计时 + torch 对照）=="
python3 layout_lab.py | tee "$OUT/layout_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_layout.py（验收测试）=="
python3 test_layout.py | tee "$OUT/test_layout.txt"
echo "exit=$?"
echo

echo "== 3. layout_orders.mlir：解析 + 验证 + 打印 =="
"$MLIR_OPT" layout_orders.mlir | tee "$OUT/layout_orders_roundtrip.mlir"
echo "exit=$?"
echo

echo "== 4. layout_orders.mlir --canonicalize：布局元数据折叠成常数 =="
"$MLIR_OPT" --canonicalize layout_orders.mlir | tee "$OUT/layout_orders_canon.mlir"
echo "exit=$?"
echo

echo "== 5. layout_orders.mlir：降级到 LLVM 并用 mlir-cpu-runner 真实执行 =="
"$MLIR_OPT" --convert-func-to-llvm --finalize-memref-to-llvm \
  --convert-arith-to-llvm --reconcile-unrealized-casts \
  layout_orders.mlir -o "$OUT/layout_orders.lowered.mlir" \
  && "$MLIR_RUNNER" "$OUT/layout_orders.lowered.mlir" \
     -e main --entry-point-result=void --shared-libs="$SHARED" \
     | tee "$OUT/layout_orders_exec.txt"
echo "exit=$?"
echo

echo "== 6. bad_layout.mlir：Verifier 应拒绝（退出码 1）=="
if "$MLIR_OPT" bad_layout.mlir > "$OUT/bad_layout.txt" 2>&1; then
  echo "意外通过：Verifier 未拦截谎报布局" && exit 1
else
  echo "Verifier 按预期拒绝（exit=$?），诊断如下："
  head -3 "$OUT/bad_layout.txt"
fi
echo
echo "run_all: 全部完成"
