#!/usr/bin/env bash
# run_all.sh —— 第 54 天全部 MLIR 实验的一键复跑。
# 用法: bash run_all.sh          （在 mlir-mini/ 目录下）
# 输出: outputs/test-summary.txt
#
# 期望值说明：
#   rc=0  贪心驱动收敛（注意：收敛到「合法但不理想」的形态也是 rc=0——
#         抢跑实验正是靠这个展示「verify 通过 ≠ 融对了」）
#   rc=2  驱动未收敛（oscillate + 护栏：Pattern 互相打架）
#   rc=124 timeout 杀掉（oscillate 不加护栏：拉锯永不停）

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"
TOOL=./build/mini-fuse3
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
  # 最终形态自述：从「融合后」段落里提取出现的算子，一眼看出融成什么样
  local form
  form=$(sed -n '/===== 融合后 =====/,$p' "$OUT/$name.out" \
         | grep -oE "mini\.(fused_add_relu|fused_matmul_bias_relu|fused_matmul_bias|matmul|add|relu)" \
         | sort -u | tr '\n' ' ')
  echo "    最终形态: ${form:-（无，或未到融合后段落）}"
}

{
echo "第 54 天实验汇总 —— $(date '+%Y-%m-%d %H:%M')"
echo "工具: $TOOL；环境: $(g++ --version | head -1)，"
echo "      $($MLIR_OPT --version | head -1)，aarch64 Linux"
echo

echo "== A. 三算子融合的三条路线（主线图 bias_relu，期望都到 fused_matmul_bias_relu）=="
run two_stage_main  0 $TOOL inputs/bias_relu.mlir --set=two-stage
run direct_main     0 $TOOL inputs/bias_relu.mlir --set=direct
run all_main        0 $TOOL inputs/bias_relu.mlir --set=all
run all_main_topdn  0 $TOOL inputs/bias_relu.mlir --set=all --top-down

echo
echo "== B. 抢跑事故（同一集合 [P51,P3]，只换访问顺序）=="
run steal_bottomup  0 $TOOL inputs/bias_relu.mlir --set=steal
run steal_topdown    0 $TOOL inputs/bias_relu.mlir --set=steal --top-down

echo
echo "== C. 两种修法：让位规则 / Pass 管道顺序（两种遍历都试）=="
run guarded_bottomup 0 $TOOL inputs/bias_relu.mlir --set=guarded
run guarded_topdown   0 $TOOL inputs/bias_relu.mlir --set=guarded --top-down
run pipeline_main     0 $TOOL inputs/bias_relu.mlir --set=pipeline

echo
echo "== D. 修法不误伤纯 Add+Relu 图（小融合的正确主场）=="
run steal_small    0 $TOOL inputs/add_relu_only.mlir --set=steal
run guarded_small  0 $TOOL inputs/add_relu_only.mlir --set=guarded
run pipeline_small 0 $TOOL inputs/add_relu_only.mlir --set=pipeline

echo
echo "== E. %s 共用的半融合不动点 + 乘积多使用者的恒等拒绝 =="
run two_stage_shared 0 $TOOL inputs/shared_result.mlir --set=two-stage
run direct_shared     0 $TOOL inputs/shared_result.mlir --set=direct
run steal_shared     0 $TOOL inputs/shared_result.mlir --set=steal
run all_multi        0 $TOOL inputs/multi_user_product.mlir --set=all

echo
echo "== F. 互相打架的 Pattern：护栏止损 / 无护栏拉锯 =="
run oscillate_guarded 2 $TOOL inputs/bias_relu.mlir --set=oscillate --max-rewrites=6
if command -v timeout > /dev/null; then
  timeout 10 $TOOL inputs/bias_relu.mlir --set=oscillate \
      > "$OUT/oscillate_hang.out" 2> "$OUT/oscillate_hang.err"
  rc=$?
  if [ "$rc" -eq 124 ]; then
    echo "oscillate_hang  ->  rc=124 (期望 124)  通过（10 秒内未返回，被 timeout 杀掉；"
    echo "    Unfuse 执行 $(grep -cE '\[Unfuse\]' "$OUT/oscillate_hang.err") 次仍在拉锯）"
    pass=$((pass+1))
  else
    echo "oscillate_hang  ->  rc=$rc  (期望 124)  失败!"
    fail=$((fail+1))
  fi
else
  echo "oscillate_hang 跳过（无 timeout 命令）"
fi

echo
echo "== 汇总: $pass 通过 / $fail 失败 =="
} | tee "$SUMMARY"

[ "$fail" -eq 0 ]
