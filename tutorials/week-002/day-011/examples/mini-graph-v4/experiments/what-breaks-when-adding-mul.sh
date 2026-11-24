#!/usr/bin/env bash
# 实验：新增一种算子（Mul）时，「switch 方案」和「Visitor 方案」各要改哪里、
#        谁替你抓漏。全程真实编译，输出同时记录到 experiments/what-breaks.log。
# 步骤：
#   0) 基线（未加 Mul）应当全绿；
#   1) 只给 OpKind 加 Mul（add-mul.patch）→ -Wswitch 警告三处开花，
#      但仍能编译通过（漏改的风险就此潜伏）；
#   2) 响应警告，给 NodeVisitor 补上 visit_mul 纯虚（add-mul-visit.patch）
#      → 编译错误，编译器逐个点名所有没实现的访问者——这就是修改清单；
#   3) 还原两个补丁 → 重新全绿。
# 用法：bash experiments/what-breaks-when-adding-mul.sh
set -u
cd "$(dirname "$0")/.."   # 回到 mini-graph-v4 根目录
BUILD=build-experiment
LOG=experiments/what-breaks.log
: > "$LOG"

run_build() {  # run_build <标题>
    echo "$1" | tee -a "$LOG"
    cmake --build "$BUILD" 2>&1 | tee -a "$LOG"
}

echo "== 步骤 0：基线（未加 Mul）==" | tee -a "$LOG"
cmake -S . -B "$BUILD" -G Ninja > /dev/null
run_build "（应当安静地全部编译通过）"
BASELINE_OK=$?

echo | tee -a "$LOG"
echo "== 步骤 1：只给 OpKind 加 Mul（experiments/add-mul.patch）==" | tee -a "$LOG"
patch -p1 --forward < experiments/add-mul.patch | tee -a "$LOG"
run_build "（看 -Wswitch 在哪里报警）" | grep -v "^\[" | head -30

echo | tee -a "$LOG"
echo "== 步骤 2：响应警告——给 NodeVisitor 补上 visit_mul 纯虚 ==" | tee -a "$LOG"
echo "          （experiments/add-mul-visit.patch，同时给 apply_visitor 加 case）" | tee -a "$LOG"
patch -p1 --forward < experiments/add-mul-visit.patch | tee -a "$LOG"
run_build "（这次应当编译失败：漏实现的访问者被逐个点名）" | grep -v "^\[" | head -40

echo | tee -a "$LOG"
echo "== 步骤 3：还原两个补丁，确认重新全绿 ==" | tee -a "$LOG"
patch -R -p1 < experiments/add-mul-visit.patch | tee -a "$LOG"
patch -R -p1 < experiments/add-mul.patch | tee -a "$LOG"
run_build "（应当重新全部通过）"
echo "实验完成，完整输出见 $LOG" | tee -a "$LOG"
