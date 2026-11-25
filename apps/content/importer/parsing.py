"""README 正文解析（设计文档 §7.3）。

从 tutorials/week-NNN/day-NNN/README.md 解析：
- 标题（`# 第 N 天：…`），日号/周号与目录一致；
- 四类引用块：今日目标 / 预计时间 / 前置准备 / 今日产出；
- 预计时间（“学习 X 分钟；练习 Y 分钟”，兼容全角标点）。

不依赖任何 Markdown 渲染库；逐行扫描，错误带文件与行号。
"""
import re
from pathlib import Path

from .errors import ImporterError

TASK_IDS = ("reading", "exercise", "experiment", "acceptance")

DAY_TYPES = (
    "concept_lab",
    "environment_lab",
    "integration",
    "review",
    "documentation",
    "presentation",
    "final_assessment",
)

TYPE_TASKS = {
    "concept_lab": ("reading", "exercise", "experiment", "acceptance"),
    "environment_lab": ("reading", "exercise", "experiment", "acceptance"),
    "integration": ("reading", "exercise", "experiment", "acceptance"),
    "review": ("reading", "exercise", "acceptance"),
    "documentation": ("reading", "exercise", "acceptance"),
    "presentation": ("reading", "exercise", "acceptance"),
    "final_assessment": ("reading", "exercise", "experiment", "acceptance"),
}

# 周关键产出默认口径：Day 6 集成 / Day 7 复盘 / 最终验收。
KEY_OUTPUT_DEFAULT_TYPES = frozenset({"integration", "review", "final_assessment"})

QUOTE_LABELS = {
    "objective": "今日目标",
    "time": "预计时间",
    "prerequisites": "前置准备",
    "deliverable": "今日产出",
}

TITLE_RE = re.compile(r"^#\s+第\s*(\d+)\s*天[：:]\s*(.+)$")
QUOTE_LINE_RE = re.compile(r"^>\s?(.*)$")
LABEL_PREFIX_RE = re.compile(r"^\*\*(.+?)\*\*")
TIME_LEARNING_RE = re.compile(r"学习\s*(\d+)\s*分钟")
TIME_PRACTICE_RE = re.compile(r"(?:实践|练习)\s*(\d+)\s*分钟")


def infer_day_type(day: int, phase: int) -> str:
    """稳定类型规则（设计文档 §5.2：显式覆盖优先、稳定规则其次）。"""
    if day == 168:
        return "final_assessment"
    if day % 7 == 0:
        return "review"
    if day % 7 == 6:
        return "integration"
    if phase == 6:
        return "documentation"
    return "concept_lab"


def required_tasks_for_type(day_type: str) -> tuple:
    try:
        return TYPE_TASKS[day_type]
    except KeyError:
        raise ImporterError(
            "CONTENT_TYPE_UNSUPPORTED", f"未知日课类型：{day_type!r}"
        ) from None


def _clean_quote_value(raw: str) -> str:
    """去掉粗体标记、列表前缀与多余空白；保留反引号内文本。"""
    lines = []
    for line in raw.split("\n"):
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = line.replace("**", "")
        lines.append(line.strip())
    value = "\n".join(lines).strip()
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value


def extract_labeled_quote(markdown: str, label: str, source) -> tuple[str, int]:
    """返回 (清洗后的值, 起始行号)。缺失/重复/空值均为错误。"""
    label_re = re.compile(r"^>\s*\*\*" + re.escape(label) + r"\*\*\s*[：:]\s*(.*)$")
    known = [re.escape(v) for v in QUOTE_LABELS.values()]
    known_re = re.compile(r"^(?:[" + "|".join(known) + r"])\b|^")

    found: list[tuple[int, str]] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        match = label_re.match(lines[i])
        if not match:
            i += 1
            continue
        start_line = i + 1
        value_lines = [match.group(1)]
        j = i + 1
        while j < len(lines):
            quote = QUOTE_LINE_RE.match(lines[j])
            if not quote:
                break
            stripped = quote.group(1).strip()
            if any(stripped.startswith(f"**{lbl}**") for lbl in QUOTE_LABELS.values()):
                break
            value_lines.append(stripped)
            j += 1
        found.append((start_line, _clean_quote_value("\n".join(value_lines))))
        i = j

    if not found:
        raise ImporterError(
            "METADATA_LABEL_MISSING", f"缺少“{label}”引用块", source=source
        )
    if len(found) > 1:
        raise ImporterError(
            "METADATA_LABEL_DUPLICATE",
            f"“{label}”引用块出现 {len(found)} 次",
            source=source,
            line=found[1][0],
        )
    line_no, value = found[0]
    if not value:
        raise ImporterError(
            "METADATA_LABEL_EMPTY", f"“{label}”内容为空", source=source, line=line_no
        )
    return value, line_no


def parse_estimated_minutes(text: str) -> dict | None:
    learning = TIME_LEARNING_RE.search(text)
    practice = TIME_PRACTICE_RE.search(text)
    if not learning or not practice:
        return None
    learning_min = int(learning.group(1))
    practice_min = int(practice.group(1))
    if learning_min <= 0 or practice_min <= 0:
        return None
    return {"learning_min": learning_min, "practice_min": practice_min}


class DayDoc:
    """单个日课的解析结果（纯数据，未应用覆盖）。"""

    __slots__ = (
        "day", "week", "phase", "day_id", "title", "objective", "time_text",
        "time", "prerequisites", "deliverable", "markdown", "source_dir", "source",
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def parse_readme(readme_path: Path) -> DayDoc:
    """解析单个日课 README；任何结构性问题都抛 ImporterError。"""
    try:
        text = readme_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ImporterError(
            "ENCODING_INVALID", "README 不是合法 UTF-8", source=readme_path
        ) from exc

    day_dir = readme_path.parent
    week_dir = day_dir.parent
    try:
        directory_day = int(day_dir.name.removeprefix("day-"))
        directory_week = int(week_dir.name.removeprefix("week-"))
    except ValueError:
        raise ImporterError(
            "DIR_NAME_INVALID",
            f"教程目录名称无效：{week_dir.name}/{day_dir.name}",
            source=readme_path,
        ) from None

    lines = text.strip().splitlines()
    if not lines:
        raise ImporterError("TITLE_MISSING", "README 为空", source=readme_path)
    match = TITLE_RE.match(lines[0])
    if not match:
        raise ImporterError(
            "TITLE_UNPARSEABLE", "无法从首行解析“第 N 天：标题”", source=readme_path, line=1
        )
    if int(match.group(1)) != directory_day:
        raise ImporterError(
            "DAY_MISMATCH",
            f"标题天数 {match.group(1)} 与目录 {day_dir.name} 不一致",
            source=readme_path,
            line=1,
        )
    expected_week = (directory_day - 1) // 7 + 1
    if directory_week != expected_week:
        raise ImporterError(
            "WEEK_MISMATCH",
            f"目录周号 {directory_week} 与按日号推导的 {expected_week} 不一致",
            source=readme_path,
        )

    body = "\n".join(lines[1:]).strip()
    objective, _ = extract_labeled_quote(body, QUOTE_LABELS["objective"], readme_path)
    time_text, _ = extract_labeled_quote(body, QUOTE_LABELS["time"], readme_path)
    prerequisites, _ = extract_labeled_quote(
        body, QUOTE_LABELS["prerequisites"], readme_path
    )
    deliverable, _ = extract_labeled_quote(
        body, QUOTE_LABELS["deliverable"], readme_path
    )
    time = parse_estimated_minutes(time_text)  # 失败时由覆盖配置回退（导入器处理）

    return DayDoc(
        day=directory_day,
        week=directory_week,
        phase=(directory_day - 1) // 28 + 1,
        day_id=f"day-{directory_day:03d}",
        title=match.group(2).strip(),
        objective=objective,
        time_text=time_text,
        time=time,
        prerequisites=prerequisites,
        deliverable=deliverable,
        markdown=body,
        source_dir=day_dir,
        source=readme_path,
    )
