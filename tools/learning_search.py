#!/usr/bin/env python3
"""轻量搜索索引与六阶段正文分片（WP-05 构建侧）。

对应 docs/development/01_构建与内容契约.md §6：
- ``public/learning/search/lite-index.json``：168 天元数据，不含正文
- ``public/learning/search/phase-1.json`` … ``phase-6.json``：每片 28 天正文 chunk
- chunk 以二级/三级标题为边界；超长章节按段落继续切分（单块目标 500—2000 字符）
- 保留代码命令、错误码、IR 操作、文件名的原始 token
- ``anchor`` 与前端 vp-solution.js 的 CJK 友好 slug 完全一致（构建端复刻）
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = 1

CHUNK_HEADING_MAX = 4000  # 超过该长度的章节继续按段落切分
CHUNK_TARGET_MIN = 500
CHUNK_TARGET_MAX = 2000
MAX_CODE_PATHS = 60
MAX_ERROR_TOKENS = 20
ERROR_TOKEN_MAX_LEN = 120

_FENCE_RE = re.compile(r"^(\s*)(```+|~~~+)\s*([\w+-]*)\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_DAY_PREFIX_RE = re.compile(r"^Day\s+(\d+)")
_TABLE_PIPE_RE = re.compile(r"\s*\|\s*")

_ERROR_LINE_RES = (
    re.compile(r"^(?:[^\s:]+:[0-9]+:[0-9]+:\s*)?(error|fatal error)\s*:\s*(.+)$", re.IGNORECASE),
    re.compile(r"^(LLVM ERROR|Assertion failed|Assertion `).*", re.IGNORECASE),
)
_BACKTICK_SPAN_RE = re.compile(r"`([^`\n]{2,120})`")
_BACKTICK_ERROR_HINT_RE = re.compile(r"error|ERROR|Error|错误|Assertion|断言")

# 与 learning_assets.py 保持一致的代码文件扫描排除（outputs 参与错误样例提取）
_SCAN_EXCLUDED_DIR_NAMES = frozenset(
    {"build", "__pycache__", ".cache", ".git", ".idea", ".vscode", "node_modules", ".dSYM", ".pytest_cache"}
)
_SCAN_EXCLUDED_SUFFIXES = frozenset({".o", ".a", ".so", ".dylib", ".dll", ".exe", ".pyc", ".class"})
_JUNK_NAMES = frozenset({".DS_Store", "Thumbs.db", ".localized"})


# ---------------------------------------------------------------------------
# slug：与 static/js/vp-solution.js makeSlugger() 完全一致的构建端复刻
# ---------------------------------------------------------------------------


def make_slugger():
    """CJK 友好 slug；重复时追加 -1/-2；返回函数，空 slug 返回 ''。"""
    used = {}

    def slugify(raw):
        day_match = _DAY_PREFIX_RE.match(str(raw))
        if day_match:
            return "day-" + day_match.group(1)
        slug = str(raw).lower()
        slug = re.sub(r"<[^>]+>", "", slug)
        slug = _LINK_RE.sub(r"\1", slug)
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = slug.strip()
        slug = re.sub(r"\s+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        if not slug:
            return ""
        if slug[0].isdigit():
            slug = "_" + slug
        if slug in used:
            used[slug] += 1
            return f"{slug}-{used[slug]}"
        used[slug] = 0
        return slug

    return slugify


# ---------------------------------------------------------------------------
# 文本抽取与 chunk 切分
# ---------------------------------------------------------------------------


def clean_inline_text(line):
    """清理单行 Markdown 为可搜索纯文本（保留命令与代码字符）。"""
    line = _IMAGE_RE.sub(r" \1 ", line)
    line = _LINK_RE.sub(r"\1", line)
    line = line.replace("**", "").replace("`", "")
    line = _TABLE_PIPE_RE.sub(" ", line)
    return line


def _strip_list_prefix(line):
    return _LIST_PREFIX_RE.sub("", line)


def extract_chunks(markdown):
    """把 Markdown 正文切成 chunk 列表。

    返回 ``[{"seq", "heading", "anchor", "text"}, ...]``；
    h2/h3 开新节，其他标题归入当前节文本；代码围栏保留内容去掉标记；
    超长章节按空行段落继续切分。
    """
    slugify = make_slugger()
    sections = []  # (heading, anchor, [lines])
    current_heading = ""
    current_anchor = ""
    current_lines = []
    in_fence = False

    for line in markdown.splitlines():
        fence = _FENCE_RE.match(line)
        if fence:
            in_fence = not in_fence
            continue
        if in_fence:
            # 代码内容原样保留（去掉缩进外的围栏语言标记已在上面跳过）
            current_lines.append(line.rstrip())
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            raw_text = heading.group(2)
            anchor = slugify(raw_text)
            display = clean_inline_text(raw_text).strip()
            if level in (2, 3):
                if current_lines or current_heading:
                    sections.append((current_heading, current_anchor, current_lines))
                current_heading, current_anchor = display, anchor
                current_lines = []
            else:
                if display:
                    current_lines.append(display)
            continue
        cleaned = clean_inline_text(line)
        cleaned = _strip_list_prefix(cleaned)
        current_lines.append(cleaned.rstrip())
    if current_lines or current_heading:
        sections.append((current_heading, current_anchor, current_lines))

    chunks = []
    seq = 0
    for heading, anchor, lines in sections:
        text = "\n".join(lines).strip("\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text:
            continue
        for piece in _split_long_text(text):
            if not piece.strip():
                continue
            seq += 1
            chunks.append({"seq": seq, "heading": heading, "anchor": anchor, "text": piece})
    return chunks


def _split_long_text(text):
    """超长章节按空行段落切分为目标 500—2000 字符的块。"""
    if len(text) <= CHUNK_HEADING_MAX:
        return [text]
    paragraphs = [p for p in re.split(r"\n\n+", text) if p.strip()]
    pieces = []
    buffer = []
    size = 0
    for paragraph in paragraphs:
        if len(paragraph) > CHUNK_HEADING_MAX:
            if buffer:
                pieces.append("\n\n".join(buffer))
                buffer, size = [], 0
            pieces.extend(_hard_split(paragraph))
            continue
        if size >= CHUNK_TARGET_MIN and size + len(paragraph) > CHUNK_TARGET_MAX:
            pieces.append("\n\n".join(buffer))
            buffer, size = [], 0
        buffer.append(paragraph)
        size += len(paragraph) + 2
    if buffer:
        pieces.append("\n\n".join(buffer))
    return pieces


def _hard_split(text):
    """单个超长段落按行硬切（约 CHUNK_TARGET_MAX 一块）。"""
    pieces = []
    buffer = []
    size = 0
    for line in text.splitlines():
        if size >= CHUNK_TARGET_MAX:
            pieces.append("\n".join(buffer))
            buffer, size = [], 0
        buffer.append(line)
        size += len(line) + 1
    if buffer:
        pieces.append("\n".join(buffer))
    return pieces


# ---------------------------------------------------------------------------
# code_paths 与 error_tokens
# ---------------------------------------------------------------------------


def _iter_code_files(code_dir):
    if not code_dir.is_dir():
        return
    for path in sorted(code_dir.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if path.name in _JUNK_NAMES:
            continue
        rel = path.relative_to(code_dir)
        if any(part in _SCAN_EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
            continue
        if path.suffix in _SCAN_EXCLUDED_SUFFIXES:
            continue
        yield path, rel


def collect_code_paths(day_dir, cap=MAX_CODE_PATHS):
    """返回 code/ 下真实文件的 ``code/<rel>`` 列表（含 outputs，供错误检索）。"""
    code_dir = Path(day_dir) / "code"
    paths = []
    for _, rel in _iter_code_files(code_dir):
        paths.append("code/" + rel.as_posix())
        if len(paths) >= cap:
            break
    return paths


def collect_error_tokens(day_dir, markdown, cap=MAX_ERROR_TOKENS):
    """从正文与代码/输出中提取明确错误样例 token（去重、限长、限量）。"""
    tokens = []
    seen = set()

    def push(token):
        token = re.sub(r"\s+", " ", token).strip()
        if not token or len(token) > ERROR_TOKEN_MAX_LEN:
            return
        if token in seen:
            return
        seen.add(token)
        tokens.append(token)

    for match in _BACKTICK_SPAN_RE.finditer(markdown):
        span = match.group(1)
        if _BACKTICK_ERROR_HINT_RE.search(span):
            push(span)
    code_dir = Path(day_dir) / "code"
    for path, _ in _iter_code_files(code_dir):
        if len(tokens) >= cap:
            break
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:1024]:
            continue  # 跳过二进制
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            continue
        for line in text.splitlines():
            if len(tokens) >= cap:
                break
            line = line.strip()
            if not line:
                continue
            for pattern in _ERROR_LINE_RES:
                if pattern.match(line):
                    push(line)
                    break
    return tokens[:cap]


# ---------------------------------------------------------------------------
# 索引写出
# ---------------------------------------------------------------------------


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def build_search_indexes(tutorials_by_day, days, output_dir, content_commit):
    """生成 lite-index.json 与 phase-1..6.json。

    ``tutorials_by_day``：{day_number: tutorial dict}（来自 load_tutorials）；
    ``days``：days.json 的 days 数组。
    返回 ``(lite_path, [phase_path, ...])``。
    """
    output_dir = Path(output_dir)
    by_day_id = {d["day_id"]: d for d in days}

    lite_days = []
    for record in days:
        lite_days.append(
            {
                "day_id": record["day_id"],
                "day": record["day"],
                "week": record["week"],
                "phase": record["phase"],
                "type": record["type"],
                "key_output": record["key_output"],
                "title": record["title"],
                "objective": record["objective"],
                "deliverable": record["deliverable"],
                "skills": record["skills"],
                "url": record["url"],
            }
        )
    lite_path = _write_json(
        output_dir / "learning" / "search" / "lite-index.json",
        {"schema_version": SCHEMA_VERSION, "content_commit": content_commit, "days": lite_days},
    )

    phase_paths = []
    for phase in range(1, 7):
        phase_days = []
        for record in days:
            if record["phase"] != phase:
                continue
            tutorial = tutorials_by_day.get(record["day"])
            day_dir = Path(tutorial["source"]) if tutorial else None
            markdown = tutorial["markdown"] if tutorial else ""
            chunks = extract_chunks(markdown)
            phase_days.append(
                {
                    "day_id": record["day_id"],
                    "code_paths": collect_code_paths(day_dir) if day_dir else [],
                    "error_tokens": collect_error_tokens(day_dir, markdown),
                    "chunks": [
                        {
                            "chunk_id": f"{record['day_id']}:{chunk['seq']:04d}",
                            "heading": chunk["heading"],
                            "anchor": chunk["anchor"],
                            "text": chunk["text"],
                        }
                        for chunk in chunks
                    ],
                }
            )
        phase_path = _write_json(
            output_dir / "learning" / "search" / f"phase-{phase}.json",
            {
                "schema_version": SCHEMA_VERSION,
                "content_commit": content_commit,
                "phase": phase,
                "days": phase_days,
            },
        )
        phase_paths.append(phase_path)

    validate_search_indexes(output_dir, days, content_commit)
    return lite_path, phase_paths


def validate_search_indexes(output_dir, days, content_commit):
    """校验索引覆盖、提交一致性与 chunk 基本约束（失败抛 LearningError）。"""
    from learning_metadata import LearningError

    output_dir = Path(output_dir)
    search_dir = output_dir / "learning" / "search"

    lite = json.loads((search_dir / "lite-index.json").read_text(encoding="utf-8"))
    if lite["content_commit"] != content_commit:
        raise LearningError("LEARNING_E301", "lite 索引 content_commit 与 days.json 不一致")
    if len(lite["days"]) != len(days):
        raise LearningError("LEARNING_E302", f"lite 索引天数 {len(lite['days'])} ≠ {len(days)}")

    seen_day_ids = []
    seen_chunk_ids = set()
    for phase in range(1, 7):
        shard = json.loads((search_dir / f"phase-{phase}.json").read_text(encoding="utf-8"))
        if shard["content_commit"] != content_commit:
            raise LearningError("LEARNING_E303", f"phase-{phase} content_commit 与 days.json 不一致")
        if shard["phase"] != phase:
            raise LearningError("LEARNING_E304", f"phase-{phase} 文件的 phase 字段不一致")
        for day_entry in shard["days"]:
            seen_day_ids.append(day_entry["day_id"])
            if not day_entry["chunks"]:
                raise LearningError("LEARNING_E305", f"{day_entry['day_id']} 没有任何正文 chunk")
            for chunk in day_entry["chunks"]:
                if not chunk["text"].strip():
                    raise LearningError("LEARNING_E306", f"{day_entry['day_id']} 存在空 chunk")
                if chunk["chunk_id"] in seen_chunk_ids:
                    raise LearningError("LEARNING_E307", f"chunk_id 重复：{chunk['chunk_id']}")
                seen_chunk_ids.add(chunk["chunk_id"])

    expected_ids = sorted(d["day_id"] for d in days)
    if sorted(seen_day_ids) != expected_ids:
        missing = set(expected_ids) - set(seen_day_ids)
        extra = set(seen_day_ids) - set(expected_ids)
        raise LearningError(
            "LEARNING_E308",
            f"六阶段分片与 days.json 不一致（缺失 {sorted(missing)[:3]}，多余 {sorted(extra)[:3]}）",
        )
    return True
