#!/usr/bin/env bash
# 第 13 天对照实验：同一个模型，权重放两种位置（weights vs inputs）。
# 真实执行、全程留日志（weight-position.log）：
#   变体 A：bias 进 weights（initializer）→ lower 成 Constant 节点；
#   变体 B：bias 进 inputs（图输入）  → 运行期由解释器 bind 提供。
# 观察点：IR 差一行、verify 双 PASS、数字相同、合同不同。
set -uo pipefail
cd "$(dirname "$0")"
LOG=weight-position.log

: > "$LOG"
mkdir -p /tmp/opencode
echo "第 13 天实验：权重放哪（$(date '+%Y-%m-%d %H:%M:%S')）" | tee -a "$LOG"
echo "环境：$(g++ --version | head -1) · $(uname -m)" | tee -a "$LOG"
echo | tee -a "$LOG"

echo "===== 编译 weight_position_ab.cpp =====" | tee -a "$LOG"
if g++ -std=c++17 -g -I ../src ../src/Graph.cpp ../src/Interpreter.cpp \
    ../src/Verifier.cpp ../src/Frontend.cpp weight_position_ab.cpp \
    -o /tmp/opencode/weight_position_ab 2>&1 | tee -a "$LOG"; then
    echo "----- 运行 ./weight_position_ab -----" | tee -a "$LOG"
    /tmp/opencode/weight_position_ab 2>&1 | tee -a "$LOG"
    echo "（退出码 ${PIPESTATUS[0]}）" | tee -a "$LOG"
else
    echo "编译失败" | tee -a "$LOG"
fi
echo | tee -a "$LOG"

echo "===== 两种 IR 的逐行 diff（只该差 bias 的来历行） =====" | tee -a "$LOG"
/tmp/opencode/weight_position_ab 2>/dev/null | awk '/^graph "A-/,/^}/' > /tmp/opencode/ir_a.txt
/tmp/opencode/weight_position_ab 2>/dev/null | awk '/^graph "B-/,/^}/' > /tmp/opencode/ir_b.txt
diff /tmp/opencode/ir_a.txt /tmp/opencode/ir_b.txt | tee -a "$LOG" || true
echo "日志已写入 $LOG"
