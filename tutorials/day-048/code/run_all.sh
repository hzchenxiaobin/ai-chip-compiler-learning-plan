#!/usr/bin/env bash
# 第 48 天（组合运行优化 Pass）一键重放：
#   1. 构建带 mini-combined 组合管道的 mini-opt
#   2. 正例 3 个（FileCheck）：主线 / 级联 / 冲突三局面
#   3. 负例 1 个（FileCheck）：+0.0 与混合零在组合管道后不许被消
#   4. 顺序对照：同一文件四种 Pass 顺序，mini.add 存亡对照
#   5. 不动点三连：max-iterations=0 vs 1 vs 10；幂等性；多轮救回
#   6. 量化对照：mini-count-ops 数优化前后的操作数
#   7. 上游 arith 探针：mlir-opt-18 的同一套级联行为
#   8. 中间 IR 打印：--mlir-print-ir-after-all 看错序管线的错过窗口
# 环境：Ubuntu 20.04、LLVM/MLIR 18.1.8（mlir-18-tools）、
#       cmake 3.20.5 + Ninja、g++ 9.4 —— 与 Day 29/37~47 记录一致
# 用法：bash run_all.sh              # 在本目录执行
#   构建目录默认 /tmp/day048/build，可用环境变量 DAY048_BUILD 覆盖
#   （例如 DAY048_BUILD=/tmp/opencode/day048-build bash run_all.sh）
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD="${DAY048_BUILD:-/tmp/day048/build}"
MINI_SRC="$HERE/mini"
MINI_OPT="$BUILD/bin/mini-opt"
FCK=$(command -v FileCheck-18 || command -v FileCheck)

mkdir -p "$(dirname "$BUILD")"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

run_check() {  # run_check <extra-args> <file>：mini-opt 跑文件，输出交 FileCheck
  local args=$1 f=$2
  if "$MINI_OPT" $args "$HERE/$f" 2>&1 | "$FCK" "$HERE/$f"; then
    echo "[$f] FileCheck 通过 (rc=0)"
  else
    echo "[$f] FileCheck 失败 (rc=$?)"
  fi
}

count_op() {  # count_op <extra-args> <file> <op-name>：数输出里某种 op 的行数
  local args=$1 f=$2 op=$3
  "$MINI_OPT" $args "$HERE/$f" 2>/dev/null | grep -c "$op" || true
}

banner "0/8 环境检查"
mlir-opt-18 --version | head -1
cmake --version | head -1
ninja --version
g++ --version | head -1

banner "1/8 构建：带 mini-combined 组合管道的 mini-opt（首次约 1~3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
cmake --build "$BUILD"

banner "1b/8 改动半径收据（相对 Day 47 的 mini 工程）"
if [ -d "$HERE/../../day-047/code/mini" ]; then
  diff -rq "$HERE/../../day-047/code/mini" "$MINI_SRC" || true
fi

banner "2/8 正例：主线（四种机会全兑现）/ 级联（一趟到底）/ 冲突三局面"
run_check -mini-combined combo_main.mlir
run_check -canonicalize cascade_chain.mlir
run_check -canonicalize conflict_regimes.mlir

banner "3/8 负例：+0.0 与混合零 bias，组合管道后 add 必须留存"
run_check -mini-combined guard_survives.mlir

banner "4/8 顺序对照：combo_main 四种 Pass 顺序的 mini.add 存亡"
echo "--- (a) -canonicalize：bias 折了、add 被类型护栏拦下（mini.add 行数应为 1）---"
count_op "-canonicalize" combo_main.mlir "mini.add"
echo "--- (b) -mini-combined：正确顺序，全消（mini.add 行数应为 0）---"
count_op "-mini-combined" combo_main.mlir "mini.add"
echo "--- (c) -canonicalize -mini-infer-shape：窗口错过（应为 1）---"
count_op "-canonicalize -mini-infer-shape" combo_main.mlir "mini.add"
echo "--- (d) -canonicalize -mini-infer-shape -canonicalize：手动多轮救回（应为 0）---"
count_op "-canonicalize -mini-infer-shape -canonicalize" combo_main.mlir "mini.add"
echo "--- (e) 等价性：-mini-combined 与 -mini-infer-shape -canonicalize 输出 diff---"
if diff <("$MINI_OPT" -mini-combined "$HERE/combo_main.mlir" 2>/dev/null) \
        <("$MINI_OPT" -mini-infer-shape -canonicalize "$HERE/combo_main.mlir" 2>/dev/null) >/dev/null; then
  echo "逐字节相同：mini-combined 就是注册成名字的那串命令行"
else
  echo "输出不同（异常！）"
fi
echo "--- (d) 救回后的 IR 与 (b) 全消后的 IR diff---"
if diff <("$MINI_OPT" -canonicalize -mini-infer-shape -canonicalize "$HERE/combo_main.mlir" 2>/dev/null) \
        <("$MINI_OPT" -mini-combined "$HERE/combo_main.mlir" 2>/dev/null) >/dev/null; then
  echo "逐字节相同：多轮救回到达与正确顺序相同的不动点"
else
  echo "输出不同（异常！）"
fi

banner "5/8 不动点三连：迭代预算 / 幂等性 / 多轮救回"
echo "--- (i) max-iterations=0：零轮预算，IR 一个字节不许动 ---"
"$MINI_OPT" --pass-pipeline='builtin.module(canonicalize{max-iterations=0})' "$HERE/cascade_chain.mlir" 2>/dev/null | grep -c "mini.add" || true
echo "    ↑ mini.add 行数（应仍为 4：零轮 = 零工作）"
echo "--- (ii) max-iterations=1：与默认 10 轮对照 ---"
if diff <("$MINI_OPT" --pass-pipeline='builtin.module(canonicalize{max-iterations=1})' "$HERE/cascade_chain.mlir" 2>/dev/null) \
        <("$MINI_OPT" --pass-pipeline='builtin.module(canonicalize)' "$HERE/cascade_chain.mlir" 2>/dev/null) >/dev/null; then
  echo "逐字节相同：删减型级联在 1 轮工作表排空里就到底"
else
  echo "输出不同（max-iterations 有可观察差异）"
fi
echo "--- (iii) 幂等性：-mini-combined 跑两遍 vs 一遍 ---"
if diff <("$MINI_OPT" -mini-combined -mini-combined "$HERE/combo_main.mlir" 2>/dev/null) \
        <("$MINI_OPT" -mini-combined "$HERE/combo_main.mlir" 2>/dev/null) >/dev/null; then
  echo "逐字节相同：第二遍空转——这就是『稳定 IR』的可操作定义"
else
  echo "输出不同（异常！第二遍还在改 IR）"
fi
echo "--- (iv) 单独跑 -canonicalize 两遍（无推导可做的场景）---"
if diff <("$MINI_OPT" -canonicalize -canonicalize "$HERE/cascade_chain.mlir" 2>/dev/null) \
        <("$MINI_OPT" -canonicalize "$HERE/cascade_chain.mlir" 2>/dev/null) >/dev/null; then
  echo "逐字节相同"
else
  echo "输出不同（异常！）"
fi

banner "6/8 量化对照：mini-count-ops 数优化前后的操作数"
echo "--- 优化前（-mini-count-ops 在管道前面跑）---"
"$MINI_OPT" -mini-count-ops -mini-combined "$HERE/combo_main.mlir" 2>&1 | grep "remark:" | sed 's/^.*remark: /remark: /'
echo "--- 优化后（-mini-count-ops 在管道后面跑）---"
"$MINI_OPT" -mini-combined -mini-count-ops "$HERE/combo_main.mlir" 2>&1 | grep "remark:" | sed 's/^.*remark: /remark: /'

banner "7/8 上游 arith 探针：mlir-opt-18 的级联折叠"
if mlir-opt-18 -canonicalize "$HERE/arith_cascade_probe.mlir" 2>&1 | "$FCK" "$HERE/arith_cascade_probe.mlir"; then
  echo "[arith_cascade_probe.mlir] FileCheck 通过 (rc=0)"
else
  echo "[arith_cascade_probe.mlir] FileCheck 失败 (rc=$?)"
fi

banner "8/8 中间 IR：错序管线的错过窗口（--mlir-print-ir-after-all）"
echo "--- 快照一：canonicalize 之后（bias 已折成 -0.0 常量，add 被 ?x2 拦下）---"
"$MINI_OPT" -canonicalize -mini-infer-shape --mlir-print-ir-after-all "$HERE/combo_main.mlir" 2>&1 \
  | sed -n '/IR Dump After Canonicalizer/,/^}/p'
echo "--- 快照二：infer-shape 之后（matmul 已是 2x2，但 add 留着——"
echo "    类型护栏放行的时机已经出现，却再没有驱动回头看它。）"
"$MINI_OPT" -canonicalize -mini-infer-shape --mlir-print-ir-after-all "$HERE/combo_main.mlir" 2>&1 \
  | sed -n '/IR Dump After.*ShapeInferencePass/,/^}/p'
