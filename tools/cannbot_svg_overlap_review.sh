#!/usr/bin/env bash
# 使用 cannbot 串行检查每日教程的 SVG，修复文字或图形重叠并复检。
# 默认处理第 001～168 天，也可只处理某一天：
#   ./cannbot_svg_overlap_review.sh
#   ./cannbot_svg_overlap_review.sh 45
# 在可信环境中需要自动批准 cannbot 工具权限时：
#   CANNBOT_AUTO_APPROVE=1 ./cannbot_svg_overlap_review.sh 45
# 可通过 MAX_ATTEMPTS 调整重试次数，FORCE=1 可忽略完成标记重新检查。
# 日志默认保存在 build/cannbot_svg_overlap_review/。
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TUTORIAL_TOOL="$ROOT_DIR/skills/ai-compiler-daily-tutorial/scripts/tutorial_tools.py"
BUILD_TOOL="$ROOT_DIR/tools/build.py"
TUTORIAL_ROOT="$ROOT_DIR/tutorials"
MAX_DAY=168
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
CANNBOT_AUTO_APPROVE="${CANNBOT_AUTO_APPROVE:-0}"
FORCE="${FORCE:-0}"
LOG_BASE="${LOG_BASE:-$ROOT_DIR/build/cannbot_svg_overlap_review}"
REVIEW_MARKER='<!-- svg-overlap-review: v1 -->'

cd "$ROOT_DIR" || exit 1

for required_command in cannbot python3 tee; do
    if ! command -v "$required_command" > /dev/null 2>&1; then
        echo "错误：找不到 $required_command 命令" >&2
        exit 1
    fi
done

for required_file in "$TUTORIAL_TOOL" "$BUILD_TOOL"; do
    if [ ! -f "$required_file" ]; then
        echo "错误：找不到必需文件：$required_file" >&2
        exit 1
    fi
done

if [[ ! "$MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
    echo "错误：MAX_ATTEMPTS 必须是正整数" >&2
    exit 2
fi
for boolean_name in CANNBOT_AUTO_APPROVE FORCE; do
    boolean_value="${!boolean_name}"
    if [ "$boolean_value" != "0" ] && [ "$boolean_value" != "1" ]; then
        echo "错误：$boolean_name 只能设为 0 或 1" >&2
        exit 2
    fi
done

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
if [ "$FORCE" -eq 1 ]; then
    echo ">>> 已启用 FORCE，将重新检查带有完成标记的 SVG"
fi
echo ">>> 本次运行日志：$LOG_DIR"

check_svg_files() {
    python3 - "$REVIEW_MARKER" "${SVG_FILES[@]}" <<'PY'
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

marker = sys.argv[1]
errors = []
for filename in sys.argv[2:]:
    path = Path(filename)
    try:
        root = ET.parse(path).getroot()
        if root.tag.rsplit("}", 1)[-1] != "svg":
            errors.append(f"根元素不是 svg：{path}")
    except (ET.ParseError, OSError) as exc:
        errors.append(f"SVG 解析失败：{path}：{exc}")
        continue
    try:
        if marker not in path.read_text(encoding="utf-8"):
            errors.append(f"缺少重叠检查完成标记：{path}")
    except (OSError, UnicodeError) as exc:
        errors.append(f"SVG 读取失败：{path}：{exc}")

if errors:
    print("\n".join(errors))
    raise SystemExit(1)
print(f"SVG 解析与重叠检查标记校验通过，共 {len(sys.argv) - 2} 张")
PY
}

FAILED_DAYS=()
REVIEWED_COUNT=0
SKIPPED_COUNT=0

for day in "${DAYS[@]}"; do
    DAY_ID="$(printf "%03d" "$day")"
    WEEK_ID="$(printf "%03d" $(( (day - 1) / 7 + 1 )))"
    DAY_DIR="$TUTORIAL_ROOT/week-$WEEK_ID/day-$DAY_ID"
    TUTORIAL="$DAY_DIR/README.md"

    echo
    echo "======== 第 $DAY_ID 天 ========"

    if [ ! -f "$TUTORIAL" ]; then
        echo ">>> 教程不存在，记录失败并继续：$TUTORIAL" >&2
        FAILED_DAYS+=("$DAY_ID")
        continue
    fi

    SVG_FILES=()
    if [ -d "$DAY_DIR/images" ]; then
        mapfile -t SVG_FILES < <(find "$DAY_DIR/images" -maxdepth 1 -type f -name '*.svg' -print | sort)
    fi
    if [ "${#SVG_FILES[@]}" -eq 0 ]; then
        echo ">>> 没有找到 SVG，记录失败并继续：$DAY_DIR/images" >&2
        FAILED_DAYS+=("$DAY_ID")
        continue
    fi

    if [ "$FORCE" -eq 0 ] && CHECK_OUTPUT="$(check_svg_files 2>&1)"; then
        echo ">>> 第 $DAY_ID 天的 ${#SVG_FILES[@]} 张 SVG 均已完成检查，跳过"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    BASE_MESSAGE="检查并修复第 $day 天教程的全部 SVG 重叠问题，只处理 $DAY_DIR/images 下现有的 ${#SVG_FILES[@]} 张 SVG。完整阅读 $TUTORIAL 以理解每张图的技术含义，逐张打开并检查图片，不要只检查被本次修改过的图，也不要处理其他教程。

必须实际渲染每张 SVG，并使用你现有的图像查看工具检查渲染结果；必要时将 SVG 临时转换为 PNG，临时文件放在系统临时目录并在完成后清理。不得仅根据 SVG 坐标或源码推断没有重叠。若当前环境无法渲染和查看图片，明确报告受阻，不要添加完成标记。

逐图检查：文字与文字、文字与节点/图标/箭头/连接线之间是否有影响阅读的重叠；文字是否超出所属容器、被其他元素遮挡、溢出 viewBox 或被裁切；分组 transform、text-anchor、tspan 换行后的实际位置是否导致碰撞。文字位于有足够留白的面板内部、背景与前景正常包含、箭头与节点的合理连接不算问题，不要为了消除有意的层叠而破坏图意。

发现重叠时直接优化对应 SVG，优先最小调整相关文字或元素的位置、容器尺寸、换行、字号或画布尺寸，保持原有技术内容、手绘风格、配色、文件路径和教程引用不变。不得用缩小到难以阅读的字号来掩盖问题，不得删除技术标签，不得顺手润色教程、代码、输出或其他图片。修复后重新渲染并逐张复检，确认没有引入新的重叠、溢出或裁切。

每张 SVG 只有在完成实际渲染检查且无需修复，或修复后复检通过时，才在文件中保留或添加一行 $REVIEW_MARKER。该标记仅用于断点续跑，不得用添加标记代替检查和修复。最终回复逐图说明“无重叠”或“已修复”及具体调整。

完成后运行 python3 $TUTORIAL_TOOL check $TUTORIAL 和 python3 $BUILD_TOOL，确保教程图片校验与整站构建通过。不要执行 Git 提交或推送。"

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

上一次尝试未完成，不要重复相同操作。先读取上次日志并检查已有文件，从断点继续。已经实际检查且带有完成标记的图片无需返工，重点处理尚未标记、仍有重叠或导致校验失败的图片；若上轮修复不正确，只调整有问题的元素。
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
        if ! CHECK_OUTPUT="$(check_svg_files 2>&1)"; then
            :
        elif ! CHECK_OUTPUT="$(python3 "$TUTORIAL_TOOL" check "$TUTORIAL" 2>&1)"; then
            :
        elif BUILD_OUTPUT="$(python3 "$BUILD_TOOL" 2>&1)"; then
            printf '%s\n%s\n' "$CHECK_OUTPUT" "$BUILD_OUTPUT" | tee -a "$ATTEMPT_LOG"
            echo ">>> 第 $DAY_ID 天 SVG 重叠检查完成，图片解析、教程校验和整站构建均通过"
            COMPLETED=1
            REVIEWED_COUNT=$((REVIEWED_COUNT + 1))
            break
        fi
        printf '>>> 校验或构建结果：\n%s\n%s\n' "$CHECK_OUTPUT" "$BUILD_OUTPUT" | tee -a "$ATTEMPT_LOG"

        if [ "$CANNBOT_STATUS" -ne 0 ]; then
            echo ">>> 警告：cannbot 执行失败（退出码 $CANNBOT_STATUS），且 SVG 检查尚未完成" >&2
        else
            echo ">>> 警告：cannbot 已退出，但 SVG 检查尚未通过完整校验" >&2
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
    echo ">>> SVG 重叠检查结束：本次完成 $REVIEWED_COUNT 篇，跳过 $SKIPPED_COUNT 篇；失败日期：${FAILED_DAYS[*]}" >&2
    echo ">>> 失败详情见日志：$LOG_DIR" >&2
    exit 1
fi
if [ "$REVIEWED_COUNT" -eq 0 ]; then
    echo ">>> 所有指定教程的 SVG 均已完成检查，跳过 $SKIPPED_COUNT 篇，无需重复处理"
else
    echo ">>> SVG 重叠检查完毕：本次完成 $REVIEWED_COUNT 篇，跳过 $SKIPPED_COUNT 篇"
fi
echo ">>> 日志目录：$LOG_DIR"
