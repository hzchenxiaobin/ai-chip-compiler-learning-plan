#!/usr/bin/env python3
"""日课元数据、覆盖配置与内容哈希（WP-01）。

对应 docs/development/01_构建与内容契约.md：
- 解析 README 引用块四标签：今日目标 / 预计时间 / 前置准备 / 今日产出
- 日课类型推断与 ``config/learning/day-overrides.json`` 覆盖
- 确定性内容哈希 ``content_sha``
- 组装、校验并输出 ``public/learning/days.json``

本模块只读取 tutorials/ 与 config/learning/，不写任何产物。
兼容 Python 3.9+，无第三方依赖。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# 契约常量
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
DAYS_COUNT = 168

QUOTE_LABELS = ("今日目标", "预计时间", "前置准备", "今日产出")

DAY_TYPES = (
    "concept_lab",
    "environment_lab",
    "integration",
    "review",
    "documentation",
    "presentation",
    "final_assessment",
)

#: 日课类型 → 适用任务（与前端 progress.js 的 TASK_IDS 完全一致）
TYPE_TASKS = {
    "concept_lab": ("reading", "exercise", "experiment", "acceptance"),
    "environment_lab": ("reading", "exercise", "experiment", "acceptance"),
    "integration": ("reading", "exercise", "experiment", "acceptance"),
    "review": ("reading", "exercise", "acceptance"),
    "documentation": ("reading", "exercise", "acceptance"),
    "presentation": ("reading", "exercise", "acceptance"),
    "final_assessment": ("reading", "exercise", "experiment", "acceptance"),
}

#: 默认计为“关键产出”的类型（可用 key_output 覆盖）
KEY_OUTPUT_TYPES = frozenset({"integration", "review", "final_assessment"})

#: 覆盖配置允许的日级字段
ALLOWED_OVERRIDE_FIELDS = frozenset(
    {"type", "key_output", "skills", "time", "prerequisites", "deliverable", "source_include"}
)

#: 内容哈希与源码包共同排除的操作系统噪音文件（gitignore 覆盖、跨机器不可复现）
JUNK_BASENAMES = frozenset({".DS_Store", "Thumbs.db", ".localized"})

_TIME_LEARNING_RE = re.compile(r"学习\s*(\d+)\s*分钟")
_TIME_PRACTICE_RE = re.compile(r"实践\s*(\d+)\s*分钟")

_TITLE_PREFIX_RE = re.compile(r"^第\s*\d+\s*天[：:]\s*")


# ---------------------------------------------------------------------------
# 错误类型
# ---------------------------------------------------------------------------


class LearningError(Exception):
    """带错误码与定位信息的内容契约错误。

    展示格式：``[LEARNING_E###] 文件:行号 — 问题；修复建议``
    """

    def __init__(self, code, message, path=None, line=None, hint=None):
        self.code = code
        self.path = str(path) if path is not None else None
        self.line = line
        self.message = message
        self.hint = hint
        location = self.path or ""
        if location and line is not None:
            location += f":{line}"
        text = f"[{code}]"
        if location:
            text += f" {location}"
        text += f" — {message}"
        if hint:
            text += f"；{hint}"
        super().__init__(text)


# ---------------------------------------------------------------------------
# 引用块解析
# ---------------------------------------------------------------------------

_LABEL_LINE_TEMPLATES = {
    label: re.compile(r"^\s*>\s*\*\*" + re.escape(label) + r"\*\*\s*[：:]?\s*(.*)$") for label in QUOTE_LABELS
}
_QUOTE_MARK_RE = re.compile(r"^\s*>\s?")
_LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def extract_labeled_quote(markdown, label, source=None):
    """提取 ``> **标签**：内容`` 引用块，返回 ``(text, line_no)``。

    - 逐行扫描，不依赖 Markdown 渲染库
    - 收集同一连续引用块中的后续行，保留换行
    - 遇到下一个已知标签或引用块结束即停止
    - 标签缺失或重复时抛出 LearningError（含文件与行号）
    """
    if label not in _LABEL_LINE_TEMPLATES:
        raise LearningError("LEARNING_E100", f"未知引用块标签：{label!r}")
    pattern = _LABEL_LINE_TEMPLATES[label]
    lines = markdown.splitlines()
    found = []
    i = 0
    while i < len(lines):
        match = pattern.match(lines[i])
        if not match:
            i += 1
            continue
        start_line = i + 1
        block = [match.group(1)]
        i += 1
        while i < len(lines):
            line = lines[i]
            if not line.lstrip().startswith(">"):
                break
            if any(p.match(line) for p in _LABEL_LINE_TEMPLATES.values()):
                break
            block.append(_QUOTE_MARK_RE.sub("", line, count=1))
            i += 1
        found.append((start_line, "\n".join(block).strip()))
    if not found:
        raise LearningError(
            "LEARNING_E101",
            f"缺少“{label}”引用块",
            path=source,
            hint="在标题下方补充 `> **%s**：…` 引用块" % label,
        )
    if len(found) > 1:
        positions = "、".join(f"第 {ln} 行" for ln, _ in found)
        raise LearningError(
            "LEARNING_E102",
            f"“{label}”引用块出现 {len(found)} 次（{positions}）",
            path=source,
            line=found[0][0],
            hint="同一标签只允许出现一次，请合并内容",
        )
    return found[0][1], found[0][0]


def clean_quote_text(text):
    """把引用块 Markdown 清理为纯文本。

    去掉粗体标记、行内代码反引号、链接/图片语法与列表前缀，
    保留命令、下划线、加号等原文内容。
    """
    cleaned_lines = []
    for line in text.splitlines():
        line = _LIST_PREFIX_RE.sub("", line)
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)
    text = _IMAGE_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    text = text.replace("**", "")
    text = text.replace("`", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_estimated_minutes(text):
    """解析“学习 X 分钟 ＋ 实践 Y 分钟”，返回 dict 或 None。

    兼容全角/半角加号、全角分号、括注等真实变体；
    两个整数均须大于 0。
    """
    learning = _TIME_LEARNING_RE.search(text)
    practice = _TIME_PRACTICE_RE.search(text)
    if not learning or not practice:
        return None
    learning_min = int(learning.group(1))
    practice_min = int(practice.group(1))
    if learning_min <= 0 or practice_min <= 0:
        return None
    return {"learning_min": learning_min, "practice_min": practice_min}


def infer_day_type(day, phase, title=""):
    """按文档规定顺序推断日课类型（覆盖配置可改写结果）。"""
    if day == 168:
        return "final_assessment"
    if day % 7 == 0:
        return "review"
    if day % 7 == 6:
        return "integration"
    if phase == 6:
        return "documentation"
    return "concept_lab"


# ---------------------------------------------------------------------------
# 覆盖配置
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise LearningError("LEARNING_E110", f"JSON 重复键：{key!r}", hint="删除重复键，后值静默覆盖前值不被允许")
        seen[key] = value
    return seen


def load_day_overrides(path, valid_day_ids=None):
    """加载并校验 day-overrides.json，返回 ``{"schema_version": 1, "days": {...}}``。"""
    path = Path(path)
    if not path.is_file():
        return {"schema_version": 1, "days": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise LearningError("LEARNING_E111", f"JSON 解析失败：{exc}", path=path) from exc
    except UnicodeDecodeError as exc:
        raise LearningError("LEARNING_E112", f"文件不是有效 UTF-8：{exc}", path=path) from exc
    if not isinstance(data, dict):
        raise LearningError("LEARNING_E113", "顶层必须是 JSON 对象", path=path)
    unknown_top = set(data) - {"schema_version", "days"}
    if unknown_top:
        raise LearningError(
            "LEARNING_E114",
            f"顶层出现未知字段：{sorted(unknown_top)}",
            path=path,
            hint="只允许 schema_version 与 days",
        )
    if data.get("schema_version") != SCHEMA_VERSION:
        raise LearningError("LEARNING_E115", f"schema_version 必须为 {SCHEMA_VERSION}", path=path)
    days = data.get("days")
    if not isinstance(days, dict):
        raise LearningError("LEARNING_E116", "days 必须是对象", path=path)
    for day_id, override in days.items():
        _validate_day_override(path, day_id, override, valid_day_ids)
    return data


def _validate_day_override(path, day_id, override, valid_day_ids):
    def fail(code, message, hint=None):
        raise LearningError(code, message, path=path, hint=hint)

    if valid_day_ids is not None and day_id not in valid_day_ids:
        fail("LEARNING_E117", f"覆盖配置引用了不存在的日课：{day_id}", "day_id 必须是 day-001…day-168 之一")
    if not isinstance(override, dict):
        fail("LEARNING_E118", f"{day_id} 的覆盖必须是对象")
    unknown = set(override) - ALLOWED_OVERRIDE_FIELDS
    if unknown:
        fail("LEARNING_E119", f"{day_id} 出现未知字段：{sorted(unknown)}", f"允许字段：{sorted(ALLOWED_OVERRIDE_FIELDS)}")
    if "type" in override:
        if override["type"] not in DAY_TYPES:
            fail("LEARNING_E120", f"{day_id} 的 type 非法：{override['type']!r}", f"七种枚举之一：{list(DAY_TYPES)}")
    if "key_output" in override and not isinstance(override["key_output"], bool):
        fail("LEARNING_E121", f"{day_id} 的 key_output 必须是布尔值")
    if "skills" in override:
        skills = override["skills"]
        if not isinstance(skills, list) or not (1 <= len(skills) <= 12):
            fail("LEARNING_E122", f"{day_id} 的 skills 必须是 1—12 个标签的数组")
        seen = set()
        for skill in skills:
            if not isinstance(skill, str):
                fail("LEARNING_E123", f"{day_id} 的技能标签必须是字符串：{skill!r}")
            stripped = skill.strip()
            if not (1 <= len(stripped) <= 40):
                fail("LEARNING_E124", f"{day_id} 的技能标签长度须为 1—40：{skill!r}")
            if stripped in seen:
                fail("LEARNING_E125", f"{day_id} 的技能标签重复：{stripped!r}")
            seen.add(stripped)
    if "time" in override:
        time = override["time"]
        if not isinstance(time, dict) or set(time) != {"learning_min", "practice_min"}:
            fail("LEARNING_E126", f"{day_id} 的 time 必须只含 learning_min/practice_min")
        for key in ("learning_min", "practice_min"):
            value = time[key]
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                fail("LEARNING_E127", f"{day_id} 的 time.{key} 必须是大于 0 的整数")
    for field in ("prerequisites", "deliverable"):
        if field in override:
            value = override[field]
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                fail("LEARNING_E128", f"{day_id} 的 {field} 必须是非空、≤2000 字符的字符串")
    if "source_include" in override:
        includes = override["source_include"]
        if not isinstance(includes, list) or not includes:
            fail("LEARNING_E129", f"{day_id} 的 source_include 必须是非空数组")
        for item in includes:
            if not isinstance(item, str) or not item.strip():
                fail("LEARNING_E130", f"{day_id} 的 source_include 条目必须是字符串")
            if any(ch in item for ch in "*?"):
                fail("LEARNING_E131", f"{day_id} 的 source_include 不允许通配符：{item!r}")
            if "\\" in item or item.startswith("/") or ".." in Path(item).parts:
                fail("LEARNING_E132", f"{day_id} 的 source_include 必须是 code/ 下的显式相对路径：{item!r}")


def unused_override_ids(overrides, day_ids):
    """返回覆盖配置中未被任何真实日课使用的键（应为空）。"""
    return sorted(set(overrides.get("days", {})) - set(day_ids))


# ---------------------------------------------------------------------------
# 内容哈希
# ---------------------------------------------------------------------------


def _iter_day_files(day_dir):
    """遍历日课目录下所有参与哈希的普通文件（相对 POSIX 路径，字节排序）。"""
    entries = []
    for path in day_dir.rglob("*"):
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        if path.name in JUNK_BASENAMES:
            continue
        entries.append((path.relative_to(day_dir).as_posix(), path))
    entries.sort(key=lambda item: item[0].encode("utf-8"))
    return entries


def canonical_override_json(effective_override):
    """规范化的“该日有效覆盖”JSON 字节流（排序键、紧凑分隔符、非 ASCII 原样）。"""
    payload = effective_override if effective_override else {}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def compute_content_sha(day_dir, effective_override=None):
    """计算日课内容哈希（SHA-256，64 位小写十六进制）。

    输入范围：当日 README、images/、code/（含冻结 outputs/）全部普通文件，
    外加该日有效覆盖配置的规范 JSON。排除符号链接与操作系统噪音文件，
    不含构建时间、base path 与其他日课内容。
    """
    digest = hashlib.sha256()
    day_dir = Path(day_dir)
    for rel, path in _iter_day_files(day_dir):
        stat = path.stat()
        data = path.read_bytes()
        if len(data) != stat.st_size:
            raise LearningError(
                "LEARNING_E103",
                f"文件在遍历和读取之间发生变化：{path}",
                hint="请重试构建；若持续出现请检查同步盘或编辑器",
            )
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).hexdigest().encode("ascii"))
        digest.update(b"\n")
    digest.update(canonical_override_json(effective_override))
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# 日课记录组装
# ---------------------------------------------------------------------------


def build_day_record(
    tutorial,
    repo_root,
    overrides_days,
    *,
    github_repo_url,
    content_commit,
    source_zip=None,
):
    """把 load_tutorials() 的一条记录组装为 days.json 的日课记录。

    ``source_zip`` 由构建编排（build.py）在源码包选择之后传入；
    无可发布源码时保持 None，页面隐藏下载入口。
    """
    repo_root = Path(repo_root)
    day = tutorial["number"]
    day_id = f"day-{day:03d}"
    phase = (day - 1) // 28 + 1
    day_dir = Path(tutorial["source"])
    readme_rel = day_dir.relative_to(repo_root).as_posix() + "/README.md"
    override = overrides_days.get(day_id, {})

    markdown = tutorial["markdown"]
    objective_raw, _ = extract_labeled_quote(markdown, "今日目标", source=readme_rel)
    time_raw, _ = extract_labeled_quote(markdown, "预计时间", source=readme_rel)
    prerequisites_raw, _ = extract_labeled_quote(markdown, "前置准备", source=readme_rel)
    deliverable_raw, _ = extract_labeled_quote(markdown, "今日产出", source=readme_rel)

    time = parse_estimated_minutes(time_raw)
    if time is None:
        time = override.get("time")
    if time is None:
        raise LearningError(
            "LEARNING_E104",
            "无法解析“预计时间”（需要“学习 X 分钟”与“实践 Y 分钟”两个正整数）",
            path=readme_rel,
            hint="修正 README，或在 day-overrides.json 的 time 中补充该日覆盖",
        )

    day_type = override.get("type") or infer_day_type(day, phase, tutorial["title"])
    if day_type not in DAY_TYPES:
        raise LearningError("LEARNING_E105", f"日课类型非法：{day_type!r}", path=readme_rel)

    code_dir = day_dir / "code"
    outputs_dir = code_dir / "outputs"
    code_rel = day_dir.relative_to(repo_root).as_posix() + "/code"
    run_all_path = code_dir / "run_all.sh"
    run_all = run_all_path.is_file() and not run_all_path.is_symlink()

    content_sha = compute_content_sha(day_dir, override)

    def github_tree(suffix):
        if not github_repo_url:
            return None
        return f"{github_repo_url}/tree/{content_commit}/{suffix}"

    record = {
        "day_id": day_id,
        "day": day,
        "week": tutorial["week"],
        "phase": phase,
        "type": day_type,
        "key_output": override.get("key_output", day_type in KEY_OUTPUT_TYPES),
        "title": _TITLE_PREFIX_RE.sub("", tutorial["title"]).strip(),
        "objective": clean_quote_text(objective_raw),
        "time": dict(time),
        "prerequisites": override.get("prerequisites") or clean_quote_text(prerequisites_raw),
        "deliverable": override.get("deliverable") or clean_quote_text(deliverable_raw),
        "source_path": readme_rel,
        "code_path": code_rel if code_dir.is_dir() else None,
        "url": f"tutorials/week-{tutorial['week']:03d}/{day_id}/",
        "source_zip": source_zip,
        "code_url": github_tree(code_rel) if code_dir.is_dir() else None,
        "outputs_url": github_tree(code_rel + "/outputs") if outputs_dir.is_dir() else None,
        "run_all": run_all,
        "skills": list(override.get("skills", [])),
        "required_tasks": list(TYPE_TASKS[day_type]),
        "content_sha": content_sha,
    }
    return record


def validate_day_collection(days, content_commit, base_path=""):
    """校验 168 天集合的跨字段一致性，返回错误列表（空列表即通过）。"""
    errors = []

    def add(code, message, hint=None):
        errors.append(LearningError(code, message, hint=hint))

    if len(days) != DAYS_COUNT:
        add("LEARNING_E130C", f"日课数量为 {len(days)}，必须恰好 {DAYS_COUNT} 天")
    if not days:
        return errors
    ids = [d["day_id"] for d in days]
    if len(set(ids)) != len(ids):
        add("LEARNING_E131", "day_id 存在重复")
    if [d["day"] for d in days] != list(range(days[0]["day"], days[0]["day"] + len(days))) or days[0]["day"] != 1:
        add("LEARNING_E132", "日号必须从 1 开始且连续递增")
    for day_record in days:
        day = day_record["day"]
        if day_record["week"] != (day - 1) // 7 + 1:
            add("LEARNING_E133", f"{day_record['day_id']}：week 与日号不一致")
        if day_record["phase"] != (day - 1) // 28 + 1:
            add("LEARNING_E134", f"{day_record['day_id']}：phase 与日号不一致")
        if day_record["type"] not in DAY_TYPES:
            add("LEARNING_E135", f"{day_record['day_id']}：未知类型 {day_record['type']!r}")
        elif day_record["required_tasks"] != list(TYPE_TASKS[day_record["type"]]):
            add("LEARNING_E136", f"{day_record['day_id']}：required_tasks 与类型推导不一致")
        if not re.fullmatch(r"[0-9a-f]{64}", day_record["content_sha"] or ""):
            add("LEARNING_E137", f"{day_record['day_id']}：content_sha 必须是 64 位小写十六进制")
        for field in ("source_path", "code_path", "url"):
            value = day_record.get(field)
            if value is None:
                continue
            if ".." in Path(value).parts or "\\" in value or value.startswith("/"):
                add("LEARNING_E138", f"{day_record['day_id']}：{field} 含不安全路径：{value!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", content_commit or ""):
        add("LEARNING_E139", "content_commit 必须是 40 位十六进制提交哈希")
    if base_path and (not base_path.startswith("/") or base_path.endswith("/")):
        add("LEARNING_E140", "base_path 必须为空串或以单斜杠开头且不以斜杠结尾")
    return errors


def write_days_json(days, output_dir, content_commit, base_path="", generated_at=""):
    """写出 public/learning/days.json（UTF-8、稳定缩进、末尾换行）。"""
    output_dir = Path(output_dir)
    target = output_dir / "learning" / "days.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "content_commit": content_commit,
        "generated_at": generated_at,
        "base_path": base_path,
        "days": days,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    target.write_text(text, encoding="utf-8")
    return target
