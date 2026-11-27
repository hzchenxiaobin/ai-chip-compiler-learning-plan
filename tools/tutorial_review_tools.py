#!/usr/bin/env python3
"""Validate structured technical review reports for daily tutorials."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SECTION_RE = re.compile(r"^## (【错误】|【存疑】|【建议】)\s*$", re.MULTILINE)
FINDING_RE = re.compile(r"^####\s+\d+\.\s+.+$", re.MULTILINE)
QUOTE_RE = re.compile(r"^- \*\*原文\*\*：(.+)$", re.MULTILINE)
BASIS_RE = re.compile(r"^- \*\*依据\*\*：(.+)$", re.MULTILINE)


def check_review(tutorial_path: Path, report_path: Path) -> list[str]:
    if not report_path.is_file():
        return [f"技术校对报告不存在：{report_path}"]

    tutorial = tutorial_path.read_text(encoding="utf-8")
    report = report_path.read_text(encoding="utf-8")
    errors: list[str] = []
    sections = list(SECTION_RE.finditer(report))
    names = [match.group(1) for match in sections]
    expected = ["【错误】", "【存疑】", "【建议】"]
    if names != expected:
        return ["报告必须依次包含且只包含 ## 【错误】、## 【存疑】、## 【建议】 三个分级小节"]

    for index, match in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(report)
        section = report[match.end():end].strip()
        severity = match.group(1)
        if section == "- 无。":
            continue
        findings = list(FINDING_RE.finditer(section))
        if not findings:
            errors.append(f"{severity} 必须写“- 无。”或使用“#### 序号. 标题”列出意见")
            continue
        for finding_index, finding in enumerate(findings):
            finding_end = findings[finding_index + 1].start() if finding_index + 1 < len(findings) else len(section)
            block = section[finding.end():finding_end]
            label = f"{severity} 第 {finding_index + 1} 条"
            quotes = QUOTE_RE.findall(block)
            bases = BASIS_RE.findall(block)
            if len(quotes) != 1:
                errors.append(f"{label}必须且只能包含一行“- **原文**：“引用”")
            else:
                quote = quotes[0].strip()
                if len(quote) < 3 or quote[0] not in "“\"" or quote[-1] not in "”\"":
                    errors.append(f"{label}的原文引用必须使用中文双引号或英文双引号包裹")
                else:
                    quote = quote[1:-1]
                    if quote not in tutorial:
                        errors.append(f"{label}的原文引用未在教程中找到：{quote}")
            if len(bases) != 1 or not bases[0].strip():
                errors.append(f"{label}必须且只能包含一行非空的“- **依据**：说明”")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tutorial", type=Path, help="教程 README.md")
    parser.add_argument("report", type=Path, help="技术校对报告 technical-review.md")
    args = parser.parse_args()
    try:
        errors = check_review(args.tutorial, args.report)
    except (OSError, UnicodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    if errors:
        print("技术校对报告检查未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"技术校对报告检查通过：{args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
