#!/usr/bin/env python3
"""Extract a daily brief and validate illustrated Markdown tutorials."""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DAY_RE = re.compile(r"^###\s+第\s*(\d+)\s*天(?:｜|[:：|]?)\s*(.*)$", re.MULTILINE)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
PLACEHOLDER_RE = re.compile(
    r"此处.{0,8}(插图|放图)|图片待补充|图像待补充|待插图|占位图|"
    r"建议.{0,6}(画|插入|生成).{0,4}图|TODO|PLACEHOLDER",
    re.IGNORECASE,
)


def extract_day(plan: Path, day: int) -> str:
    text = plan.read_text(encoding="utf-8")
    matches = list(DAY_RE.finditer(text))
    target = next((m for m in matches if int(m.group(1)) == day), None)
    if target is None:
        available = f"{int(matches[0].group(1))}～{int(matches[-1].group(1))}" if matches else "无"
        raise ValueError(f"计划中未找到第 {day} 天；可识别范围：{available}")

    next_heading = re.search(r"^#{1,3}\s+", text[target.end():], re.MULTILINE)
    end = target.end() + next_heading.start() if next_heading else len(text)
    return text[target.start():end].strip() + "\n"


def valid_image(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "文件不存在"
    if path.stat().st_size == 0:
        return False, "空文件"
    suffix = path.suffix.lower()
    try:
        if suffix == ".svg":
            root = ET.parse(path).getroot()
            if not root.tag.lower().endswith("svg"):
                return False, "SVG 根元素无效"
            return True, ""
        if suffix == ".png":
            with path.open("rb") as f:
                if f.read(8) != b"\x89PNG\r\n\x1a\n":
                    return False, "PNG 文件头无效"
            return True, ""
        if suffix in {".jpg", ".jpeg"}:
            with path.open("rb") as f:
                if f.read(2) != b"\xff\xd8":
                    return False, "JPG 文件头无效"
            return True, ""
        if suffix == ".webp":
            with path.open("rb") as f:
                header = f.read(12)
            if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WEBP":
                return False, "WebP 文件头无效"
            return True, ""
        if suffix == ".gif":
            with path.open("rb") as f:
                if f.read(6) not in {b"GIF87a", b"GIF89a"}:
                    return False, "GIF 文件头无效"
            return True, ""
    except (ET.ParseError, OSError) as exc:
        return False, f"解析失败：{exc}"
    return False, "不支持的图片格式"


def check_tutorial(path: Path, min_images: int, min_chars: int) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    content_chars = len(re.sub(r"\s+", "", text))

    if content_chars < min_chars:
        errors.append(f"正文过短：去空白后 {content_chars} 字符，要求至少 {min_chars}")
    if PLACEHOLDER_RE.search(text):
        errors.append("发现 TODO、占位图或待补图文字")
    if text.count("```") % 2:
        errors.append("代码围栏未成对闭合")
    if len(re.findall(r"^##\s+", text, re.MULTILINE)) < 5:
        errors.append("二级小节少于 5 个，教程可能不完整")
    for keyword in ("实践", "常见错误", "练习", "验收", "总结"):
        if keyword not in text:
            errors.append(f"缺少必要环节：{keyword}")
    if len(re.findall(r"^- \[ \]", text, re.MULTILINE)) < 3:
        errors.append("可勾选验收项少于 3 个")

    matches = IMAGE_RE.findall(text)
    local_count = 0
    for alt, raw_target in matches:
        target = raw_target.strip().split()[0].strip("<>")
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target) or target.startswith("data:"):
            continue
        local_count += 1
        image_path = (path.parent / target).resolve()
        ok, reason = valid_image(image_path)
        if not alt.strip():
            errors.append(f"图片缺少替代文本：{target}")
        if not ok:
            errors.append(f"图片无效：{target}（{reason}）")
    if local_count < min_images:
        errors.append(f"本地图片少于 {min_images} 张，实际识别到 {local_count} 张")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="提取计划中的某一天")
    extract_parser.add_argument("plan", type=Path)
    extract_parser.add_argument("--day", type=int, required=True)

    check_parser = subparsers.add_parser("check", help="检查 Markdown 教程")
    check_parser.add_argument("tutorial", type=Path)
    check_parser.add_argument("--min-images", type=int, default=3)
    check_parser.add_argument("--min-chars", type=int, default=1800)

    args = parser.parse_args()
    try:
        if args.command == "extract":
            sys.stdout.write(extract_day(args.plan, args.day))
            return 0

        errors = check_tutorial(args.tutorial, args.min_images, args.min_chars)
        if errors:
            print("教程检查未通过：", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("教程检查通过：结构、图片和最低内容要求均满足。")
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
