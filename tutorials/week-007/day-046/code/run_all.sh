#!/usr/bin/env bash
# 第 46 天（代数化简 Pattern）一键重放：
#   1. 构建带 SimplifyAddNegZero / SimplifyMulOne 的 mini-opt
#   2. 正例 4 个（FileCheck）→ 负例 4 个（FileCheck）
#   3. 主线：pipeline_order 三种 Pass 顺序 + 非零 bias 回归
#   4. 上游 arith 探针：同样的恒等式，mlir-opt-18 怎么做
#   5. 对照实验 A：删掉类型护栏 → canonicalize 后过不了验证
#   6. 对照实验 B：isNegZero 换成 == 比较 → +0.0 被误消（负例失守）
#   7. numpy IEEE 见证：-0.0 / NaN / Inf 的真实算术
# 环境：Ubuntu 20.04 (aarch64)、LLVM/MLIR 18.1.8（mlir-18-tools）、
#       cmake 3.20.5 + Ninja、g++ 9.4、numpy 1.26.4 —— 与 Day 29/37~45 记录一致
# 用法：bash run_all.sh        # 在本目录执行；构建目录 /tmp/day046/ 下
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=/tmp/day046/build
MINI_SRC="$HERE/mini"
MINI_OPT="$BUILD/bin/mini-opt"
FCK=$(command -v FileCheck-18 || command -v FileCheck)

mkdir -p "$BUILD"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

# run_check <pass-args> <file>：mini-opt 跑 <file>，输出交 FileCheck 校验
run_check() {  # run_check <extra-args> <file>
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
python3 -c "import numpy; print('numpy', numpy.__version__)"

banner "1/8 构建：带代数化简 Pattern 的 mini-opt（首次约 1~3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
cmake --build "$BUILD"

banner "1b/8 改动半径收据（相对 Day 45 的 mini 工程）"
if [ -d "$HERE/../../day-045/code/mini" ]; then
  diff -rq "$HERE/../../day-045/code/mini" "$MINI_SRC" || true
fi

banner "2/8 正例：加 -0.0 两个方向 / 乘 1.0 两个方向 / 多使用者 / 洋葱剥壳"
run_check -canonicalize add_negzero_basic.mlir
run_check -canonicalize mul_one_basic.mlir
run_check -canonicalize add_zero_multi_user.mlir
run_check -canonicalize cascade_onion.mlir

banner "3/8 负例：+0.0 / 入口参数 / 非 splat / 乘 0 / 类型护栏（IR 一律不许变）"
run_check -canonicalize add_zero_safety.mlir
run_check -canonicalize add_nonsplat_safety.mlir
run_check -canonicalize mul_zero_safety.mlir
run_check -canonicalize type_guard_negative.mlir

banner "4/8 主线：pipeline_order 三种顺序 + 非零 bias 回归"
echo "--- (a) -canonicalize：护栏拦下，add 留存（mini.add 行数应为 1）---"
count_op "-canonicalize" pipeline_order.mlir "mini.add"
echo "--- (b) -mini-infer-shape -canonicalize：add 消失（mini.add 行数应为 0）---"
count_op "-mini-infer-shape -canonicalize" pipeline_order.mlir "mini.add"
run_check "-mini-infer-shape -canonicalize" pipeline_order.mlir
echo "--- (c) -canonicalize -mini-infer-shape：顺序换了，优化丢了（应为 1）---"
count_op "-canonicalize -mini-infer-shape" pipeline_order.mlir "mini.add"
echo "--- 回归：非零 bias 的 add 不许动（FileCheck 应通过）---"
run_check "-mini-infer-shape -canonicalize" pipeline_bias_nonzero.mlir

banner "5/8 上游 arith 探针：同样的恒等式，mlir-opt-18 -canonicalize 怎么做"
echo "--- 输出里每种算子各剩几个（0 表示被上游消掉）---"
for op in addf mulf addi; do
  printf '%-6s %s\n' "$op" "$(mlir-opt-18 -canonicalize "$HERE/arith_probe.mlir" 2>/dev/null | grep -c "arith.$op" || true)"
done

banner "6/8 对照实验 A：删掉类型护栏，guard 用例会怎样"
NOGUARD_SRC=/tmp/day046-noguard-src
NOGUARD_BUILD=/tmp/day046-noguard/build
rm -rf "$NOGUARD_SRC" && mkdir -p "$NOGUARD_SRC"
cp -r "$MINI_SRC" "$NOGUARD_SRC/mini"
python3 - "$NOGUARD_SRC/mini" <<'PY'
import sys, pathlib
cpp = pathlib.Path(sys.argv[1]) / "lib/AlgebraicSimplification.cpp"
text = cpp.read_text()
for guard in (
    "    if (x.getType() != add.getRes().getType())\n      return failure();\n\n",
    "    if (x.getType() != mul.getRes().getType())\n      return failure();\n\n",
):
    assert guard in text, "guard snippet not found"
    text = text.replace(guard, "")
cpp.write_text(text)
print("已删除两处类型护栏（SimplifyAddNegZero / SimplifyMulOne）")
PY
cmake -G Ninja -B "$NOGUARD_BUILD" -S "$NOGUARD_SRC/mini" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir > /dev/null
cmake --build "$NOGUARD_BUILD" > /dev/null
echo "--- 无护栏 mini-opt -canonicalize type_guard_negative.mlir（应报验证错误）---"
"$NOGUARD_BUILD/bin/mini-opt" -canonicalize "$HERE/type_guard_negative.mlir"; echo "rc=$?"

banner "7/8 对照实验 B：isNegZero 换成 == 比较，负例会失守吗"
EQ_SRC=/tmp/day046-eqcmp-src
EQ_BUILD=/tmp/day046-eqcmp/build
rm -rf "$EQ_SRC" && mkdir -p "$EQ_SRC"
cp -r "$MINI_SRC" "$EQ_SRC/mini"
python3 - "$EQ_SRC/mini" <<'PY'
import sys, pathlib
cpp = pathlib.Path(sys.argv[1]) / "lib/AlgebraicSimplification.cpp"
text = cpp.read_text()
old = "static bool isNegZero(const llvm::APFloat &f) { return f.isNegZero(); }"
new = ("static bool isNegZero(const llvm::APFloat &f) {\n"
       "  return f == llvm::APFloat(-0.0f);\n"
       "}")
assert old in text, "isNegZero line not found"
cpp.write_text(text.replace(old, new))
print("已把 isNegZero 换成 == 比较（IEEE 语义：-0.0 == +0.0）")
PY
cmake -G Ninja -B "$EQ_BUILD" -S "$EQ_SRC/mini" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir > /dev/null
cmake --build "$EQ_BUILD" > /dev/null
echo "--- 正确版：add_zero_safety.mlir -canonicalize 后 mini.add 行数（应为 2）---"
"$MINI_OPT" -canonicalize "$HERE/add_zero_safety.mlir" 2>/dev/null | grep -c "mini.add" || true
echo "--- == 版：同文件同命令（若小于 2，说明 +0.0 被错误消掉了）---"
"$EQ_BUILD/bin/mini-opt" -canonicalize "$HERE/add_zero_safety.mlir" 2>/dev/null | grep -c "mini.add" || true

banner "8/8 numpy IEEE 见证：-0.0 / NaN / Inf 的真实算术"
python3 "$HERE/ieee_witness.py"
