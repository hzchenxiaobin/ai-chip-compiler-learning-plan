#!/usr/bin/env bash
# run_all.sh —— 第 60 天一键复跑：Python Broadcast 实验 + MLIR 双视角三连
#              （shape 折叠 / linalg 循环展开 / 真实执行）+ Verifier 错误现场。
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

echo "== 1. broadcast_lab.py（判定表 + stride-0 + 未知维度 + 随机对拍 + 9 项断言）=="
python3 broadcast_lab.py | tee "$OUT/broadcast_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_broadcast.py（验收测试：手算期望 + 400 组随机对拍）=="
python3 test_broadcast.py | tee "$OUT/test_broadcast.txt"
echo "exit=$?"
echo

if command -v "$MLIR_OPT" >/dev/null 2>&1; then
  echo "== 3. broadcast_shapes.mlir：解析 + 验证 + 打印 =="
  "$MLIR_OPT" broadcast_shapes.mlir | tee "$OUT/broadcast_shapes_roundtrip.mlir"
  echo "exit=$?"
  echo

  echo "== 4. broadcast_shapes.mlir --canonicalize：兼容形状折成常数，失配原样留 =="
  "$MLIR_OPT" --canonicalize broadcast_shapes.mlir | tee "$OUT/broadcast_shapes_canon.mlir"
  echo "exit=$?"
  echo

  echo "== 5. broadcast_add.mlir --convert-linalg-to-loops：广播降成「少一个下标」的循环 =="
  "$MLIR_OPT" --convert-linalg-to-loops broadcast_add.mlir | tee "$OUT/broadcast_add_loops.mlir"
  echo "exit=$?"
  echo

  echo "== 6. broadcast_add.mlir：降级到 LLVM 并用 mlir-cpu-runner 真实执行 =="
  "$MLIR_OPT" --convert-linalg-to-loops --convert-scf-to-cf \
    --convert-cf-to-llvm --convert-func-to-llvm \
    --finalize-memref-to-llvm --convert-arith-to-llvm \
    --reconcile-unrealized-casts \
    broadcast_add.mlir -o "$OUT/broadcast_add.lowered.mlir" \
    && "$MLIR_RUNNER" "$OUT/broadcast_add.lowered.mlir" \
       -e main --entry-point-result=void --shared-libs="$SHARED" \
       | tee "$OUT/broadcast_add_exec.txt"
  echo "exit=$?"
  echo

  echo "== 7. bad_broadcast.mlir：Verifier 应拒绝（退出码 1）=="
  if "$MLIR_OPT" bad_broadcast.mlir > "$OUT/bad_broadcast.txt" 2>&1; then
    echo "意外通过：Verifier 未拦截非法广播" && exit 1
  else
    echo "Verifier 按预期拒绝，诊断如下："
    head -2 "$OUT/bad_broadcast.txt"
  fi
  echo
fi

echo "run_all: 全部完成"
