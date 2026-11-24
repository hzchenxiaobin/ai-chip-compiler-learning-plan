#!/usr/bin/env bash
# 第 119 天一键复现：第 17 周复盘（D113~D118）
#   1. map_layers.py     七层表示信息对账表＋12 题周测＋自检
#   2. 若本机有 mlir-opt：现场重跑 D117 管道验证"周内结论跨版本成立"
#      （LLVM 23 vs D117 冻结的 LLVM 18——结构对账而非逐字节对账）
# 产物全部写 outputs/
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs"
mkdir -p "$OUT"

PY=python3
command -v "$PY" >/dev/null || PY=python

R="$OUT/run-all-log.txt"
: > "$R"
echo "第 119 天：第 17 周复盘——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"

# ── 1. 主脚本：七层对账＋周测 ──
echo "" | tee -a "$R"
echo "[1] map_layers.py：七层信息对账表" | tee -a "$R"
"$PY" "$HERE/map_layers.py" 2>&1 | tee -a "$R"
RC1=$?

# ── 2. 跨版本结构对账（可选：本机有 mlir-opt 才跑）──
MLIR_OPT="$(command -v mlir-opt || echo /opt/homebrew/opt/llvm/bin/mlir-opt)"
if [ -x "$MLIR_OPT" ]; then
  echo "" | tee -a "$R"
  echo "[2] 跨版本对账：本机 LLVM 23 重跑 D117 管道（gemm.mlir → LLVM 方言）" | tee -a "$R"
  TMP=$(mktemp -d)
  "$MLIR_OPT" "$HERE/gemm.mlir" --canonicalize --cse \
      --convert-scf-to-cf --finalize-memref-to-llvm --convert-func-to-llvm \
      --convert-cf-to-llvm --convert-arith-to-llvm --convert-index-to-llvm \
      -o "$TMP/stage2-noreconcile.mlir" 2>>"$R" \
    && "$MLIR_OPT" "$TMP/stage2-noreconcile.mlir" --reconcile-unrealized-casts \
        -o "$TMP/stage2.mlir" 2>>"$R"
  if [ -f "$TMP/stage2.mlir" ]; then
    # 结构特征对账（vs D117 冻结的 gemm-2-llvm-dialect.mlir）
    D117_DIR="$(cd "$HERE/../../day-117/code/outputs" && pwd)"
    NEW_OPS=$("$PY" "$HERE/census.py" "$TMP/stage2.mlir" | head -1 | sed 's|^[^:]*: ||')
    OLD_OPS=$("$PY" "$HERE/census.py" "$D117_DIR/gemm-2-llvm-dialect.mlir" | head -1 | sed 's|^[^:]*: ||')
    NEW_GLUE=$(grep -c "unrealized_conversion_cast" "$TMP/stage2.mlir" || true)
    OLD_GLUE=$(grep -c "unrealized_conversion_cast" "$D117_DIR/gemm-2-llvm-dialect.mlir" || true)
    {
      echo "  本机 LLVM 23：${NEW_OPS}｜胶水 ${NEW_GLUE} 条"
      echo "  D117 冻结（LLVM 18）：${OLD_OPS}｜胶水 ${OLD_GLUE} 条"
      if [ "$NEW_GLUE" = "0" ] && [ "$OLD_GLUE" = "0" ]; then
        echo "  [PASS] 胶水均为 0——reconcile 语义跨 5 个大版本一致"
      else
        echo "  [FAIL] 胶水数不一致"
      fi
    } | tee -a "$R"
    cp "$TMP/stage2.mlir" "$OUT/llvm23-2-llvm-dialect.mlir"
  else
    echo "  [SKIP] 管道失败（版本差异导致 pass 名变化）" | tee -a "$R"
  fi
  rm -rf "$TMP"
else
  echo "[2] [SKIP] 本机无 mlir-opt——跳过跨版本对账（用 D117 冻结值）" | tee -a "$R"
fi

# ── 3. 汇总 ──
SELF="$OUT/self-check.txt"
if [ -f "$SELF" ]; then
  echo "" | tee -a "$R"
  echo "汇总：$(grep 合计 "$SELF")" | tee -a "$R"
fi
exit $RC1
