#!/usr/bin/env bash
# run_all.sh —— 第 53 天全部实验的一键复跑。
# 用法: bash run_all.sh          （在 mlir-mini/ 目录下）
# 输出: ../outputs/test-summary.txt

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"
TOOL=./build/mini-fuse-bias
MLIR_OPT=/usr/lib/llvm-18/bin/mlir-opt
SUMMARY="$OUT/test-summary.txt"

pass=0; fail=0

run() {  # run <名字> <期望rc> <命令...>
  local name="$1"; local want_rc="$2"; shift 2
  "$@" > "$OUT/$name.out" 2> "$OUT/$name.err"
  local rc=$?
  if [ "$rc" -eq "$want_rc" ]; then
    echo "$name  ->  rc=$rc  (期望 $want_rc)  通过"
    pass=$((pass+1))
  else
    echo "$name  ->  rc=$rc  (期望 $want_rc)  失败!"
    fail=$((fail+1))
  fi
}

{
echo "第 53 天实验汇总 —— $(date '+%Y-%m-%d %H:%M')"
echo "工具: $TOOL；环境: $(g++ --version | head -1)，MLIR $($MLIR_OPT --version | head -1)"
echo

echo "== 正例（期望 rc=0）=="
run bias_relu          0 $TOOL inputs/bias_relu.mlir
run bias_only          0 $TOOL inputs/bias_only.mlir
run bias_on_left       0 $TOOL inputs/bias_on_left.mlir
run multi_user_reject  0 $TOOL inputs/multi_user_product.mlir
run multi_user_keep    0 $TOOL inputs/multi_user_product.mlir --strategy=keep
run shared_result      0 $TOOL inputs/shared_result.mlir
run both_matmul        0 $TOOL inputs/both_matmul.mlir

echo
echo "== 负例（期望 rc=1：Verifier 拦截，轮不到 Pattern）=="
run rank1_bias             1 $TOOL inputs/rank1_bias.mlir
run bad_bias_shape         1 $TOOL inputs/bad_bias_shape.mlir
run fused_bad_result_type  1 $TOOL inputs/fused_bad_result_type.mlir
run fused_rank1_bias       1 $TOOL inputs/fused_rank1_bias.mlir

echo
echo "== 上游 linalg 对照 =="
if [ -x "$MLIR_OPT" ]; then
  $MLIR_OPT inputs/matmul_bias_relu_linalg.mlir \
      --convert-elementwise-to-linalg --linalg-fuse-elementwise-ops \
      > "$OUT/linalg_fused.out" 2> "$OUT/linalg_fused.err"
  echo "linalg 对照 rc=$?，结果见 linalg_fused.out"
else
  echo "未找到 $MLIR_OPT，跳过"
fi

echo
echo "== 汇总: $pass 通过 / $fail 失败 =="
} | tee "$SUMMARY"

[ "$fail" -eq 0 ]
