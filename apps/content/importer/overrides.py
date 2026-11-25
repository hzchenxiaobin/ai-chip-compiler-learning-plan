"""day-overrides.json 严格加载（设计文档 §7.1）。

允许的日级字段：type/key_output/skills/time/prerequisites/deliverable/source_include。
禁止修改日号、周号、阶段、路径和哈希；未知字段、重复 JSON 键、未使用覆盖均失败。
"""
import json
import re
from pathlib import Path

from .errors import ImporterError

OVERRIDE_ALLOWED_FIELDS = {
    "type",
    "key_output",
    "skills",
    "time",
    "prerequisites",
    "deliverable",
    "source_include",
}

DAY_KEY_RE = re.compile(r"^day-\d{3}$")


def _no_duplicate_keys(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ImporterError("CONFIG_DUPLICATE_KEY", f"JSON 重复键：{key!r}")
        seen.add(key)
    return dict(pairs)


def _validate_skills(day_id, skills):
    if not isinstance(skills, list) or not skills:
        raise ImporterError("OVERRIDE_INVALID", f"{day_id} skills 必须为非空数组")
    if len(skills) > 12:
        raise ImporterError("OVERRIDE_INVALID", f"{day_id} skills 超过 12 个")
    cleaned = []
    for skill in skills:
        if not isinstance(skill, str):
            raise ImporterError("OVERRIDE_INVALID", f"{day_id} 技能必须是字符串")
        stripped = skill.strip()
        if not 1 <= len(stripped) <= 40:
            raise ImporterError(
                "OVERRIDE_INVALID", f"{day_id} 技能长度必须在 1—40：{skill!r}"
            )
        if stripped not in cleaned:
            cleaned.append(stripped)
    return cleaned


def _validate_time(day_id, time):
    if not isinstance(time, dict) or set(time) != {
        "learning_min",
        "practice_min",
    }:
        raise ImporterError(
            "OVERRIDE_INVALID", f"{day_id} time 必须只含 learning_min/practice_min"
        )
    learning = time["learning_min"]
    practice = time["practice_min"]
    if not isinstance(learning, int) or isinstance(learning, bool) or learning <= 0:
        raise ImporterError("OVERRIDE_INVALID", f"{day_id} learning_min 必须为正整数")
    if not isinstance(practice, int) or isinstance(practice, bool) or practice <= 0:
        raise ImporterError("OVERRIDE_INVALID", f"{day_id} practice_min 必须为正整数")
    return {"learning_min": learning, "practice_min": practice}


def _validate_source_include(day_id, include):
    if not isinstance(include, list) or not include:
        raise ImporterError(
            "OVERRIDE_INVALID", f"{day_id} source_include 必须为非空数组"
        )
    for item in include:
        if not isinstance(item, str):
            raise ImporterError("OVERRIDE_INVALID", f"{day_id} source_include 项必须是字符串")
        if item.startswith("/") or ".." in item.split("/") or "\\" in item:
            raise ImporterError(
                "OVERRIDE_INVALID",
                f"{day_id} source_include 不允许绝对路径或 ..：{item!r}",
            )
        if any(ch in item for ch in "*?["):
            raise ImporterError(
                "OVERRIDE_INVALID", f"{day_id} source_include 不允许通配符：{item!r}"
            )
    return list(include)


def load_day_overrides(source_root: Path) -> dict[str, dict]:
    """读取并校验 day-overrides.json，返回 {day_id: {字段: 值}}。"""
    path = source_root / "config" / "learning" / "day-overrides.json"
    if not path.is_file():
        raise ImporterError(
            "CONFIG_MISSING", f"缺少覆盖配置文件：{path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ImporterError(
            "ENCODING_INVALID", "day-overrides.json 不是合法 UTF-8", source=path
        ) from None
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ImporterError(
            "CONFIG_JSON_INVALID", f"JSON 解析失败：{exc.msg}", source=path, line=exc.lineno
        ) from None

    if set(data) != {"schema_version", "days"}:
        raise ImporterError(
            "CONFIG_TOPLEVEL_INVALID", "顶层只允许 schema_version 与 days", source=path
        )
    if data["schema_version"] != 1:
        raise ImporterError(
            "CONFIG_VERSION_UNSUPPORTED",
            f"schema_version 必须为 1，收到 {data['schema_version']!r}",
            source=path,
        )
    days = data["days"]
    if not isinstance(days, dict):
        raise ImporterError("CONFIG_INVALID", "days 必须为对象", source=path)

    from .parsing import DAY_TYPES

    overrides: dict[str, dict] = {}
    for day_id, fields in days.items():
        if not DAY_KEY_RE.match(day_id):
            raise ImporterError("CONFIG_INVALID", f"日课键格式无效：{day_id!r}", source=path)
        if not isinstance(fields, dict) or not fields:
            raise ImporterError("CONFIG_INVALID", f"{day_id} 覆盖必须为非空对象", source=path)
        unknown = set(fields) - OVERRIDE_ALLOWED_FIELDS
        if unknown:
            raise ImporterError(
                "CONFIG_INVALID", f"{day_id} 存在未知覆盖字段：{sorted(unknown)}", source=path
            )
        clean = {}
        if "type" in fields:
            if fields["type"] not in DAY_TYPES:
                raise ImporterError(
                    "CONFIG_INVALID",
                    f"{day_id} type 非法：{fields['type']!r}",
                    source=path,
                )
            clean["type"] = fields["type"]
        if "key_output" in fields:
            if not isinstance(fields["key_output"], bool):
                raise ImporterError(
                    "CONFIG_INVALID", f"{day_id} key_output 必须为布尔", source=path
                )
            clean["key_output"] = fields["key_output"]
        if "skills" in fields:
            clean["skills"] = _validate_skills(day_id, fields["skills"])
        if "time" in fields:
            clean["time"] = _validate_time(day_id, fields["time"])
        if "prerequisites" in fields:
            if not isinstance(fields["prerequisites"], str) or not fields["prerequisites"].strip():
                raise ImporterError(
                    "CONFIG_INVALID", f"{day_id} prerequisites 必须为非空字符串", source=path
                )
            clean["prerequisites"] = fields["prerequisites"].strip()
        if "deliverable" in fields:
            if not isinstance(fields["deliverable"], str) or not fields["deliverable"].strip():
                raise ImporterError(
                    "CONFIG_INVALID", f"{day_id} deliverable 必须为非空字符串", source=path
                )
            clean["deliverable"] = fields["deliverable"].strip()
        if "source_include" in fields:
            clean["source_include"] = _validate_source_include(day_id, fields["source_include"])
        overrides[day_id] = clean
    return overrides


def canonical_override_payload(day_override: dict) -> bytes:
    """覆盖配置的规范 JSON 字节（参与 content_sha）。"""
    return json.dumps(
        day_override, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
