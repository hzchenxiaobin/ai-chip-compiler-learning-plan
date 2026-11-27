#!/usr/bin/env bash
# 使用 cannbot 串行审阅每日教程，校对技术内容并按理解需要补充技术 SVG。
# 默认处理第 001～168 天，也可只处理某一天：
#   ./cannbot_tutorial_svg_review.sh
#   ./cannbot_tutorial_svg_review.sh 45
# 在可信环境中需要自动批准 cannbot 工具权限时：
#   CANNBOT_AUTO_APPROVE=1 ./cannbot_tutorial_svg_review.sh 45
# 可通过 MAX_ATTEMPTS 调整重试次数，日志默认保存在 build/cannbot_tutorial_svg_review/。
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$ROOT_DIR/skills/ai-compiler-daily-tutorial/SKILL.md"
TUTORIAL_TOOL="$ROOT_DIR/skills/ai-compiler-daily-tutorial/scripts/tutorial_tools.py"
BUILD_TOOL="$ROOT_DIR/tools/build.py"
REVIEW_TOOL="$ROOT_DIR/tools/tutorial_review_tools.py"
TUTORIAL_ROOT="$ROOT_DIR/tutorials"
MAX_DAY=168
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
CANNBOT_AUTO_APPROVE="${CANNBOT_AUTO_APPROVE:-0}"
LOG_BASE="${LOG_BASE:-$ROOT_DIR/build/cannbot_tutorial_svg_review}"
REVIEW_MARKER='<!-- tutorial-review: v1 -->'

cd "$ROOT_DIR" || exit 1

for required_command in cannbot python3 tee; do
    if ! command -v "$required_command" > /dev/null 2>&1; then
        echo "错误：找不到 $required_command 命令" >&2
        exit 1
    fi
done

for required_file in "$SKILL" "$TUTORIAL_TOOL" "$BUILD_TOOL" "$REVIEW_TOOL"; do
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
REVIEWED_COUNT=0
SKIPPED_COUNT=0

for day in "${DAYS[@]}"; do
    DAY_ID="$(printf "%03d" "$day")"
    WEEK_ID="$(printf "%03d" $(( (day - 1) / 7 + 1 )))"
    DAY_DIR="$TUTORIAL_ROOT/week-$WEEK_ID/day-$DAY_ID"
    TUTORIAL="$DAY_DIR/README.md"
    REVIEW_REPORT="$DAY_DIR/technical-review.md"

    echo
    echo "======== 第 $DAY_ID 天 ========"

    if [ ! -f "$TUTORIAL" ]; then
        echo ">>> 教程不存在，记录失败并继续：$TUTORIAL" >&2
        FAILED_DAYS+=("$DAY_ID")
        continue
    fi

    CHECK_OUTPUT=""
    BUILD_OUTPUT=""
    if grep -Fq "$REVIEW_MARKER" "$TUTORIAL"; then
        if CHECK_OUTPUT="$(
            python3 "$TUTORIAL_TOOL" check "$TUTORIAL" 2>&1 \
                && python3 "$REVIEW_TOOL" "$TUTORIAL" "$REVIEW_REPORT" 2>&1
        )" && BUILD_OUTPUT="$(python3 "$BUILD_TOOL" 2>&1)"; then
            echo ">>> 第 $DAY_ID 天已完成技术校对和 SVG 审阅且校验通过，跳过"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            continue
        fi
        echo ">>> 第 $DAY_ID 天已有审阅标记，但报告、图片校验或整站构建未通过，将重新处理"
        printf '%s\n%s\n' "${CHECK_OUTPUT:-}" "${BUILD_OUTPUT:-}"
    else
        echo ">>> 第 $DAY_ID 天等待技术校对、现有图片审阅和按需补充 SVG"
    fi

    BASE_MESSAGE="以一位有十年经验的 AI 芯片编译器工程师和评审者身份审阅第 $day 天教程，只处理 $DAY_DIR。完整阅读 $TUTORIAL、当天代码、真实输出和所有已引用 SVG，并参考 $SKILL。首要任务是找事实性错误，不做文字润色。

第一项任务是技术校对，逐项检查：1）IR、Pass、调度、Tiling 等概念定义和术语是否准确；2）技术论断是否有反例、过度推广或框架版本时效问题；3）代码示例的逻辑、编译运行、未定义行为和 API 用法是否正确属实；4）“因为 A 所以 B”的因果关系是否成立；5）是否遗漏初学者必知的关键坑。优先运行当天可行的代码和测试来核实判断；若会覆盖仓库冻结产物，就在临时目录运行并清理。涉及具体版本或 API 的存疑点应查官方文档或源码，不得凭印象编造依据；无法验证时明确说明。

校对意见只写入 $REVIEW_REPORT，不允许根据意见修改教程原文、代码或输出。报告按【错误】（明确技术错误，必须改）、【存疑】（可能过时或过于绝对，需核实）、【建议】（可改进但不影响正确性）分级。每条必须包含逐字原文引用和具体技术依据，不得只给笼统评价；没有把握时标注置信度及不确定点。报告固定使用以下格式，某级没有意见时写“- 无。”：

# 第 $day 天技术校对报告

## 【错误】
#### 1. 问题标题
- **原文**：“从 README 逐字复制的一行原文”
- **依据**：解释为什么错误，并给出核实依据
- **置信度**：高／中／低及必要说明

## 【存疑】
- 无。

## 【建议】
- 无。

每个发现使用递增的 #### 序号标题；三节都必须保留。原文引用必须是一行、加双引号且能在 README 中精确找到，依据必须非空。不要编造问题或把纯风格偏好列为错误。尽早创建报告并保存，不要只在最终回复中给意见。

第二项任务是技术配图审阅。逐节判断现有图片是否足以帮助理解；3 张只是最低要求，不是上限。只有在新增图能明显降低理解成本时才补充，通常新增 0～2 张，没有明显收益就不新增，不得为凑数量重复已有图或添加装饰图。

重点关注仅靠文字较难看清的内容：多阶段 IR／数据转换、Shape／Stride／内存布局、Use-Def／控制流／依赖关系、算子融合或 Lowering 前后对照、Tiling／生命周期／调度、异步时序，以及包含多个判断分支的实验和调试流程。简单命令、短列表和已有图已解释清楚的内容不必再画。

新增图片必须是 $DAY_DIR/images/ 下真实、可编辑、可独立解析的技术 SVG，从现有最大数字前缀继续命名，例如 04-data-layout.svg，不覆盖、不重编号已有文件。在最能帮助理解的小节插入相对链接、有意义的替代文本和图注；若影响图号顺序，同步修正受影响的图号和正文引用。不要重写教程、修改代码或冻结输出，不要改动其他教程、总计划、构建脚本或本批处理脚本。若已有图片链接或 SVG 本身无效，只做必要的最小修复。

SVG 与现有教程保持一致的手绘 sketch 风（Excalidraw-like），建议 1200×675 或相近 16:9 尺寸，白色或米白背景，不超过 3～4 种柔和强调色，使用简单几何图形和清楚的中文标签。技术关系、Shape、数值、单位、IR 与执行顺序必须同正文和真实输出一致；文字不得重叠、溢出或被裁切。不得使用外部图片、Mermaid 源码、ASCII 图或占位内容替代 SVG。

尽早保存文件，完成后运行 python3 $TUTORIAL_TOOL check $TUTORIAL、python3 $REVIEW_TOOL $TUTORIAL $REVIEW_REPORT 和 python3 $BUILD_TOOL，确认报告、图片与整站构建均通过。无论本次是否新增图片，只有两项审阅和全部校验完成后才在 $TUTORIAL 末尾追加一行 $REVIEW_MARKER（已存在则不要重复），用于后续断点续跑。不要执行 Git 提交或推送。"

    COMPLETED=0
    PREVIOUS_STATUS="无"
    PREVIOUS_LOG="无"
    CHECK_OUTPUT=""
    BUILD_OUTPUT=""
    for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
        ATTEMPT_LOG="$LOG_DIR/day-$DAY_ID-attempt-$attempt.log"
        MESSAGE="$BASE_MESSAGE"
        if [ "$attempt" -gt 1 ]; then
            MESSAGE="$BASE_MESSAGE

上一次尝试未完成，不要重复相同操作。先读取上次日志并检查已有文件，从断点继续；保留已经成立的校对意见，只修复报告格式、个别图片或链接问题。不要因为已经新增过图片就再次添加相同内容的图，也不要根据校对意见修改原文。
上次 cannbot 退出码：$PREVIOUS_STATUS
上次日志：$PREVIOUS_LOG
上次校验或构建结果：
$CHECK_OUTPUT
$BUILD_OUTPUT"
        fi

        echo ">>> 第 $attempt/$MAX_ATTEMPTS 次尝试，日志：$ATTEMPT_LOG"
        cannbot run "${CANNBOT_OPTIONS[@]}" "$MESSAGE" 2>&1 | tee "$ATTEMPT_LOG"
        COMMAND_PIPE_STATUS=("${PIPESTATUS[@]}")
        CANNBOT_STATUS="${COMMAND_PIPE_STATUS[0]}"
        if [ "${COMMAND_PIPE_STATUS[1]}" -ne 0 ]; then
            echo ">>> 警告：日志写入失败，请检查磁盘空间和日志目录权限" >&2
        fi

        CHECK_OUTPUT=""
        BUILD_OUTPUT=""
        if ! grep -Fq "$REVIEW_MARKER" "$TUTORIAL"; then
            CHECK_OUTPUT="缺少完成标记：$REVIEW_MARKER"
        elif ! CHECK_OUTPUT="$(python3 "$TUTORIAL_TOOL" check "$TUTORIAL" 2>&1)"; then
            :
        elif ! CHECK_OUTPUT="$(python3 "$REVIEW_TOOL" "$TUTORIAL" "$REVIEW_REPORT" 2>&1)"; then
            :
        elif BUILD_OUTPUT="$(python3 "$BUILD_TOOL" 2>&1)"; then
            printf '%s\n%s\n' "$CHECK_OUTPUT" "$BUILD_OUTPUT" | tee -a "$ATTEMPT_LOG"
            echo ">>> 第 $DAY_ID 天技术校对和 SVG 审阅完成，报告、图片校验和整站构建均通过"
            COMPLETED=1
            REVIEWED_COUNT=$((REVIEWED_COUNT + 1))
            break
        fi
        printf '>>> 校验或构建结果：\n%s\n%s\n' "$CHECK_OUTPUT" "$BUILD_OUTPUT" | tee -a "$ATTEMPT_LOG"

        if [ "$CANNBOT_STATUS" -ne 0 ]; then
            echo ">>> 警告：cannbot 执行失败（退出码 $CANNBOT_STATUS），且教程尚未完成审阅" >&2
        else
            echo ">>> 警告：cannbot 已退出，但教程尚未通过完整校验" >&2
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
if [ "${#FAILED_DAYS[@]}" -ne 0 ]; then
    echo ">>> 技术校对和 SVG 审阅结束：本次完成 $REVIEWED_COUNT 篇，跳过 $SKIPPED_COUNT 篇；失败日期：${FAILED_DAYS[*]}" >&2
    echo ">>> 失败详情见日志：$LOG_DIR" >&2
    exit 1
fi
if [ "$REVIEWED_COUNT" -eq 0 ]; then
    echo ">>> 所有指定教程均已完成技术校对和 SVG 审阅，跳过 $SKIPPED_COUNT 篇，无需重复处理"
else
    echo ">>> 技术校对和 SVG 审阅完毕：本次完成 $REVIEWED_COUNT 篇，跳过 $SKIPPED_COUNT 篇"
fi
echo ">>> 日志目录：$LOG_DIR"
