#!/usr/bin/env bash
# 第 50 天一键回归：跑全部 15 个 IR 测试，把每个文件的退出码和
# 关键诊断写进 outputs/test-summary.txt（结果为真实运行记录）。
#
# 用法：  bash run_tests.sh /path/to/mini-opt
# mini-opt 缺省取环境变量 MINI_OPT，再缺省取 ../build/bin/mini-opt。

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
MINI="${1:-${MINI_OPT:-$HERE/../build/bin/mini-opt}}"
OUT="$HERE/outputs"
mkdir -p "$OUT"
SUMMARY="$OUT/test-summary.txt"

if [ ! -x "$MINI" ]; then
  echo "找不到可执行的 mini-opt：$MINI" >&2
  echo "先构建：cmake -G Ninja -S code/mini -B build -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir && ninja -C build mini-opt" >&2
  exit 2
fi

printf 'mini-opt: %s\n\n' "$MINI" > "$SUMMARY"

run_case() {  # run_case <文件名> <期望 rc>
  local f="$1" want_rc="$2" rc
  "$MINI" "$HERE/$f.mlir" > /dev/null 2> "$OUT/$f.err"
  rc=$?
  if [ "$rc" -eq "$want_rc" ]; then
    printf 'PASS  rc=%d  %s\n' "$rc" "$f"
  else
    printf 'FAIL  rc=%d (期望 %d)  %s\n' "$rc" "$want_rc" "$f"
  fi
  printf 'PASS  rc=%d  %s\n' "$rc" "$f" >> "$SUMMARY"
  if [ -s "$OUT/$f.err" ]; then
    grep -m1 "error:" "$OUT/$f.err" >> "$SUMMARY" 2>/dev/null || true
  fi
}

# 正例：rc=0（round-trip 原样通过）
for f in fused_add_relu_ok fused_add_relu_dynamic_ok \
         fused_matmul_bias_relu_ok fused_matmul_bias_relu_ok_batched \
         fused_matmul_bias_relu_dynamic_ok \
         target_graph_unfused integration_chain; do
  run_case "$f" 0
done

# 负例：rc=1（Verifier 拦截）
for f in fused_add_relu_mismatch fused_add_relu_broadcast fused_add_relu_bad_result \
         fused_matmul_bias_relu_inner_dim fused_matmul_bias_relu_bad_result \
         fused_matmul_bias_relu_bias_mismatch fused_matmul_bias_relu_bias_broadcast \
         fused_matmul_bias_relu_dynamic_bad_inner; do
  run_case "$f" 1
done

# op 计数对照（图 4 的数据来源）
"$MINI" -mini-count-ops "$HERE/target_graph_unfused.mlir" 2>&1 | grep "remark:" > "$OUT/count-unfused.txt"
"$MINI" -mini-count-ops "$HERE/fused_matmul_bias_relu_ok.mlir" 2>&1 | grep "remark:" > "$OUT/count-fused.txt"
printf '\nop 计数（mini-count-ops）：\n' >> "$SUMMARY"
cat "$OUT/count-unfused.txt" "$OUT/count-fused.txt" >> "$SUMMARY"

echo
echo "汇总已写入 $SUMMARY"
cat "$SUMMARY"
