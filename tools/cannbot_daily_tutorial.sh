#!/usr/bin/env bash
# 使用 ai-compiler-daily-tutorial Skill 串行编写每日教程
# 默认补全第 001～168 天缺失或不完整的教程，也可指定只编写某一天：
#   ./cannbot_daily_tutorial.sh
#   ./cannbot_daily_tutorial.sh 45
# 在可信环境中需要自动批准 cannbot 工具权限时：
#   CANNBOT_AUTO_APPROVE=1 ./cannbot_daily_tutorial.sh 45
# 可通过 MAX_ATTEMPTS 调整重试次数，日志默认保存在 build/cannbot_daily_tutorial/。
set -uo pipefail

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
PLAN="$WORKDIR/AI芯片编译器学习计划.md"
SKILL="$WORKDIR/skills/ai-compiler-daily-tutorial/SKILL.md"
TUTORIAL_TOOL="$WORKDIR/skills/ai-compiler-daily-tutorial/scripts/tutorial_tools.py"
TUTORIAL_ROOT="$WORKDIR/tutorials"
MAX_DAY=168
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
CANNBOT_AUTO_APPROVE="${CANNBOT_AUTO_APPROVE:-0}"
LOG_BASE="${LOG_BASE:-$WORKDIR/build/cannbot_daily_tutorial}"

cd "$WORKDIR" || exit 1

for required_command in cannbot python3 tee; do
    if ! command -v "$required_command" > /dev/null 2>&1; then
        echo "错误：找不到 $required_command 命令" >&2
        exit 1
    fi
done

for required_file in "$PLAN" "$SKILL" "$TUTORIAL_TOOL"; do
    if [ ! -f "$required_file" ]; then
        echo "错误：找不到必需文件：$required_file" >&2
        exit 1
    fi
done

if [[ ! "$MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
    echo "错误：MAX_ATTEMPTS 必须是正整数" >&2
    exit 2
fi
if [ "$CANNBOT_AUTO_APPROVE" != "0" ] && [ "$CANNBOT_AUTO_APPROVE" != "1" ]; then
    echo "错误：CANNBOT_AUTO_APPROVE 只能设为 0 或 1" >&2
    exit 2
fi

if [ "$#" -gt 1 ]; then
    echo "用法：$0 [天数]" >&2
    exit 2
fi

if [ "$#" -eq 1 ]; then
    if [[ ! "$1" =~ ^[0-9]+$ ]]; then
        echo "错误：天数必须是数字" >&2
        exit 2
    fi
    DAY_NUMBER=$((10#$1))
    if [ "$DAY_NUMBER" -lt 1 ] || [ "$DAY_NUMBER" -gt "$MAX_DAY" ]; then
        echo "错误：天数必须在 1～$MAX_DAY 之间" >&2
        exit 2
    fi
    DAYS=("$DAY_NUMBER")
else
    mapfile -t DAYS < <(seq 1 "$MAX_DAY")
fi

RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
LOG_DIR="$LOG_BASE/$RUN_ID"
if ! mkdir -p "$LOG_DIR"; then
    echo "错误：无法创建日志目录：$LOG_DIR" >&2
    exit 1
fi

CANNBOT_OPTIONS=(--print-logs --log-level WARN)
if [ "$CANNBOT_AUTO_APPROVE" -eq 1 ]; then
    CANNBOT_OPTIONS+=(--dangerously-skip-permissions)
    echo ">>> 警告：已启用 cannbot 工具权限自动批准"
fi
echo ">>> 本次运行日志：$LOG_DIR"

FAILED_DAYS=()
GENERATED_COUNT=0

for day in "${DAYS[@]}"; do
    DAY_ID="$(printf "%03d" "$day")"
    DAY_DIR="$TUTORIAL_ROOT/day-$DAY_ID"
    TUTORIAL="$DAY_DIR/README.md"

    echo
    echo "======== 第 $DAY_ID 天 ========"

    CHECK_OUTPUT="教程文件不存在：$TUTORIAL"
    if [ -f "$TUTORIAL" ]; then
        if CHECK_OUTPUT="$(python3 "$TUTORIAL_TOOL" check "$TUTORIAL" 2>&1)"; then
            echo ">>> 第 $DAY_ID 天教程已完整，跳过"
            continue
        fi
        echo ">>> 第 $DAY_ID 天教程已存在但未通过校验，将补全"
        printf '%s\n' "$CHECK_OUTPUT"
    fi

    BASE_MESSAGE="使用 $SKILL，根据 $PLAN 编写第 $day 天教程，保存到 $DAY_DIR/README.md。严格执行 Skill 的完整工作流程和质量底线，生成至少 3 张真实图片，其中至少 2 张是技术信息图。SVG 统一采用手绘 sketch 风（Excalidraw-like）：线条自然且可略有抖动，笔触类似马克笔或铅笔，使用不超过 3～4 种柔和强调色及白色或米白色背景，以简单几何形状和手写感字体呈现，确保技术关系准确、文字清楚。提供可运行示例，能实际执行的要运行并记录真实结果。只处理第 $day 天，不要编写其他日期的教程。若教程或代码、图片已存在，请先检查并在现有成果上补全，不要重新开始或保留占位内容。尽早创建 README.md 并分段保存正文，不要在最后一次回复中才一次性写入全部内容。完成后运行 python3 $TUTORIAL_TOOL check $TUTORIAL 并确保检查通过。不要执行 Git 提交或推送。"

    COMPLETED=0
    PREVIOUS_STATUS="无"
    PREVIOUS_LOG="无"
    for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
        ATTEMPT_LOG="$LOG_DIR/day-$DAY_ID-attempt-$attempt.log"
        MESSAGE="$BASE_MESSAGE"
        if [ "$attempt" -gt 1 ]; then
            MESSAGE="$BASE_MESSAGE

上一次尝试未完成，不要重复相同操作。先读取上次日志并检查已有文件，从断点继续；若上次因输出长度中断，请分成更小的步骤写入文件。
上次 cannbot 退出码：$PREVIOUS_STATUS
上次日志：$PREVIOUS_LOG
上次校验结果：
$CHECK_OUTPUT"
        fi

        echo ">>> 第 $attempt/$MAX_ATTEMPTS 次尝试，日志：$ATTEMPT_LOG"
        cannbot run "${CANNBOT_OPTIONS[@]}" "$MESSAGE" 2>&1 | tee "$ATTEMPT_LOG"
        COMMAND_PIPE_STATUS=("${PIPESTATUS[@]}")
        CANNBOT_STATUS="${COMMAND_PIPE_STATUS[0]}"
        if [ "${COMMAND_PIPE_STATUS[1]}" -ne 0 ]; then
            echo ">>> 警告：日志写入失败，请检查磁盘空间和日志目录权限" >&2
        fi

        CHECK_OUTPUT="教程文件不存在：$TUTORIAL"
        if [ -f "$TUTORIAL" ]; then
            if CHECK_OUTPUT="$(python3 "$TUTORIAL_TOOL" check "$TUTORIAL" 2>&1)"; then
                printf '%s\n' "$CHECK_OUTPUT" | tee -a "$ATTEMPT_LOG"
                echo ">>> 第 $DAY_ID 天教程完成，已确认通过校验"
                COMPLETED=1
                GENERATED_COUNT=$((GENERATED_COUNT + 1))
                break
            fi
        fi
        printf '>>> 校验结果：\n%s\n' "$CHECK_OUTPUT" | tee -a "$ATTEMPT_LOG"

        if [ "$CANNBOT_STATUS" -ne 0 ]; then
            echo ">>> 警告：cannbot 执行失败（退出码 $CANNBOT_STATUS），且教程尚未通过校验" >&2
        else
            echo ">>> 警告：cannbot 已退出，但教程尚未通过校验" >&2
        fi
        if [ "$CANNBOT_AUTO_APPROVE" -eq 0 ] && grep -q "The user rejected permission" "$ATTEMPT_LOG"; then
            echo ">>> 提示：检测到工具权限被拒绝。可调整权限配置，或在可信环境中使用 CANNBOT_AUTO_APPROVE=1 重跑这一天。" >&2
        fi

        PREVIOUS_STATUS="$CANNBOT_STATUS"
        PREVIOUS_LOG="$ATTEMPT_LOG"
        if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
            echo ">>> 5 秒后重试"
            sleep 5
        fi
    done

    if [ "$COMPLETED" -eq 0 ]; then
        echo ">>> 警告：第 $DAY_ID 天连续 $MAX_ATTEMPTS 次均未完成，继续下一天" >&2
        FAILED_DAYS+=("$DAY_ID")
    fi
done

echo
if [ "$GENERATED_COUNT" -eq 0 ] && [ "${#FAILED_DAYS[@]}" -eq 0 ]; then
    echo ">>> 所有指定教程均已完整，无需生成"
elif [ "${#FAILED_DAYS[@]}" -eq 0 ]; then
    echo ">>> 教程编写完毕，本次完成 $GENERATED_COUNT 天"
else
    echo ">>> 教程编写结束，本次完成 $GENERATED_COUNT 天；失败日期：${FAILED_DAYS[*]}" >&2
    echo ">>> 失败详情见日志：$LOG_DIR" >&2
    exit 1
fi
echo ">>> 日志目录：$LOG_DIR"
