#!/usr/bin/env bash
# 使用 ai-compiler-daily-tutorial Skill 串行编写每日教程
# 默认补全第 001～168 天缺失或不完整的教程，也可指定只编写某一天：
#   ./cannbot_daily_tutorial.sh
#   ./cannbot_daily_tutorial.sh 45
set -uo pipefail

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
PLAN="$WORKDIR/AI芯片编译器学习计划.md"
SKILL="$WORKDIR/skills/ai-compiler-daily-tutorial/SKILL.md"
TUTORIAL_TOOL="$WORKDIR/skills/ai-compiler-daily-tutorial/scripts/tutorial_tools.py"
TUTORIAL_ROOT="$WORKDIR/tutorials"
MAX_DAY=168
MAX_ATTEMPTS=3

cd "$WORKDIR" || exit 1

if ! command -v cannbot > /dev/null 2>&1; then
    echo "错误：找不到 cannbot 命令" >&2
    exit 1
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

FAILED_DAYS=()
GENERATED_COUNT=0

for day in "${DAYS[@]}"; do
    DAY_ID="$(printf "%03d" "$day")"
    DAY_DIR="$TUTORIAL_ROOT/day-$DAY_ID"
    TUTORIAL="$DAY_DIR/README.md"

    echo
    echo "======== 第 $DAY_ID 天 ========"

    # 已通过校验的教程直接跳过；存在但不完整的教程会继续补全。
    if [ -f "$TUTORIAL" ] && python3 "$TUTORIAL_TOOL" check "$TUTORIAL" > /dev/null 2>&1; then
        echo ">>> 第 $DAY_ID 天教程已完整，跳过"
        continue
    fi

    if [ -f "$TUTORIAL" ]; then
        echo ">>> 第 $DAY_ID 天教程已存在但未通过校验，将补全"
    fi

    MESSAGE="使用 $SKILL，根据 $PLAN 编写第 $day 天教程，保存到 $DAY_DIR/README.md。严格执行 Skill 的完整工作流程和质量底线，生成至少 3 张真实图片，其中至少 2 张是技术信息图。SVG 统一采用手绘 sketch 风（Excalidraw-like）：线条自然且可略有抖动，笔触类似马克笔或铅笔，使用不超过 3～4 种柔和强调色及白色或米白色背景，以简单几何形状和手写感字体呈现，确保技术关系准确、文字清楚。提供可运行示例，能实际执行的要运行并记录真实结果。只处理第 $day 天，不要编写其他日期的教程。若教程已存在，请检查并补全，不要保留占位内容。完成后运行 python3 $TUTORIAL_TOOL check $TUTORIAL 并确保检查通过。不要执行 Git 提交或推送。"

    COMPLETED=0
    for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
        echo ">>> 第 $attempt/$MAX_ATTEMPTS 次尝试，发送: $MESSAGE"
        if cannbot run "$MESSAGE"; then
            CANNBOT_STATUS=0
        else
            CANNBOT_STATUS=$?
        fi

        if [ -f "$TUTORIAL" ] && python3 "$TUTORIAL_TOOL" check "$TUTORIAL"; then
            echo ">>> 第 $DAY_ID 天教程完成，已确认通过校验"
            COMPLETED=1
            GENERATED_COUNT=$((GENERATED_COUNT + 1))
            break
        fi

        if [ "$CANNBOT_STATUS" -ne 0 ]; then
            echo ">>> 警告：cannbot 执行失败（退出码 $CANNBOT_STATUS），且教程尚未通过校验" >&2
        else
            echo ">>> 警告：cannbot 已退出，但教程尚未通过校验" >&2
        fi
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
    exit 1
fi
