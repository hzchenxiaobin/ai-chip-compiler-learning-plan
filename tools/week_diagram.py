#!/usr/bin/env python3
"""为每周计划页生成整体框架图 SVG（手绘风格，与教程图片规范一致）。

规范（提取自 tutorials/**/images/*.svg）：
- 纸面背景 #fdfaf4；楷体手写字体栈；标题 26–27 / 副标题 14；
- 手绘波浪边框（抖动折线 + round linejoin），线宽 2.4–3；
- 色板：主文字 #3a4657、次要 #6b7686、强调 #e0884f；
- 面板底色 #fffdf8（普通）/ #fbeadd（强调）。

布局：Day 1–5 零件卡 → Day 6 集成（强调）→ Day 7 复盘 → 本周关键产出。
数据全部来自学习计划 Markdown，构建期生成，保证与计划同步。
"""

from __future__ import annotations

import html
import math
import random
import re

FONT = "Xiaolai, 'Kaiti SC', KaiTi, STKaiti, 'Comic Sans MS', 'Segoe Print', cursive"
INK = "#3a4657"
MUTED = "#6b7686"
ACCENT = "#e0884f"
PANEL = "#fffdf8"
PANEL_ACCENT = "#fbeadd"
PAPER = "#fdfaf4"

DAY_RE = re.compile(r"^###\s*第\s*(\d+)\s*天[｜|:：]\s*(.+)$")
OUTPUT_RE = re.compile(r"^-\s*\*\*产出\*\*[：:]\s*(.+)$")


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _wrap(text: str, per_line: int, max_lines: int) -> list[str]:
    """按字符数换行（CJK 友好）；超出截断加省略号。"""
    text = text.strip()
    if len(text) <= per_line:
        return [text]
    lines = [text[i : i + per_line] for i in range(0, len(text), per_line)]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        lines[-1] = (last[: per_line - 1] + "…") if len(last) >= per_line else last
    return lines


def _text(x, y, content, *, size=13, fill=INK, weight=500, anchor="middle"):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" '
        f'font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
        f'font-weight="{weight}">{_escape(content)}</text>'
    )


def _wavy_rect(rng, x, y, w, h, *, fill=None, stroke=INK, width=2.4):
    """手绘风矩形：抖动折线路径 + 圆角连接，填充与描边分层（与教程图一致）。"""
    points = []

    def edge(x1, y1, x2, y2):
        length = math.hypot(x2 - x1, y2 - y1)
        steps = max(2, int(length / 26))
        for i in range(steps + 1):
            t = i / steps
            points.append((
                x1 + (x2 - x1) * t + rng.uniform(-1.7, 1.7),
                y1 + (y2 - y1) * t + rng.uniform(-1.7, 1.7),
            ))

    edge(x, y, x + w, y)
    edge(x + w, y, x + w, y + h)
    edge(x + w, y + h, x, y + h)
    edge(x, y + h, x, y)
    path = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in points) + " Z"
    parts = []
    if fill:
        parts.append(f'<path d="{path}" fill="{fill}" stroke="none"/>')
    parts.append(
        f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    return "".join(parts)


def _wavy_arrow(rng, x1, y1, x2, y2, *, stroke=MUTED, width=2.2):
    """手绘箭头：抖动折线 + 三角箭头。"""
    points = [(x1, y1)]
    steps = 3
    for i in range(1, steps + 1):
        t = i / (steps + 1)
        points.append((
            x1 + (x2 - x1) * t + rng.uniform(-2.0, 2.0),
            y1 + (y2 - y1) * t + rng.uniform(-2.0, 2.0),
        ))
    points.append((x2, y2))
    path = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in points)
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 8.0
    left = (x2 - size * math.cos(angle - 0.42), y2 - size * math.sin(angle - 0.42))
    right = (x2 - size * math.cos(angle + 0.42), y2 - size * math.sin(angle + 0.42))
    head = (
        f'<polygon points="{x2:.1f},{y2:.1f} {left[0]:.1f},{left[1]:.1f} '
        f'{right[0]:.1f},{right[1]:.1f}" fill="{stroke}"/>'
    )
    return (
        f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>{head}'
    )


def _parse_days(lines) -> list[dict]:
    days = []
    current = None
    for line in lines:
        day_match = DAY_RE.match(line)
        if day_match:
            current = {
                "day": int(day_match.group(1)),
                "title": day_match.group(2).strip(),
                "output": "",
            }
            days.append(current)
            continue
        if current is not None:
            output_match = OUTPUT_RE.match(line)
            if output_match and not current["output"]:
                current["output"] = output_match.group(1).strip()
    return days


def render_week_framework_svg(week: dict) -> str:
    """week 来自 build.load_plan()：{number, title, phase, lines}。"""
    rng = random.Random(2026_0000 + week["number"])
    number = week["number"]
    days = _parse_days(week["lines"])
    weekdays = [d for d in days if (d["day"] - 1) // 7 + 1 == number][:7]

    width, height = 980, 620
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{PAPER}"/>',
        _text(width / 2, 46, week["title"], size=26, weight=600),
        _text(
            width / 2, 74,
            f"{week['phase']} ｜ 本周闭环：Day 1–5 零件 → Day 6 集成 → Day 7 复盘",
            size=14, fill=MUTED,
        ),
    ]

    # ---- Row 1：Day 1–5 零件卡 ----
    card_w, card_h, gap, x0, y1 = 160, 138, 16, 58, 102
    centers = []
    for index in range(5):
        day = weekdays[index] if index < len(weekdays) else None
        x = x0 + index * (card_w + gap)
        parts.append(_wavy_rect(rng, x, y1, card_w, card_h, fill=PANEL))
        label = f"Day {day['day']}" if day else "—"
        parts.append(_text(x + card_w / 2, y1 + 28, label, size=15, weight=600))
        if day:
            for line_no, line in enumerate(_wrap(day["title"], 8, 3)):
                parts.append(_text(
                    x + card_w / 2, y1 + 54 + line_no * 19, line,
                    size=12.5, fill=MUTED,
                ))
        centers.append(x + card_w / 2)
        if index > 0:
            prev_x = x0 + (index - 1) * (card_w + gap)
            parts.append(_wavy_arrow(
                rng, prev_x + card_w + 1, y1 + card_h / 2, x - 2, y1 + card_h / 2,
            ))

    # ---- Row 2：Day 6 集成（强调）/ Day 7 复盘 ----
    y2, row2_h = 286, 132
    day6 = weekdays[5] if len(weekdays) > 5 else None
    day7 = weekdays[6] if len(weekdays) > 6 else None
    x6, w6 = 58, 416
    x7, w7 = 506, 416
    # Day 5 → Day 6 的折线箭头。
    if weekdays:
        parts.append(_wavy_arrow(
            rng, x0 + 4 * (card_w + gap) + card_w / 2, y1 + card_h + 2,
            x6 + w6 - 46, y2 - 2, stroke=ACCENT,
        ))
    # Day 6 卡。
    parts.append(_wavy_rect(rng, x6, y2, w6, row2_h, fill=PANEL_ACCENT, stroke=ACCENT))
    parts.append(_text(x6 + w6 / 2, y2 + 26, "Day 6 · 集成日", size=14, fill=ACCENT, weight=600))
    if day6:
        for line_no, line in enumerate(_wrap(day6["title"], 24, 1)):
            parts.append(_text(x6 + w6 / 2, y2 + 52, line, size=15))
        if day6["output"]:
            for line_no, line in enumerate(_wrap("产出：" + day6["output"], 26, 2)):
                parts.append(_text(
                    x6 + w6 / 2, y2 + 82 + line_no * 19, line, size=12.5, fill=MUTED,
                ))
    # Day 6 → Day 7。
    parts.append(_wavy_arrow(rng, x6 + w6 + 2, y2 + row2_h / 2, x7 - 3, y2 + row2_h / 2))
    # Day 7 卡。
    parts.append(_wavy_rect(rng, x7, y2, w7, row2_h, fill=PANEL))
    parts.append(_text(x7 + w7 / 2, y2 + 26, "Day 7 · 复盘 / 验收", size=14, fill=MUTED, weight=600))
    if day7:
        for line_no, line in enumerate(_wrap(day7["title"], 24, 1)):
            parts.append(_text(x7 + w7 / 2, y2 + 52, line, size=15))
        if day7["output"]:
            for line_no, line in enumerate(_wrap("产出：" + day7["output"], 26, 2)):
                parts.append(_text(
                    x7 + w7 / 2, y2 + 82 + line_no * 19, line, size=12.5, fill=MUTED,
                ))

    # ---- 底部：本周闭环与关键产出 ----
    y3, h3 = 462, 108
    parts.append(_wavy_rect(rng, 58, y3, 864, h3, fill=PANEL, stroke=MUTED))
    parts.append(_text(490, y3 + 28, "本周闭环", size=14, weight=600))
    parts.append(_text(
        490, y3 + 54,
        "零件（Day 1–5）→ 集成（Day 6）→ 复盘与下周准备（Day 7）",
        size=13, fill=MUTED,
    ))
    key_output = ""
    if day6 and day6["output"]:
        key_output = day6["output"]
    elif day7 and day7["output"]:
        key_output = day7["output"]
    summary = ("关键产出：" + key_output) if key_output else "关键产出：见 Day 6 / Day 7 的今日产出"
    for line_no, line in enumerate(_wrap(summary, 40, 2)):
        parts.append(_text(490, y3 + 80 + line_no * 18, line, size=13))

    # 图注。
    parts.append(_text(
        490, height - 16,
        f"图 {number}：第 {number} 周整体框架——零件、集成与复盘的 7 天闭环",
        size=12, fill=MUTED,
    ))
    parts.append("</svg>")
    return "\n".join(parts)
