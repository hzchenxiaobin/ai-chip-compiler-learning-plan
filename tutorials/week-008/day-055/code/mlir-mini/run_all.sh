#!/usr/bin/env bash
# run_all.sh —— 第 55 天 MLIR 层验收语料的一键复跑。
# 用法: bash run_all.sh          （在 mlir-mini/ 目录下）
# 输出: outputs/accept-summary.txt（每用例的 stdout/stderr 另存 outputs/M*.out/.err）
#
# 期望判决与 Python 层（mini_fuse_accept.py 的 C01～C14）一一对应：
#   正例 fused / 负例 identity（恒等拒绝）/ Verifier 负例 verifier_reject
# rc=0 全部通过；rc=1 有失败。

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"
TOOL=./build/mini-accept
SUMMARY="$OUT/accept-summary.txt"

pass=0; fail=0

run() {  # run <名字> <期望判决> <命令...>
  local name="$1"; local want="$2"; shift 2
  "$@" > "$OUT/$name.out" 2> "$OUT/$name.err"
  local rc=$?
  local verdict
  verdict=$(grep -oE 'verdict=(fused|identity|verifier_reject)' "$OUT/$name.out" | cut -d= -f2)
  if [ "$rc" -eq 0 ] && [ "$verdict" == "$want" ]; then
    echo "$name  ->  rc=0  判决 $verdict (期望 $want)  通过"
    pass=$((pass+1))
  else
    echo "$name  ->  rc=$rc  判决 ${verdict:-（无）} (期望 $want)  失败!"
    fail=$((fail+1))
  fi
  # 最终形态自述：只看「融合后」段落里出现的 mini.* 算子（输入段不算）
  local form
  form=$(sed -n '/^===== 融合后（A 路/,$p' "$OUT/$name.out" \
         | grep -oE "mini\.(fused_add_relu|fused_matmul_bias_relu|fused_matmul_bias|matmul|add|relu)" \
         | sort -u | tr '\n' ' ')
  echo "    最终形态: ${form:-（被闸门一拦下，无融合后 IR）}"
}

{
echo "第 55 天 MLIR 层验收汇总 —— $(date '+%Y-%m-%d %H:%M')"
echo "工具: $TOOL；环境: $(g++ --version | head -1)，"
echo "      $(/usr/lib/llvm-18/bin/mlir-opt --version | head -1)，aarch64 Linux"
echo "验收管道: P1(benefit 1) + P2(benefit 1) + P51g(让位版) + P3(benefit 2)"
echo "          ＋ 类型闸门（fused* 语义只对 f32 验证过）"
echo

echo "== 正例：应融合，且双遍历同形态（R1）=="
run M01_bias_relu         fused           $TOOL inputs/m01_bias_relu.mlir --expect=fused
run M02_add_relu_only     fused           $TOOL inputs/m02_add_relu_only.mlir --expect=fused

echo
echo "== 负例（Pattern 闸门）：应恒等拒绝（R2：IR 逐字不变）=="
run M03_multi_user        identity        $TOOL inputs/m03_multi_user_product.mlir --expect=identity
run M04_shared_result     fused           $TOOL inputs/m04_shared_result.mlir --expect=fused
run M05_both_matmul       identity        $TOOL inputs/m05_both_matmul.mlir --expect=identity
run M06_f64_add_relu      identity        $TOOL inputs/m06_f64_add_relu.mlir --expect=identity
run M07_mixed_dtype       identity        $TOOL inputs/m07_mixed_dtype_bias.mlir --expect=identity

echo
echo "== 负例（Verifier 闸门）：parse + verify 拦下 =="
run M08_f64_matmul        verifier_reject $TOOL inputs/m08_f64_matmul_chain.mlir --expect=verifier_reject
run M09_bad_shape         verifier_reject $TOOL inputs/m09_bad_bias_shape.mlir --expect=verifier_reject
run M10_bad_broadcast     verifier_reject $TOOL inputs/m10_bad_bias_broadcast.mlir --expect=verifier_reject

echo
echo "== 汇总: $pass 通过 / $fail 失败 =="
} | tee "$SUMMARY"

[ "$fail" -eq 0 ]
