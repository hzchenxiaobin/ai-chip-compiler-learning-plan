#!/usr/bin/env python3
"""Validate the summary and SVG used by a weekly plan page."""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

IMAGE_BLOCK_RE = re.compile(r"^!\[([^\]]+)\]\(images/week-overview\.svg\)$")
PLACEHOLDER_RE = re.compile(
    r"此处.{0,8}(插图|放图)|图片待补充|图像待补充|待插图|占位图|"
    r"建议.{0,6}(画|插入|生成).{0,4}图|TODO|PLACEHOLDER",
    re.IGNORECASE,
)


def check_overview(week_dir: Path) -> list[str]:
    overview_path = week_dir / "overview.md"
    image_path = week_dir / "images" / "week-overview.svg"
    if not overview_path.is_file():
        return [f"周概览不存在：{overview_path}"]

    errors: list[str] = []
    try:
        text = overview_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"无法读取周概览：{exc}"]

    blocks = re.split(r"\n\s*\n", text.strip())
    if len(blocks) != 2:
        errors.append("overview.md 必须且只能包含一个总结段落和一张总览图")
        return errors

    summary, image_block = blocks
    summary_chars = len(re.sub(r"\s+", "", summary))
    if summary_chars < 80:
        errors.append(f"总结过短：去空白后 {summary_chars} 字符，要求至少 80 字符")
    if summary_chars > 400:
        errors.append(f"总结过长：去空白后 {summary_chars} 字符，要求不超过 400 字符")
    if re.search(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|```)", summary, re.MULTILINE):
        errors.append("总结必须是一个自然段，不能包含标题、列表、引用或代码围栏")
    if PLACEHOLDER_RE.search(text):
        errors.append("发现 TODO、占位图或待补图文字")

    image_match = IMAGE_BLOCK_RE.fullmatch(image_block.strip())
    if not image_match:
        errors.append("第二段必须是 ![有意义的替代文本](images/week-overview.svg)")
    elif not image_match.group(1).strip():
        errors.append("总览图缺少替代文本")

    if not image_path.is_file():
        errors.append(f"总览图不存在：{image_path}")
    elif image_path.stat().st_size == 0:
        errors.append("总览图是空文件")
    else:
        try:
            root = ET.parse(image_path).getroot()
            if not root.tag.lower().endswith("svg"):
                errors.append("总览图 SVG 根元素无效")
            if not root.get("viewBox") and not (root.get("width") and root.get("height")):
                errors.append("总览图 SVG 缺少 viewBox 或宽高")
            visible_text = "".join(root.itertext()).strip()
            if not visible_text:
                errors.append("总览图 SVG 没有文字标签")
            if PLACEHOLDER_RE.search(visible_text):
                errors.append("总览图包含占位文字")
        except (ET.ParseError, OSError) as exc:
            errors.append(f"总览图 SVG 解析失败：{exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("week_dir", type=Path, help="例如 tutorials/week-001")
    args = parser.parse_args()

    errors = check_overview(args.week_dir)
    if errors:
        print("周概览检查未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"周概览检查通过：{args.week_dir} 的总结、图片链接和 SVG 均有效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
