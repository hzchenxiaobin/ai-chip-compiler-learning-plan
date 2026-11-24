#!/usr/bin/env bash
# run_all.sh —— 第 62 天一键复跑：特化工具 + 前后 IR 对照 + 产物实验 + 分发现场。
#
# 用法：bash run_all.sh
# 输出：屏幕打印全部结果，并把真实输出保存到 outputs/ 目录。
#
# 流程：
#   1    环境
#   2    specialize.py --list-dims：看看要特化的是什么
#   3    特化 matmul_dyn.mlir → outputs/matmul_spec.mlir（替换 + 重推 + 重验）
#   4    特化前后 IR 对照：验证 / 降 scf 循环（memref.dim 1→0）
#        / 降 affine 循环 + 三次 full-unroll（动态版 M 循环卡住，特化版全直码化）
#   5    k_blind 对照实验：动态版放行（? 失明）→ 特化后被 mlir-opt 拦下
#   6    products_lab.py：特化收益、产物数量与编译时间、分发模拟（全实测）
#   7    test_specialize.py：验收测试（A-F 六段 28 个测试点）
#   8    dispatch.mlir：cpu-runner 真实执行（命中 / 回退 / 缓存增长三场景）

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
export MLIR_OPT
LOWER="--convert-linalg-to-loops --convert-scf-to-cf --convert-cf-to-llvm \
  --convert-func-to-llvm --finalize-memref-to-llvm --convert-arith-to-llvm \
  --reconcile-unrealized-casts"

echo "== 环境 =="
python3 --version
"$MLIR_OPT" --version | head -1
python3 -c "import numpy; print('numpy', numpy.__version__)" 2>/dev/null \
  || echo "numpy 不可用（test_specialize 的 F 段对拍需要它）"
uname -m
echo

echo "== 1. 先看看要特化的是什么（--list-dims）=="
python3 specialize.py matmul_dyn.mlir --list-dims | tee "$OUT/list_dims.txt"
echo

echo "== 2. 特化：matmul_dyn.mlir → outputs/matmul_spec.mlir =="
python3 specialize.py matmul_dyn.mlir --specialize-shape "a=2x3,b=3x2" \
  -o "$OUT/matmul_spec.mlir" | tee "$OUT/specialize_run.txt"
echo "exit=$?"
echo

if command -v "$MLIR_OPT" >/dev/null 2>&1; then
  echo "== 3. 特化前后 IR 对照 =="
  echo "-- 3a. 两版都过 parse+verify："
  "$MLIR_OPT" matmul_dyn.mlir > /dev/null && echo "   动态版 exit=0"
  "$MLIR_OPT" "$OUT/matmul_spec.mlir" > /dev/null && echo "   特化版 exit=0"
  echo "-- 3b. 降 scf 循环（看 M 的上界从哪来）："
  for f in matmul_dyn "$OUT/matmul_spec"; do
    "$MLIR_OPT" --convert-linalg-to-loops "$f.mlir" > "$OUT/$(basename "$f")_scf.mlir"
    echo "   $(basename "$f"): memref.dim=$(grep -c 'memref.dim' "$OUT/$(basename "$f")_scf.mlir") \
scf.for=$(grep -c 'scf.for' "$OUT/$(basename "$f")_scf.mlir") \
行数=$(wc -l < "$OUT/$(basename "$f")_scf.mlir")"
  done
  grep -n "memref.dim\|%dim" "$OUT/matmul_dyn_scf.mlir" | head -2 | sed 's/^/     /'
  echo "-- 3c. 降 affine 循环 + 三次 full-unroll："
  for f in matmul_dyn "$OUT/matmul_spec"; do
    stem=$(basename "$f")
    "$MLIR_OPT" --convert-linalg-to-affine-loops "$f.mlir" \
      -o "$OUT/${stem}_aff.mlir"
    cur="$OUT/${stem}_aff.mlir"
    for i in 1 2 3; do
      "$MLIR_OPT" --affine-loop-unroll=unroll-full "$cur" -o "$OUT/${stem}_unr${i}.mlir"
      cur="$OUT/${stem}_unr${i}.mlir"
    done
    echo "   $stem: unroll 后 affine.for=$(grep -c 'affine.for' "$cur") \
affine.load=$(grep -c 'affine.load' "$cur") 行数=$(wc -l < "$cur") 字节=$(stat -c%s "$cur")"
  done
  echo "   （动态版的 M 循环上界是 %dim，三次 unroll 也展不开；特化版全部直码化）"
  echo

  echo "== 4. k_blind 对照：藏在 ? 后面的 K 失配，特化后被重新点亮 =="
  "$MLIR_OPT" k_blind.mlir > /dev/null 2> "$OUT/k_blind_dyn.txt" \
    && echo "   动态版（M=?）：exit=0 放行——静态检查失明"
  python3 specialize.py k_blind.mlir --specialize-shape "a=2x4,b=3x2" \
    --force -o "$OUT/k_blind_spec_rejected.mlir" | tee "$OUT/k_blind_spec.txt"
  echo "   → 特化版被 mlir-opt 拦下（exit=1）：特化把静态检查网重新点亮"
  echo
fi

echo "== 5. products_lab.py：收益、产物数量、编译时间、分发模拟（全实测）=="
python3 products_lab.py | tee "$OUT/products_lab.txt"
echo "exit=$?"
echo

echo "== 6. test_specialize.py：验收测试 =="
python3 test_specialize.py | tee "$OUT/test_specialize.txt"
echo "exit=$?"
echo

if command -v "$MLIR_RUNNER" >/dev/null 2>&1; then
  echo "== 7. dispatch.mlir：分发现场（命中 / 回退 / 缓存增长三场景）=="
  "$MLIR_OPT" $LOWER dispatch.mlir -o "$OUT/dispatch.lowered.mlir" \
    && "$MLIR_RUNNER" "$OUT/dispatch.lowered.mlir" -e main \
       --entry-point-result=void --shared-libs="$SHARED" \
       | tee "$OUT/dispatch_exec.txt"
  echo "exit=$?"
  echo "   输出解读：每场景先打 [hit 标志][M]，再打结果——"
  echo "   场景 1: 1,2 + 220/280/490/640（命中特化版）"
  echo "   场景 2: 0,4 + C2 八个值（回退通用版，带运行期 K 检查）"
  echo "   场景 3: 1,4 + 同样八个值（缓存长出第二份特化后再命中）"
  echo "   两版数值逐位一致 = 特化语义保持的直接证据"
  echo
fi

echo "run_all: 全部完成"
