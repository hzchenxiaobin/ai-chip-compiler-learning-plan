#!/usr/bin/env bash
# 第 49 天（第 7 周复盘）实验重放脚本：一键重跑当天全部实验。
#
# 用法：
#   cmake -G Ninja -B /tmp/day049/build -S tutorials/day-049/code/mini \
#         -DCMAKE_BUILD_TYPE=Release -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
#   cmake --build /tmp/day049/build
#   bash tutorials/day-049/code/run_all.sh /tmp/day049/build/bin/mini-opt
#
# 所有结果写入 code/outputs/（与教程引用的编号一致），
# 脚本末尾自动做三组断言（全链 vs 默认、预算、组合 vs 推导+规范化）。

set -euo pipefail

MINI_OPT="${1:-/tmp/day049/build/bin/mini-opt}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/outputs"
mkdir -p "$OUT"
cd "$HERE"

P() { printf '\n===== %s =====\n' "$1"; }

# ---------------------------------------------------------------- 段 1：combo.mlir —— 三步接力
P "01 基线（解析+验证，不做任何优化）"
"$MINI_OPT" combo.mlir > "$OUT/01-baseline-combo.mlir"

P "02 只留 fold（三条 Pattern 全部禁用）"
"$MINI_OPT" --pass-pipeline='builtin.module(func.func(canonicalize{disable-patterns=mini-add-neg-zero,mini-mul-one,mini-double-relu}))' \
  combo.mlir > "$OUT/02-fold-only.mlir"

P "03 fold + 双 relu（禁用 add-neg-zero、mul-one）"
"$MINI_OPT" --pass-pipeline='builtin.module(func.func(canonicalize{disable-patterns=mini-add-neg-zero,mini-mul-one}))' \
  combo.mlir > "$OUT/03-fold-plus-double-relu.mlir"

P "04 fold + 乘一（禁用 add-neg-zero、double-relu）"
"$MINI_OPT" --pass-pipeline='builtin.module(func.func(canonicalize{disable-patterns=mini-add-neg-zero,mini-double-relu}))' \
  combo.mlir > "$OUT/04-fold-plus-mul-one.mlir"

P "05 fold + 加负零（只 enable add-neg-zero）"
"$MINI_OPT" --pass-pipeline='builtin.module(func.func(canonicalize{enable-patterns=mini-add-neg-zero}))' \
  combo.mlir > "$OUT/05-fold-plus-add-neg-zero.mlir"

P "06 fold + 乘一 + 双 relu（enable mul-one,double-relu）"
"$MINI_OPT" --pass-pipeline='builtin.module(func.func(canonicalize{enable-patterns=mini-mul-one,mini-double-relu}))' \
  combo.mlir > "$OUT/06-fold-plus-mul-one-plus-double-relu.mlir"

P "07 默认 -canonicalize（不过滤）"
"$MINI_OPT" -canonicalize combo.mlir > "$OUT/07-all-default.mlir"

P "13 预算实验：每轮最多 1 次 Pattern 重写"
"$MINI_OPT" --pass-pipeline='builtin.module(func.func(canonicalize{max-num-rewrites=1}))' \
  combo.mlir > "$OUT/13-budget-one-rewrite.mlir"

P "20 括号陷阱：enable-patterns=[mini-mul-one]（带方括号）"
"$MINI_OPT" --pass-pipeline='builtin.module(func.func(canonicalize{enable-patterns=[mini-mul-one]}))' \
  combo.mlir > "$OUT/20-brackets-trap.mlir"

# ------------------------------------------------- 段 2：combo_shape.mlir —— 信息关卡
P "10 只跑 -mini-infer-shape"
"$MINI_OPT" -mini-infer-shape combo_shape.mlir > "$OUT/10-infer-only.mlir"

P "11 只跑 -canonicalize"
"$MINI_OPT" -canonicalize combo_shape.mlir > "$OUT/11-canon-only.mlir"

P "12 先 -mini-infer-shape 再 -canonicalize"
"$MINI_OPT" -mini-infer-shape -canonicalize combo_shape.mlir > "$OUT/12-infer-then-canon.mlir"

# ------------------------------------------------------------ 段 3：mini-count-ops 计数
P "14/15 combo.mlir 计数：优化前 vs 推导+规范化后"
"$MINI_OPT" -mini-count-ops combo.mlir > "$OUT/14-count-baseline.txt" 2>&1
"$MINI_OPT" -mini-infer-shape -canonicalize -mini-count-ops combo.mlir > "$OUT/15-count-after-canon.txt" 2>&1

P "16/17/18 combo_shape.mlir 计数：基线 / 只规范化 / 推导+规范化"
"$MINI_OPT" -mini-count-ops combo_shape.mlir > "$OUT/16-count-shape-baseline.txt" 2>&1
"$MINI_OPT" -canonicalize -mini-count-ops combo_shape.mlir > "$OUT/17-count-shape-canon-only.txt" 2>&1
"$MINI_OPT" -mini-infer-shape -canonicalize -mini-count-ops combo_shape.mlir > "$OUT/18-count-shape-full.txt" 2>&1

# ------------------------------------------------------------ 段 4：断言（重放自检）
P "断言 A：全链 06 与默认 07 逐字节相同（工作清单自动接力）"
diff "$OUT/06-fold-plus-mul-one-plus-double-relu.mlir" "$OUT/07-all-default.mlir" \
  && echo "A 通过：06 == 07"

P "断言 B：预算 13 与默认 07 逐字节相同（预算只拆轮，不砍结果）"
diff "$OUT/13-budget-one-rewrite.mlir" "$OUT/07-all-default.mlir" \
  && echo "B 通过：13 == 07"

P "断言 C：括号陷阱 20 与只 fold 02 逐字节相同（enable 侧整体失效）"
diff "$OUT/20-brackets-trap.mlir" "$OUT/02-fold-only.mlir" \
  && echo "C 通过：20 == 02"

P "断言 D：四个计数 remark 与教程数字一致（8→3，9→6/4）"
grep -h "remark:" "$OUT/14-count-baseline.txt" "$OUT/15-count-after-canon.txt" \
  "$OUT/16-count-shape-baseline.txt" "$OUT/17-count-shape-canon-only.txt" \
  "$OUT/18-count-shape-full.txt"

P "断言 E：括号陷阱的不对称——disable 侧带括号 = 谁也没关"
diff <("$MINI_OPT" --pass-pipeline='builtin.module(func.func(canonicalize{disable-patterns=[mini-mul-one,mini-double-relu]}))' combo.mlir) \
     "$OUT/07-all-default.mlir" \
  && echo "E 通过：disable-patterns=[...] 与默认逐字节相同（过滤失效）"

P "全部重放完成：outputs/ 下 17 个文件已刷新"
