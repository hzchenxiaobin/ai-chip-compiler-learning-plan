"""正文分片与锚点（设计文档 §7.5）。

- 以二级/三级标题为边界切分；超过 4000 字符的章节按空行段落继续切分，
  单块目标 500—2000 字符；
- 保留代码命令、错误码、IR 操作、文件名 token（只去除围栏标记）；
- 锚点复刻 vp-solution.js 的 CJK 友好 slug 规则，保证页面标题与分片锚点一致。
"""
import re
from dataclasses import dataclass, field

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE_RE = re.compile(r"^(```|~~~)")
_META_LABEL_RE = re.compile(r"^>\s*\*\*(今日目标|预计时间|前置准备|今日产出)\*\*")
_MAX_SECTION = 4000
_CHUNK_TARGET = (500, 2000)

_DAY_TITLE_RE = re.compile(r"^Day\s+(\d+)")


def make_slugger():
    """复刻 vp-solution.js makeSlugger（含 Day N 特例与去重后缀）。"""
    used: dict[str, int] = {}

    def slug(raw: str) -> str:
        day_match = _DAY_TITLE_RE.match(raw)
        if day_match:
            return "day-" + day_match.group(1)
        text = raw.lower()
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
        text = text.strip()
        text = re.sub(r"\s+", "-", text)
        text = re.sub(r"-+", "-", text).strip("-")
        if not text:
            return ""
        if text[0].isdigit():
            text = "_" + text
        if text in used:
            used[text] += 1
            text = f"{text}-{used[text]}"
        else:
            used[text] = 0
        return text

    return slug


@dataclass
class Chunk:
    chunk_id: str
    heading: str
    anchor: str
    text: str


def _strip_inline(line: str) -> str:
    """去除行内标记但保留文字与代码内容。"""
    # 图片 → alt 文本；链接 → 显示文字。
    line = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
    line = line.replace("**", "").replace("__", "")
    line = re.sub(r"`([^`]*)`", r"\1", line)
    # 表格行：去掉分隔竖线。
    if line.startswith("|"):
        line = line.strip("|").replace("|", " ")
    return line.strip()


def build_chunks(markdown: str, day_id: str) -> list[Chunk]:
    """从 Markdown 正文构建搜索分片。顶部四类引用块是元数据，不进入正文分片。"""
    slug = make_slugger()
    # 先扫描全部标题，保证锚点去重与页面渲染一致。
    headings: list[tuple[int, str, str]] = []  # (level, raw, anchor)
    in_fence = False
    for line in markdown.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            raw = match.group(2)
            headings.append((len(match.group(1)), raw, slug(raw)))

    def anchor_for(raw: str) -> str:
        for _level, candidate_raw, anchor in headings:
            if candidate_raw == raw:
                return anchor
        return slug(raw)

    sections: list[tuple[str, str]] = []  # (heading_raw, text_lines)
    current_heading = ""
    current_lines: list[str] = []
    in_fence = False
    seen_first_heading = False
    for line in markdown.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            # 围栏行本身丢弃，代码内容保留。
            if not in_fence:
                current_lines.append("")
            continue
        if not seen_first_heading and not in_fence and _META_LABEL_RE.match(line):
            # 顶部元数据引用块（含其续行）跳过。
            continue
        if not in_fence:
            match = _HEADING_RE.match(line)
            if match:
                if current_lines or current_heading:
                    sections.append((current_heading, "\n".join(current_lines).strip()))
                seen_first_heading = True
                current_heading = match.group(2)
                current_lines = []
                continue
        current_lines.append(_strip_inline(line) if not in_fence else line.rstrip())
    if current_lines or current_heading:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    chunks: list[Chunk] = []
    index = 1
    for heading_raw, text in sections:
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text:
            continue
        anchor = anchor_for(heading_raw) if heading_raw else ""
        parts = _split_long_text(text)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"{day_id}:{index:04d}",
                    heading=heading_raw[:200],
                    anchor=anchor[:200],
                    text=part,
                )
            )
            index += 1
    return chunks


def _split_long_text(text: str) -> list[str]:
    if len(text) <= _MAX_SECTION:
        return [text]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    parts: list[str] = []
    buffer: list[str] = []
    size = 0
    for paragraph in paragraphs:
        para_len = len(paragraph) + 1
        if buffer and size + para_len > _CHUNK_TARGET[1]:
            parts.append("\n\n".join(buffer))
            buffer = []
            size = 0
        buffer.append(paragraph)
        size += para_len
        if size >= _CHUNK_TARGET[0] and size <= _CHUNK_TARGET[1]:
            parts.append("\n\n".join(buffer))
            buffer = []
            size = 0
    if buffer:
        parts.append("\n\n".join(buffer))
    return parts


def heading_anchors(markdown: str) -> list[str]:
    """全部标题锚点（供链接校验）。"""
    slug = make_slugger()
    result = []
    in_fence = False
    for line in markdown.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            anchor = slug(match.group(2))
            if anchor:
                result.append(anchor)
    return result


@dataclass
class CodePaths:
    paths: list[str] = field(default_factory=list)
    error_tokens: list[str] = field(default_factory=list)


def collect_code_paths(code_dir) -> CodePaths:
    """code/ 下相对文件路径（供检索）与正文/代码中的错误样例 token。"""
    import os
    from pathlib import Path

    result = CodePaths()
    code_dir = Path(code_dir)
    if not code_dir.is_dir():
        return result
    count = 0
    for root, dirs, files in os.walk(code_dir, followlinks=False):
        root_path = Path(root)
        dirs[:] = sorted(d for d in dirs if d not in {"outputs", "build", ".cache", "__pycache__"})
        for name in sorted(files):
            path = root_path / name
            if path.is_symlink():
                continue
            rel = path.relative_to(code_dir.parent).as_posix()
            result.paths.append(rel)
            count += 1
            if count >= 200:
                return result
    return result


_ERROR_LINE_RE = re.compile(r"(?i)\berror\b|错误")


def collect_error_tokens(markdown: str, limit: int = 20) -> list[str]:
    """从正文含 error/错误 的行提取反引号片段与大写错误码。"""
    tokens: list[str] = []
    seen = set()
    for line in markdown.splitlines():
        if not _ERROR_LINE_RE.search(line):
            continue
        for backtick in re.findall(r"`([^`\n]{2,60})`", line):
            cleaned = backtick.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                tokens.append(cleaned)
        for upper in re.findall(r"\b([A-Z][A-Z0-9_]{2,29})\b", line):
            if upper not in seen:
                seen.add(upper)
                tokens.append(upper)
        if len(tokens) >= limit:
            break
    return tokens[:limit]
