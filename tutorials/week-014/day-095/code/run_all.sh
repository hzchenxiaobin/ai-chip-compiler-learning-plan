#!/usr/bin/env bash
# run_all.sh —— 第 95 天：一键复现全部实验并记录真实输出
# 用法：  bash run_all.sh
# 产出：  outputs/ 下 6 份记录（策略表、suite、三个错误复现、IR 检查）

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs"
MLIR_OPT="${MLIR_OPT:-/usr/lib/llvm-18/bin/mlir-opt}"

mkdir -p "$OUT"

echo "== [1/6] 编译 tiled_matmul =="
g++ -O2 -std=c++17 -Wall -Wextra -o "$HERE/tiled_matmul" "$HERE/tiled_matmul.cpp" || exit 1

echo "== [2/6] 主例：5x7x3, tile 2x4x2, 三种策略 =="
"$HERE/tiled_matmul" 5 7 3 2 4 2 --all | tee "$OUT/strategy-table.txt"

echo
echo "== [3/6] 非整除/边界 shape 套件 =="
"$HERE/tiled_matmul" 5 7 3 2 4 2 --suite | tee "$OUT/shape-suite.txt"

echo
echo "== [4/6] 对照实验：完全整除 6x8x4 =="
"$HERE/tiled_matmul" 6 8 4 2 4 2 --all | tee "$OUT/strategy-table-divisible.txt"

echo
echo "== [5/6] 三个错误复现 =="
for m in danger clamp-store off-by-one; do
  "$HERE/tiled_matmul" 5 7 3 2 4 2 --mode "$m" | tee "$OUT/err-$m.txt"
  echo
done

echo "== [6/7] 边界 IR：生成 + mlir-opt 验证 =="
python3 "$HERE/tilegen.py"
{
  echo "mlir-opt 版本："
  "$MLIR_OPT" --version | head -2
  echo
  for f in "$HERE"/ir/*.mlir; do
    if "$MLIR_OPT" "$f" -o /dev/null; then
      echo "PARSE OK  $(basename "$f")  ($(( $(wc -c < "$f") )) bytes)"
    else
      echo "PARSE FAIL  $(basename "$f")"
    fi
  done
  echo
  echo "静态保护指令计数："
  echo "  matmul_min_bounds.mlir            arith.minsi x$(grep -c 'arith.minsi' "$HERE/ir/matmul_min_bounds.mlir")"
  echo "  matmul_mask.mlir                  arith.cmpi  x$(grep -c 'arith.cmpi'  "$HERE/ir/matmul_mask.mlir") / arith.andi x$(grep -c 'arith.andi' "$HERE/ir/matmul_mask.mlir")"
  echo "  matmul_danger.mlir                保护指令 x0"
  echo
  echo "canonicalize 折叠实验（整除配置的 min 能否被常量折叠消掉）："
  for f in matmul_min_bounds.mlir matmul_min_bounds_divisible.mlir; do
    n=$("$MLIR_OPT" "$HERE/ir/$f" -canonicalize | grep -c 'arith\.minsi' || true)
    echo "  $f -canonicalize 之后 arith.minsi 仍剩 ${n} 条"
  done
  echo "  —— i0 是循环归纳变量，min(i0+TM, M) 不是常量表达式，"
  echo "     常量折叠帮不上忙；这就是 21 次 min 成为真实运行时代价的原因。"
} | tee "$OUT/ir-check.txt"

echo
echo "== [7/7] 上游对照：linalg.matmul 的 transform tiling =="
"$MLIR_OPT" "$HERE/upstream_tile_check.mlir" \
  --test-transform-dialect-interpreter --test-transform-dialect-erase-schedule \
  > "$OUT/upstream-tiling.txt"
{
  echo "== 上游 MLIR 对同一主例（5x7x3, tile 2x4x2）做 tiling 的关键输出 =="
  echo
  grep -n "affine.min\|scf.for\|memref.subview" "$OUT/upstream-tiling.txt" | head -10
  echo
  echo "== affine 映射定义（tile 尺寸的 min 钳制）=="
  grep "^#map" "$OUT/upstream-tiling.txt"
  echo
  echo "读法：上游把 tile 尺寸写成 min(Tile, 维度 - 起点)："
  echo "  min(2, 5-i0) / min(4, 7-j0) / min(2, 3-k0)"
  echo "与手写的 min(起点+Tile, 维度) 是同一个钳制的两种写法（一个算尺寸、一个算终点）。"
} | tee "$OUT/upstream-tiling-summary.txt"

echo
echo "== 全部完成：outputs/ 下共 $(ls "$OUT" | wc -l) 份记录 =="
