#!/usr/bin/env python3
"""每周整体框架图（v3：大字号 + 仓库实测完整色板）。

色板与字号均来自对仓库 554 张教程 SVG 的统计（抽样 50 张）：
- 墨色 #3b352d/#84796a；蓝系 #4a7fa5/#5d8fc9/#dbe7f6；绿系 #5a8a5a；
  琥珀 #a8772e/#d08a4e/#fbeadd；玫红 #d96c5c/#b0605a；纸面 #fdfaf4/#fdfbf6。
- 类型分色：学习日=蓝、集成日=琥珀、复盘日=绿、最终验收=玫红。
- 学习/实践/产出三要素标签分别以蓝/绿/琥珀加粗强调。
手绘风格不变：抖动波浪边框、楷体字体栈、圆角线帽。
"""

from __future__ import annotations

import html
import math
import random
import re

FONT = "Xiaolai, 'Kaiti SC', KaiTi, STKaiti, 'Comic Sans MS', 'Segoe Print', cursive"
INK = "#3b352d"
MUTED = "#84796a"
PAPER = "#fdfaf4"
PANEL = "#fdfbf6"
PANEL_ACCENT = "#fbeadd"

BLUE_TEXT, BLUE_STROKE, BLUE_FILL = "#4a7fa5", "#5d8fc9", "#dbe7f6"
GREEN_TEXT, GREEN_STROKE = "#5a8a5a", "#5a8a5a"
AMBER_TEXT, AMBER_STROKE = "#a8772e", "#d08a4e"
ROSE_TEXT, ROSE_STROKE = "#b0605a", "#d96c5c"

DAY_RE = re.compile(r"^###\s*第\s*(\d+)\s*天[｜|:：]\s*(.+)$")
BULLET_RE = re.compile(r"^-\s*\*\*(学习|实践|产出)\*\*[：:]\s*(.+)$")

WIDTH = 1200
CARD_X = 150
CARD_W = 1000
CARD_H = 140
CARD_GAP = 14
BUBBLE_X = 100


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _wrap1(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _text(x, y, content, *, size=15.5, fill=INK, weight=500, anchor="start"):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" '
        f'font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
        f'font-weight="{weight}">{_escape(content)}</text>'
    )


def _label_value_text(x, y, label, value, *, label_color, size=15.5):
    """「标签：值」行 —— 标签加粗分色，值墨色。"""
    value = _wrap1(value, 58)
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}">'
        f'<tspan font-weight="700" fill="{label_color}">{_escape(label)}</tspan>'
        f'<tspan fill="{INK}">：{_escape(value)}</tspan></text>'
    )


def _wavy_path(rng, points, *, stroke, width=2.4, fill="none", close=False):
    jittered = [
        (px + rng.uniform(-1.7, 1.7), py + rng.uniform(-1.7, 1.7))
        for px, py in points
    ]
    d = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in jittered)
    if close:
        d += " Z"
    return (
        f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _wavy_rect(rng, x, y, w, h, *, fill=None, stroke=INK, width=2.4):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    dense = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + [pts[0]]):
        steps = max(2, int(math.hypot(bx - ax, by - ay) / 26))
        for i in range(1, steps + 1):
            t = i / steps
            dense.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    parts = []
    if fill:
        parts.append(_wavy_path(rng, dense, stroke="none", fill=fill, close=True))
    parts.append(_wavy_path(rng, dense, stroke=stroke, width=width, close=True))
    return "".join(parts)


def _wavy_circle(rng, cx, cy, r, *, stroke=INK, width=2.4, fill="#ffffff"):
    pts = []
    steps = 14
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return _wavy_path(rng, pts, stroke=stroke, width=width, fill=fill, close=True)


def _arrow_head(rng, x, y, angle, *, stroke, size=10):
    left = (x - size * math.cos(angle - 0.42), y - size * math.sin(angle - 0.42))
    right = (x - size * math.cos(angle + 0.42), y - size * math.sin(angle + 0.42))
    return (
        f'<polygon points="{x:.1f},{y:.1f} {left[0]:.1f},{left[1]:.1f} '
        f'{right[0]:.1f},{right[1]:.1f}" fill="{stroke}"/>'
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
                "bullets": {},
            }
            days.append(current)
            continue
        if current is not None:
            bullet = BULLET_RE.match(line)
            if bullet and bullet.group(1) not in current["bullets"]:
                current["bullets"][bullet.group(1)] = bullet.group(2).strip()
    return days


def _day_theme(day: int) -> dict:
    """类型 → (徽标文字, 描边, 卡片底色, 标签文字色, 标签底色)。"""
    if day == 168:
        return {
            "label": "最终验收", "stroke": ROSE_STROKE, "fill": PANEL,
            "text": ROSE_TEXT, "chip_fill": "#f6e3e0",
        }
    if day % 7 == 0:
        return {
            "label": "复盘日", "stroke": GREEN_STROKE, "fill": PANEL,
            "text": GREEN_TEXT, "chip_fill": "#e9e4d8",
        }
    if day % 7 == 6:
        return {
            "label": "集成日", "stroke": AMBER_STROKE, "fill": PANEL_ACCENT,
            "text": AMBER_TEXT, "chip_fill": "#f6e7d2",
        }
    return {
        "label": "学习日", "stroke": BLUE_STROKE, "fill": PANEL,
        "text": BLUE_TEXT, "chip_fill": BLUE_FILL,
    }


BULLET_COLORS = {"学习": BLUE_TEXT, "实践": GREEN_TEXT, "产出": AMBER_TEXT}


def render_week_framework_svg(week: dict) -> str:
    rng = random.Random(2026_1200 + week["number"])
    number = week["number"]
    days = [d for d in _parse_days(week["lines"])
            if (d["day"] - 1) // 7 + 1 == number][:7]
    stats = week.get("stats", {})
    phase_index = week.get("phase_index", 0)
    week_in_phase = week.get("week_in_phase", 1)

    header_h = 164
    timeline_top = header_h
    timeline_h = len(days) * (CARD_H + CARD_GAP) - CARD_GAP
    stats_y = timeline_top + timeline_h + 20
    stats_h = 116
    height = stats_y + stats_h + 52

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{height}" viewBox="0 0 {WIDTH} {height}">',
        f'<rect x="0" y="0" width="{WIDTH}" height="{height}" fill="{PAPER}"/>',
        _text(WIDTH / 2, 54, week["title"], size=30, weight=700, anchor="middle"),
        _text(
            WIDTH / 2, 86,
            f"{week['phase']} ｜ 第 {number}/24 周 · 阶段内第 {week_in_phase}/4 周",
            size=16, fill=MUTED, anchor="middle",
        ),
    ]

    # ---- 24 周进度刻度 ----
    tick_y = 120
    tick_x0, tick_x1 = 90, 1110
    step = (tick_x1 - tick_x0) / 23
    parts.append(
        f'<path d="M {tick_x0} {tick_y} L {tick_x1} {tick_y}" stroke="{MUTED}" '
        f'stroke-width="1.2" stroke-linecap="round" stroke-dasharray="1 6" opacity="0.55"/>'
    )
    for i in range(24):
        x = tick_x0 + i * step
        current = i + 1 == number
        h = 15 if current else 8
        color = AMBER_STROKE if current else MUTED
        parts.append(
            f'<path d="M {x:.1f} {tick_y - h / 2} L {x:.1f} {tick_y + h / 2}" '
            f'stroke="{color}" stroke-width="{3.0 if current else 1.6}" '
            f'stroke-linecap="round"/>'
        )
    for phase_mark in range(1, 6):
        x = tick_x0 + phase_mark * 4 * step - step * 2
        parts.append(
            f'<path d="M {x:.1f} {tick_y - 11} L {x:.1f} {tick_y + 11}" '
            f'stroke="{MUTED}" stroke-width="1" stroke-linecap="round" '
            f'stroke-dasharray="2 3" opacity="0.7"/>'
        )
    parts.append(_text(
        tick_x0 + (number - 1) * step, tick_y - 18, f"W{number}",
        size=14, fill=AMBER_TEXT, weight=700, anchor="middle",
    ))
    parts.append(_text(tick_x0, tick_y + 26, "W1", size=12, fill=MUTED, anchor="middle"))
    parts.append(_text(tick_x1, tick_y + 26, "W24", size=12, fill=MUTED, anchor="middle"))

    # ---- 时间轴主干 ----
    if days:
        first_cy = timeline_top + CARD_H / 2
        last_cy = timeline_top + (len(days) - 1) * (CARD_H + CARD_GAP) + CARD_H / 2
        parts.append(_wavy_path(
            rng, [(BUBBLE_X, first_cy), (BUBBLE_X, last_cy + 38)],
            stroke=MUTED, width=2.2,
        ))
        parts.append(_arrow_head(
            rng, BUBBLE_X, last_cy + 40, math.pi / 2, stroke=MUTED, size=11,
        ))

    # ---- 7 张日卡 ----
    for index, day in enumerate(days):
        y = timeline_top + index * (CARD_H + CARD_GAP)
        theme = _day_theme(day["day"])
        is_key = day["day"] % 7 in (0, 6) or day["day"] == 168
        parts.append(_wavy_rect(
            rng, CARD_X, y, CARD_W, CARD_H,
            fill=theme["fill"], stroke=theme["stroke"],
            width=3.2 if is_key else 2.4,
        ))
        # 编号气泡（白底 + 类型色描边）。
        parts.append(_wavy_circle(
            rng, BUBBLE_X, y + CARD_H / 2, 20,
            stroke=theme["stroke"], width=2.8,
        ))
        parts.append(_text(
            BUBBLE_X, y + CARD_H / 2 + 5, str(day["day"]),
            size=14, weight=700, anchor="middle",
        ))
        # 行 1：Day NNN + 类型徽标（手绘 chip）+ 标题。
        parts.append(_text(
            CARD_X + 28, y + 34, f"Day {day['day']}", size=15, fill=MUTED,
            weight=700,
        ))
        chip_w, chip_h = 96, 30
        chip_x, chip_y = CARD_X + 122, y + 12
        parts.append(_wavy_rect(
            rng, chip_x, chip_y, chip_w, chip_h,
            fill=theme["chip_fill"], stroke=theme["stroke"], width=1.8,
        ))
        parts.append(_text(
            chip_x + chip_w / 2, chip_y + 21, theme["label"],
            size=14, fill=theme["text"], weight=700, anchor="middle",
        ))
        parts.append(_text(
            CARD_X + 246, y + 34, _wrap1(day["title"], 36),
            size=19, weight=700,
        ))
        # 行 2–4：学习 / 实践 / 产出（标签分色加粗）。
        bullet_y = y + 68
        for key in ("学习", "实践", "产出"):
            value = day["bullets"].get(key, "—")
            parts.append(_label_value_text(
                CARD_X + 28, bullet_y, key, value,
                label_color=BULLET_COLORS[key],
            ))
            bullet_y += 26

    # ---- 底部：本周体量统计（数值分色）----
    parts.append(_wavy_rect(
        rng, 70, stats_y, 1060, stats_h, fill=PANEL, stroke=MUTED, width=2.2,
    ))
    parts.append(_text(
        600, stats_y + 32, "本周体量（来自已发布教程的实际统计）",
        size=16, weight=700, anchor="middle",
    ))
    parts.append(
        f'<text x="600" y="{stats_y + 62}" font-family="{FONT}" font-size="15.5" '
        f'text-anchor="middle">'
        f'<tspan fill="{INK}">教程正文 </tspan>'
        f'<tspan font-weight="700" fill="{BLUE_TEXT}">{stats.get("chars_wan", "—")} 万字</tspan>'
        f'<tspan fill="{MUTED}"> ｜ </tspan>'
        f'<tspan fill="{INK}">技术图 </tspan>'
        f'<tspan font-weight="700" fill="{GREEN_TEXT}">{stats.get("images", "—")} 张</tspan>'
        f'<tspan fill="{MUTED}"> ｜ </tspan>'
        f'<tspan fill="{INK}">代码/IR 文件 </tspan>'
        f'<tspan font-weight="700" fill="{AMBER_TEXT}">{stats.get("code_files", "—")} 个</tspan>'
        f'<tspan fill="{MUTED}"> ｜ </tspan>'
        f'<tspan fill="{INK}">run_all 脚本 </tspan>'
        f'<tspan font-weight="700" fill="{ROSE_TEXT}">{stats.get("run_all_days", "—")} 天</tspan>'
        f'</text>'
    )
    learning = stats.get("learning_min", 0)
    practice = stats.get("practice_min", 0)
    parts.append(_text(
        600, stats_y + 92,
        f"预计投入：学习 {learning // 60}h{learning % 60}m ＋ 实践 "
        f"{practice // 60}h{practice % 60}m（阶段 {phase_index + 1}/6）",
        size=15, fill=MUTED, anchor="middle",
    ))

    parts.append(_text(
        WIDTH / 2, height - 18,
        f"图 {number}：第 {number} 周整体框架——每日学习/实践/产出、"
        f"集成与复盘节点及本周实际体量",
        size=13.5, fill=MUTED, anchor="middle",
    ))
    parts.append("</svg>")
    return "\n".join(parts)
