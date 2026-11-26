#!/usr/bin/env bash
# 使用 cannbot 串行为每周计划页补充总结和总览图。
# 默认处理第 001～024 周，也可只处理某一周：
#   ./cannbot_weekly_overview.sh
#   ./cannbot_weekly_overview.sh 1
# 在可信环境中需要自动批准 cannbot 工具权限时：
#   CANNBOT_AUTO_APPROVE=1 ./cannbot_weekly_overview.sh 1
# 可通过 MAX_ATTEMPTS 调整重试次数，日志默认保存在 build/cannbot_weekly_overview/。
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLAN="$ROOT_DIR/AI芯片编译器学习计划.md"
BUILD_TOOL="$ROOT_DIR/tools/build.py"
CHECK_TOOL="$ROOT_DIR/tools/weekly_overview_tools.py"
TUTORIAL_ROOT="$ROOT_DIR/tutorials"
MAX_WEEK=24
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
CANNBOT_AUTO_APPROVE="${CANNBOT_AUTO_APPROVE:-0}"
LOG_BASE="${LOG_BASE:-$ROOT_DIR/build/cannbot_weekly_overview}"

cd "$ROOT_DIR" || exit 1

for required_command in cannbot python3 tee; do
    if ! command -v "$required_command" > /dev/null 2>&1; then
        echo "错误：找不到 $required_command 命令" >&2
        exit 1
    fi
done

for required_file in "$PLAN" "$BUILD_TOOL" "$CHECK_TOOL"; do
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
    echo "用法：$0 [周数]" >&2
    exit 2
fi

if [ "$#" -eq 1 ]; then
    if [[ ! "$1" =~ ^[0-9]+$ ]]; then
        echo "错误：周数必须是数字" >&2
        exit 2
    fi
    WEEK_NUMBER=$((10#$1))
    if [ "$WEEK_NUMBER" -lt 1 ] || [ "$WEEK_NUMBER" -gt "$MAX_WEEK" ]; then
        echo "错误：周数必须在 1～$MAX_WEEK 之间" >&2
        exit 2
    fi
    WEEKS=("$WEEK_NUMBER")
else
    mapfile -t WEEKS < <(seq 1 "$MAX_WEEK")
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

FAILED_WEEKS=()
GENERATED_COUNT=0

for week in "${WEEKS[@]}"; do
    WEEK_ID="$(printf "%03d" "$week")"
    WEEK_DIR="$TUTORIAL_ROOT/week-$WEEK_ID"
    OVERVIEW="$WEEK_DIR/overview.md"
    OVERVIEW_IMAGE="$WEEK_DIR/images/week-overview.svg"

    echo
    echo "======== 第 $WEEK_ID 周 ========"

    if CHECK_OUTPUT="$(python3 "$CHECK_TOOL" "$WEEK_DIR" 2>&1)"; then
        echo ">>> 第 $WEEK_ID 周概览已完整，跳过"
        continue
    fi
    if [ -f "$OVERVIEW" ] || [ -f "$OVERVIEW_IMAGE" ]; then
        echo ">>> 第 $WEEK_ID 周已有部分成果但未通过校验，将就地补全"
        printf '%s\n' "$CHECK_OUTPUT"
    else
        echo ">>> 第 $WEEK_ID 周尚未生成概览"
    fi

    BASE_MESSAGE="为 AI 芯片编译器学习计划补充第 $week 周的周概览，只处理这一周。权威计划位于 $PLAN；先读取第 $week 周标题、七天的学习/实践/产出，再阅读 $WEEK_DIR 下对应的每日 README.md 了解实际教程内容，必要时查看前一周和后一周标题以把握承上启下。创建 $OVERVIEW 和 $OVERVIEW_IMAGE，不修改总计划、每日教程、构建脚本或其他周的内容。

$OVERVIEW 必须严格只有两个 Markdown 段落：第一段是一个 80～400 字（去空白计）的中文自然段，不加标题、列表或引用；第二段是 ![能准确概括本周内容的替代文本](images/week-overview.svg)。总结要通俗易懂，说明本周为什么重要、七天内容如何围绕一条主线逐步推进、最终形成什么能力或产物；不得编造已完成的学习效果、实验数据或性能结论。

$OVERVIEW_IMAGE 必须是真实、可编辑、可独立打开的技术总览 SVG，建议 1200×675 或相近的 16:9 尺寸。图中应准确呈现本周主题、关键概念之间的关系、七天学习的阶段推进和核心产出，不要只是把七个日标题机械排列，也不要复用每日教程里的图片。采用与现有教程一致的手绘 sketch 风（Excalidraw-like）：白色或米白背景，不超过 3～4 种柔和强调色，简单几何图形和箭头，线条可略有手绘抖动；中文优先使用楷体等可读字体，文字不得重叠、溢出或被裁切。不得使用外部图片、Mermaid 源码、ASCII 图、占位符或装饰性图片替代技术总览图。

尽早创建文件并保存，不要在最终回复中才一次性给出内容。完成后运行 python3 $CHECK_TOOL $WEEK_DIR 和 python3 $BUILD_TOOL，确保概览校验与整站构建都通过，并检查生成页面中内容顺序为总结、总览图、每日计划。不要执行 Git 提交或推送。"

    COMPLETED=0
    PREVIOUS_STATUS="无"
    PREVIOUS_LOG="无"
    for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
        ATTEMPT_LOG="$LOG_DIR/week-$WEEK_ID-attempt-$attempt.log"
        MESSAGE="$BASE_MESSAGE"
        if [ "$attempt" -gt 1 ]; then
            MESSAGE="$BASE_MESSAGE

上一次尝试未完成，不要重复相同操作。先读取上次日志并检查已有文件，从断点继续；若图片文字布局有问题，只调整有问题的元素，不要重做全部内容。
上次 cannbot 退出码：$PREVIOUS_STATUS
上次日志：$PREVIOUS_LOG
上次校验或构建结果：
$CHECK_OUTPUT"
        fi

        echo ">>> 第 $attempt/$MAX_ATTEMPTS 次尝试，日志：$ATTEMPT_LOG"
        cannbot run "${CANNBOT_OPTIONS[@]}" "$MESSAGE" 2>&1 | tee "$ATTEMPT_LOG"
        COMMAND_PIPE_STATUS=("${PIPESTATUS[@]}")
        CANNBOT_STATUS="${COMMAND_PIPE_STATUS[0]}"
        if [ "${COMMAND_PIPE_STATUS[1]}" -ne 0 ]; then
            echo ">>> 警告：日志写入失败，请检查磁盘空间和日志目录权限" >&2
        fi

        BUILD_OUTPUT=""
        if CHECK_OUTPUT="$(python3 "$CHECK_TOOL" "$WEEK_DIR" 2>&1)"; then
            if BUILD_OUTPUT="$(python3 "$BUILD_TOOL" 2>&1)"; then
                printf '%s\n%s\n' "$CHECK_OUTPUT" "$BUILD_OUTPUT" | tee -a "$ATTEMPT_LOG"
                echo ">>> 第 $WEEK_ID 周概览完成，已确认校验和整站构建通过"
                COMPLETED=1
                GENERATED_COUNT=$((GENERATED_COUNT + 1))
                break
            fi
            CHECK_OUTPUT="$CHECK_OUTPUT
整站构建失败：
$BUILD_OUTPUT"
        fi
        printf '>>> 校验或构建结果：\n%s\n' "$CHECK_OUTPUT" | tee -a "$ATTEMPT_LOG"

        if [ "$CANNBOT_STATUS" -ne 0 ]; then
            echo ">>> 警告：cannbot 执行失败（退出码 $CANNBOT_STATUS），且周概览尚未完成" >&2
        else
            echo ">>> 警告：cannbot 已退出，但周概览尚未通过校验和构建" >&2
        fi
        if [ "$CANNBOT_AUTO_APPROVE" -eq 0 ] && grep -q "The user rejected permission" "$ATTEMPT_LOG"; then
            echo ">>> 提示：检测到工具权限被拒绝。可调整权限配置，或在可信环境中使用 CANNBOT_AUTO_APPROVE=1 重跑这一周。" >&2
        fi

        PREVIOUS_STATUS="$CANNBOT_STATUS"
        PREVIOUS_LOG="$ATTEMPT_LOG"
        if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
            echo ">>> 5 秒后重试"
            sleep 5
        fi
    done

    if [ "$COMPLETED" -eq 0 ]; then
        echo ">>> 警告：第 $WEEK_ID 周连续 $MAX_ATTEMPTS 次均未完成，继续下一周" >&2
        FAILED_WEEKS+=("$WEEK_ID")
    fi
done

echo
if [ "$GENERATED_COUNT" -eq 0 ] && [ "${#FAILED_WEEKS[@]}" -eq 0 ]; then
    echo ">>> 所有指定周概览均已完整，无需生成"
elif [ "${#FAILED_WEEKS[@]}" -eq 0 ]; then
    echo ">>> 周概览编写完毕，本次完成 $GENERATED_COUNT 周"
else
    echo ">>> 周概览编写结束，本次完成 $GENERATED_COUNT 周；失败周数：${FAILED_WEEKS[*]}" >&2
    echo ">>> 失败详情见日志：$LOG_DIR" >&2
    exit 1
fi
echo ">>> 日志目录：$LOG_DIR"
