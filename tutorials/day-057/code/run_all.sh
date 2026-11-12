#!/usr/bin/env bash
# run_all.sh —— 第 57 天一键复跑：Python 布局实验 + MLIR memref 视图实验。
#
# 用法：bash run_all.sh
# 输出：屏幕打印全部结果，并把真实输出保存到 outputs/ 目录。

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"

MLIR_OPT="${MLIR_OPT:-mlir-opt}"
if ! command -v "$MLIR_OPT" >/dev/null 2>&1; then
  if [ -x /usr/lib/llvm-18/bin/mlir-opt ]; then
    MLIR_OPT=/usr/lib/llvm-18/bin/mlir-opt
  fi
fi

echo "== 环境 =="
python3 --version
"$MLIR_OPT" --version | head -1
python3 -c "import numpy; print('numpy', numpy.__version__)"
echo

echo "== 1. layout_lab.py（同一存储的三个视图 + reshape 对照）=="
python3 layout_lab.py | tee "$OUT/layout_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_layout.py（验收测试）=="
python3 test_layout.py | tee "$OUT/test_layout.txt"
echo "exit=$?"
echo

echo "== 3. layout_views.mlir：解析 + 验证 + 打印 =="
"$MLIR_OPT" layout_views.mlir | tee "$OUT/layout_views_roundtrip.mlir"
echo "exit=$?"
echo

echo "== 4. layout_views.mlir --canonicalize：元数据折叠成常数 =="
"$MLIR_OPT" --canonicalize layout_views.mlir | tee "$OUT/layout_views_canon.mlir"
echo "exit=$?"
echo

echo "== 5. bad_load.mlir：Verifier 应拒绝（退出码 1）=="
if "$MLIR_OPT" bad_load.mlir > "$OUT/bad_load.txt" 2>&1; then
  echo "意外通过：Verifier 未拦截错误下标" && exit 1
else
  echo "Verifier 按预期拒绝（exit=$?），诊断如下："
  cat "$OUT/bad_load.txt"
fi
echo
echo "run_all: 全部完成"
