#!/usr/bin/env bash
# run_all.sh —— 第 59 天一键复跑：Python Reshape 实验 + MLIR 视图三连
#              （解析/折叠/真实执行）+ Verifier 错误现场 + Verifier 缺口。
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
LLVM_LIB="$(dirname "$(readlink -f "$MLIR_RUNNER")")/../lib"
SHARED="$LLVM_LIB/libmlir_runner_utils.so,$LLVM_LIB/libmlir_c_runner_utils.so"

echo "== 环境 =="
python3 --version
"$MLIR_OPT" --version | head -1
python3 -c "import numpy; print('numpy', numpy.__version__)"
uname -m
echo

echo "== 1. reshape_lab.py（判定表 + 偏移序列 + 计时 + 23 项断言）=="
python3 reshape_lab.py | tee "$OUT/reshape_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_reshape.py（验收测试：手算期望 + 200 组随机对拍）=="
python3 test_reshape.py | tee "$OUT/test_reshape.txt"
echo "exit=$?"
echo

if command -v "$MLIR_OPT" >/dev/null 2>&1; then
  echo "== 3. reshape_views.mlir：解析 + 验证 + 打印 =="
  "$MLIR_OPT" reshape_views.mlir | tee "$OUT/reshape_views_roundtrip.mlir"
  echo "exit=$?"
  echo

  echo "== 4. reshape_views.mlir --canonicalize：reshape 元数据折叠成常数 =="
  "$MLIR_OPT" --canonicalize reshape_views.mlir | tee "$OUT/reshape_views_canon.mlir"
  echo "exit=$?"
  echo

  echo "== 5. reshape_views.mlir --expand-strided-metadata：视图展开成基址+偏移运算 =="
  "$MLIR_OPT" --expand-strided-metadata reshape_views.mlir | tee "$OUT/reshape_views_expanded.mlir"
  echo "exit=$?"
  echo

  echo "== 6. reshape_views.mlir：降级到 LLVM 并用 mlir-cpu-runner 真实执行 =="
  "$MLIR_OPT" --expand-strided-metadata --convert-func-to-llvm \
    --finalize-memref-to-llvm --convert-arith-to-llvm \
    --reconcile-unrealized-casts \
    reshape_views.mlir -o "$OUT/reshape_views.lowered.mlir" \
    && "$MLIR_RUNNER" "$OUT/reshape_views.lowered.mlir" \
       -e main --entry-point-result=void --shared-libs="$SHARED" \
       | tee "$OUT/reshape_views_exec.txt"
  echo "exit=$?"
  echo

  echo "== 7. bad_reshape.mlir：Verifier 应拒绝（退出码 1）=="
  if "$MLIR_OPT" bad_reshape.mlir > "$OUT/bad_reshape.txt" 2>&1; then
    echo "意外通过：Verifier 未拦截非法 reshape" && exit 1
  else
    echo "Verifier 按预期拒绝（exit=$?），诊断如下："
    head -3 "$OUT/bad_reshape.txt"
  fi
  echo

  echo "== 8. reshape_gap.mlir：静态元素数 12 != 15，Verifier 居然放行 =="
  if "$MLIR_OPT" reshape_gap.mlir > "$OUT/reshape_gap.txt" 2>&1; then
    echo "通过验证（exit=0）—— memref.reshape 不静态检查元素数量；"
    echo "mini.reshape 的 Verifier 必须补上这一课（见 reshape_lab.py 的 infer_shape）。"
  else
    echo "被拒绝——该版本 Verifier 已检查元素数量，请更新教程描述。"
  fi
  echo
fi

echo "run_all: 全部完成"
