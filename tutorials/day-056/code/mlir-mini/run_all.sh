#!/usr/bin/env bash
# run_all.sh —— 第 56 天（第 8 周复盘）四站旅程的一键复跑。
# 用法: bash run_all.sh          （在 mlir-mini/ 目录下，先 ninja -C build）
# 输出: outputs/journey-summary.txt（每用例 stdout/stderr 另存 outputs/*.out/.err）
#
# 四个用例 = 一条主线路 + 三个对照：
#   main       默认顺序：验证 -> 推导 -> 折叠 -> 融合（8 -> 3）
#   skip-infer 对照 1：跳过推导站，观察「信息不齐，融合站卡住」（8 -> 5，? 残留）
#   shared     对照 2：加法结果被 return 共用 -> 半融合不动点（3 -> 2）
#   bad        对照 3：f64 输入在验证站被拦，旅程短路
# rc=0 全部通过（含 6 组文本断言）；rc=1 有失败。

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"
TOOL=./build/mini-journey
SUMMARY="$OUT/journey-summary.txt"

pass=0; fail=0

note() { echo "$@"; }

check() {  # check <描述> <命令...>（命令成功=断言通过）
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  断言 PASS: $desc"; pass=$((pass+1))
  else
    echo "  断言 FAIL: $desc"; fail=$((fail+1))
  fi
}

check_no() {  # check_no <描述> <命令...>（命令成功=断言失败；无匹配=通过）
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  断言 FAIL: $desc"; fail=$((fail+1))
  else
    echo "  断言 PASS: $desc"; pass=$((pass+1))
  fi
}

# 只取「阶段 4（融合后）」段落之后的文本，避免输入段误匹配
tail_after_fuse() {  # tail_after_fuse <file>
  sed -n '/^===== 阶段 4/,$p' "$1"
}

{
echo "第 56 天四站旅程汇总 —— $(date '+%Y-%m-%d %H:%M')"
echo "工具: $TOOL；环境: $(g++ --version | head -1)，"
echo "      $(/usr/lib/llvm-18/bin/mlir-opt --version | head -1)，aarch64 Linux"
echo "管道: 站1 parse+verify -> 站2 Shape 推导 -> 站3 fold+DCE -> 站4 融合"
echo "      （P1/P2/P51g/P3 让位版 + 类型闸门 + ? 护栏）"
echo

echo "== 主线：journey.mlir（默认顺序）=="
$TOOL inputs/journey.mlir --expect=fused >"$OUT/journey-main.out" 2>"$OUT/journey-main.err"
echo "  rc=$?（verdict=fused，8 -> 3）"
check "终点含 fused_matmul_bias_relu"    grep -q "mini.fused_matmul_bias_relu" "$OUT/journey-main.out"
check "终点含 fused_add_relu"            grep -q "mini.fused_add_relu" "$OUT/journey-main.out"
check "终点 3 个 mini.*（阶段 4 标题）"  grep -q "阶段 4: 融合后 IR（3 个 mini.*" "$OUT/journey-main.out"
check "阶段 4 之后无动态维 ?x2"          bash -c "! tail_after_fuse '$OUT/journey-main.out' | grep -q '?x2'"
check "日志含 P3 三算子融合"             grep -q "\[P3\] 匹配 MatMul + Add + Relu" "$OUT/journey-main.err"

echo
echo "== 对照 1：--skip-infer（信息不齐，融合站卡住）=="
$TOOL inputs/journey.mlir --skip-infer --expect=fused >"$OUT/journey-skip-infer.out" 2>"$OUT/journey-skip-infer.err"
echo "  rc=$?（verdict=fused，但大融合缺席：8 -> 5）"
check "终点仍含 ?x2（没人细化）"         grep -q "?x2" "$OUT/journey-skip-infer.out"
check_no "终点不含 fused_matmul_bias_relu"  grep -q "mini.fused_matmul_bias_relu" "$OUT/journey-skip-infer.out"
check "终点 5 个 mini.*"                 grep -q "阶段 4: 融合后 IR（5 个 mini.*" "$OUT/journey-skip-infer.out"
check "日志含 ? 护栏拒绝"                grep -q "乘积类型含动态维（?）-> 拒绝" "$OUT/journey-skip-infer.err"

echo
echo "== 对照 2：journey_shared.mlir（半融合不动点）=="
$TOOL inputs/journey_shared.mlir --expect=fused >"$OUT/journey-shared.out" 2>"$OUT/journey-shared.err"
echo "  rc=$?（verdict=fused，形态 = fused_matmul_bias + relu）"
check "终点含 fused_matmul_bias（两算子版）" grep -q "mini.fused_matmul_bias " "$OUT/journey-shared.out"
check_no "终点不含三算子版"                  grep -q "mini.fused_matmul_bias_relu" "$OUT/journey-shared.out"
check "日志含「不能吸收 Relu」"           grep -q "不能吸收 Relu" "$OUT/journey-shared.err"

echo
echo "== 对照 3：journey_bad.mlir（验证站拦截，短路）=="
$TOOL inputs/journey_bad.mlir --expect=verifier_reject >"$OUT/journey-bad.out" 2>"$OUT/journey-bad.err"
echo "  rc=$?（verdict=verifier_reject）"
check "验证站拦截 f64"                    grep -q "元素类型必须是 f32" "$OUT/journey-bad.err"
check "后续三站短路"                      grep -q "后续三站短路" "$OUT/journey-bad.out"

echo
echo "== 汇总: $pass 通过 / $fail 失败 =="
} | tee "$SUMMARY"

[ "$fail" -eq 0 ]
