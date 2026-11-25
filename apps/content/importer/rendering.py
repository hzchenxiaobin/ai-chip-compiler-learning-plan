"""Markdown → 白名单 HTML 渲染（设计文档 §7.1）。

- 渲染只允许白名单标签、属性与协议（nh3）；
- 相对图片路径重写为公开资源 URL；相对文件链接重写为 GitHub blob 深链；
- 标题锚点与 vp-solution.js 的 slug 规则一致（页面目录/锚点跳转可用）。
"""
import re
from pathlib import Path

import markdown as markdown_lib
import nh3

from .chunking import make_slugger

_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "blockquote",
    "pre", "code", "a", "img", "table", "thead", "tbody", "tr", "th", "td",
    "hr", "br", "strong", "em", "del", "sup", "sub", "span", "dl", "dt", "dd",
    "input",
}

_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "code": {"class"},
    "span": {"class"},
    "input": {"type", "checked", "disabled"},
}

_ALLOWED_SCHEMES = {"http", "https", "mailto"}

_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _slugify(value, separator="-"):
    """markdown toc 扩展使用的 slug 函数（与 vp-solution 一致）。"""
    text = str(value).lower()
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = text.strip()
    text = re.sub(r"[\s]+", separator, text)
    text = re.sub(f"{separator}+", separator, text).strip(separator)
    if not text:
        return "section"
    if text[0].isdigit():
        text = "_" + text
    return text


def _is_relative(target: str) -> bool:
    return not target.startswith(("#", "/", "mailto:")) and not _SCHEME_RE.match(target)


def rewrite_asset_links(markdown_text: str, asset_url_base: str, github_blob_base: str, day_dir: Path) -> str:
    """渲染前重写 Markdown 中的相对图片/文件链接。"""

    def image_sub(match):
        alt, target = match.group(1), match.group(2)
        if _is_relative(target):
            return f"![{alt}]({asset_url_base}{target})"
        return match.group(0)

    def link_sub(match):
        text, target = match.group(1), match.group(2)
        if not _is_relative(target):
            return match.group(0)
        # 只重写真实存在的文件；目录链接交给 GitHub 树视图。
        local = day_dir / target.split("#")[0].split("?")[0]
        if local.is_file():
            return f"[{text}]({github_blob_base}/{target})"
        return f"[{text}]({github_blob_base}/{target})"

    markdown_text = _IMAGE_RE.sub(image_sub, markdown_text)
    markdown_text = _LINK_RE.sub(link_sub, markdown_text)
    return markdown_text


def render_markdown_html(markdown_text: str) -> str:
    """Markdown → 白名单 HTML。"""
    md = markdown_lib.Markdown(
        extensions=["fenced_code", "tables", "sane_lists", "toc"],
        extension_configs={"toc": {"slugify": _slugify, "toc_depth": "2-3"}},
    )
    html = md.convert(markdown_text)
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_SCHEMES,
    )
