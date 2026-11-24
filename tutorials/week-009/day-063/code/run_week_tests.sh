#!/usr/bin/env bash
# run_week_tests.sh —— 第 63 天产出之一：第 9 周「全部测试」一键复跑。
#
# 范围：Day 57–62 的六套验收测试 + 今天（Day 63）的复盘测试。
# 输出：屏幕打印汇总表；每套测试的完整日志存 outputs/week_tests/day-XXX.txt。
#
# 用法：bash run_week_tests.sh   （在 day-063/code/ 目录下）

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs/week_tests"
mkdir -p "$OUT"

DAYS="057 058 059 060 061 062 063"

printf "%-6s %-22s %-12s %-8s\n" "Day" "测试文件" "结果" "退出码"
printf "%s\n" "-------------------------------------------------------------"

sum_pass=0
sum_fail=0
sum_skip=0
all_ok=1

for d in $DAYS; do
  if [ "$d" = "063" ]; then
    day_dir="$HERE"
  else
    day_dir="$HERE/../../day-$d/code"
  fi
  f="$(ls "$day_dir"/test_*.py 2>/dev/null | head -1)"
  if [ -z "$f" ]; then
    printf "%-6s %-22s %-12s\n" "$d" "(未找到)" "SKIP"
    continue
  fi
  fname="$(basename "$f")"
  log="$OUT/day-$d.txt"
  ( cd "$day_dir" && python3 "$fname" ) > "$log" 2>&1
  code=$?
  np=$(grep -cE '^[[:space:]]*\[PASS\]' "$log" || true)
  nf=$(grep -cE '^[[:space:]]*\[FAIL\]' "$log" || true)
  ns=$(grep -cE '^[[:space:]]*\[SKIP\]' "$log" || true)
  verdict="$np PASS"
  [ "$nf" -gt 0 ] 2>/dev/null && verdict="$verdict, $nf FAIL"
  [ "$ns" -gt 0 ] 2>/dev/null && verdict="$verdict, $ns SKIP"
  if [ "$code" -ne 0 ] || [ "$nf" -gt 0 ]; then
    all_ok=0
    verdict="$verdict ✗"
  fi
  printf "%-6s %-22s %-12s %-8s\n" "$d" "$fname" "$verdict" "$code"
  sum_pass=$((sum_pass + np))
  sum_fail=$((sum_fail + nf))
  sum_skip=$((sum_skip + ns))
done

printf "%s\n" "-------------------------------------------------------------"
total=$((sum_pass + sum_fail + sum_skip))
echo "合计：$sum_pass PASS / $sum_fail FAIL / $sum_skip SKIP（共 $total 个测试点，7 套）"
if [ "$all_ok" -eq 1 ]; then
  echo "第 9 周测试状态：全部通过 ✓"
else
  echo "第 9 周测试状态：有失败，见 outputs/week_tests/ 逐日日志"
fi
exit $((1 - all_ok))
