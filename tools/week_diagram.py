#!/usr/bin/env python3
"""每周整体框架图（信息密集时间轴版）。

规范（与教程图片一致）：纸面 #fdfaf4、楷体手写字体栈、抖动波浪边框、
色板 #3a4657/#6b7686/#e0884f、面板 #fffdf8/#fbeadd。

信息层次：
1. 头部：周主题、所属阶段、阶段内位置、24 周进度刻度；
2. 时间轴：7 张日卡（编号气泡 + 类型徽标 + 标题 + 学习/实践/产出三要素）；
3. 底部：本周真实体量（正文字数、技术图、代码文件、run_all 天数、预计投入），
   由构建期从 tutorials/ 实际统计。
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
BULLET_RE = re.compile(r"^-\s*\*\*(学习|实践|产出)\*\*[：:]\s*(.+)$")

WIDTH = 980
CARD_X = 126
CARD_W = 830
CARD_H = 148
CARD_GAP = 12


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _wrap(text: str, per_line: int, max_lines: int) -> list[str]:
    text = text.strip()
    if len(text) <= per_line:
        return [text]
    lines = [text[i : i + per_line] for i in range(0, len(text), per_line)]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        lines[-1] = (last[: per_line - 1] + "…") if len(last) >= per_line else last
    return lines


def _text(x, y, content, *, size=13, fill=INK, weight=500, anchor="start"):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" '
        f'font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
        f'font-weight="{weight}">{_escape(content)}</text>'
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
    # 每条边细分为 ~26px 段，保证手绘抖动。
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


def _wavy_circle(rng, cx, cy, r, *, stroke=INK, width=2.4, fill=PAPER):
    pts = []
    steps = 14
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return _wavy_path(rng, pts, stroke=stroke, width=width, fill=fill, close=True)


def _arrow_head(rng, x, y, angle, *, stroke, size=9):
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


def _day_type(day: int) -> tuple[str, str]:
    """(徽标文字, 颜色)。"""
    if day == 168:
        return "最终验收", INK
    if day % 7 == 0:
        return "复盘日", INK
    if day % 7 == 6:
        return "集成日", ACCENT
    return "学习日", MUTED


def render_week_framework_svg(week: dict) -> str:
    """week 需含 {number, title, phase, lines, stats, phase_index, week_in_phase}。"""
    rng = random.Random(2026_1100 + week["number"])
    number = week["number"]
    days = [d for d in _parse_days(week["lines"])
            if (d["day"] - 1) // 7 + 1 == number][:7]
    stats = week.get("stats", {})
    phase_index = week.get("phase_index", 0)
    week_in_phase = week.get("week_in_phase", 1)

    header_h = 152
    timeline_top = header_h
    timeline_h = len(days) * (CARD_H + CARD_GAP) - CARD_GAP
    stats_y = timeline_top + timeline_h + 18
    stats_h = 104
    height = stats_y + stats_h + 44

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{height}" viewBox="0 0 {WIDTH} {height}">',
        f'<rect x="0" y="0" width="{WIDTH}" height="{height}" fill="{PAPER}"/>',
        # 标题与副标题。
        _text(WIDTH / 2, 46, week["title"], size=26, weight=600, anchor="middle"),
        _text(
            WIDTH / 2, 74,
            f"{week['phase']} ｜ 第 {number}/24 周 · 阶段内第 {week_in_phase}/4 周",
            size=14, fill=MUTED, anchor="middle",
        ),
    ]

    # ---- 24 周进度刻度 ----
    tick_y = 100
    tick_x0, tick_x1 = 72, 908
    step = (tick_x1 - tick_x0) / 23
    ticks = [f'<path d="M {tick_x0} {tick_y} L {tick_x1} {tick_y}" '
             f'stroke="{MUTED}" stroke-width="1.2" stroke-linecap="round" '
             f'stroke-dasharray="1 6" opacity="0.55"/>']
    for i in range(24):
        x = tick_x0 + i * step
        current = i + 1 == number
        h = 13 if current else 7
        color = ACCENT if current else MUTED
        ticks.append(
            f'<path d="M {x:.1f} {tick_y - h / 2} L {x:.1f} {tick_y + h / 2}" '
            f'stroke="{color}" stroke-width="{2.6 if current else 1.6}" '
            f'stroke-linecap="round"/>'
        )
    # 阶段分隔刻度（每 4 周）。
    for phase_mark in range(1, 6):
        x = tick_x0 + phase_mark * 4 * step - step * 2
        ticks.append(
            f'<path d="M {x:.1f} {tick_y - 10} L {x:.1f} {tick_y + 10}" '
            f'stroke="{MUTED}" stroke-width="1" stroke-linecap="round" '
            f'stroke-dasharray="2 3" opacity="0.7"/>'
        )
    ticks.append(_text(
        tick_x0 + (number - 1) * step, tick_y - 14, f"W{number}",
        size=11.5, fill=ACCENT, weight=600, anchor="middle",
    ))
    ticks.append(_text(tick_x0, tick_y + 22, "W1", size=10, fill=MUTED, anchor="middle"))
    ticks.append(_text(tick_x1, tick_y + 22, "W24", size=10, fill=MUTED, anchor="middle"))
    parts.extend(ticks)

    # ---- 时间轴主干 ----
    spine_x = 88
    if days:
        first_cy = timeline_top + CARD_H / 2
        last_cy = timeline_top + (len(days) - 1) * (CARD_H + CARD_GAP) + CARD_H / 2
        parts.append(_wavy_path(
            rng, [(spine_x, first_cy), (spine_x, last_cy + 34)],
            stroke=MUTED, width=2.0,
        ))
        parts.append(_arrow_head(
            rng, spine_x, last_cy + 36, math.pi / 2, stroke=MUTED, size=10,
        ))

    # ---- 7 张日卡 ----
    for index, day in enumerate(days):
        y = timeline_top + index * (CARD_H + CARD_GAP)
        label, color = _day_type(day["day"])
        is_integration = day["day"] % 7 == 6
        is_review = day["day"] % 7 == 0
        card_fill = PANEL_ACCENT if is_integration else PANEL
        stroke = ACCENT if is_integration else (INK if is_review else MUTED)
        stroke_w = 3.0 if is_integration or is_review else 2.2
        parts.append(_wavy_rect(
            rng, CARD_X, y, CARD_W, CARD_H,
            fill=card_fill, stroke=stroke, width=stroke_w,
        ))
        # 编号气泡。
        parts.append(_wavy_circle(
            rng, spine_x, y + CARD_H / 2, 17,
            stroke=ACCENT if is_integration else INK,
            width=2.6 if is_integration else 2.2,
        ))
        parts.append(_text(
            spine_x, y + CARD_H / 2 + 4.5, str(day["day"]),
            size=11.5, weight=600, anchor="middle",
        ))
        # 行 1：Day NNN + 类型徽标。
        parts.append(_text(
            CARD_X + 24, y + 28, f"Day {day['day']}", size=13.5, fill=MUTED,
            weight=600,
        ))
        parts.append(_text(
            CARD_X + 104, y + 28, f"· {label} ·", size=12.5, fill=color,
            weight=600,
        ))
        # 行 2–3：标题（最多两行）。
        for line_no, line in enumerate(_wrap(day["title"], 24, 2)):
            parts.append(_text(
                CARD_X + 196, y + 28 + line_no * 21, line, size=14.5, weight=600,
            ))
        # 三要素。
        bullet_y = y + 76
        for key, prefix in (("学习", "学习"), ("实践", "实践"), ("产出", "产出")):
            value = day["bullets"].get(key, "")
            for line_no, line in enumerate(_wrap(
                    f"{prefix}：{value}" if value else f"{prefix}：—", 42, 1)):
                parts.append(_text(
                    CARD_X + 24, bullet_y, line, size=12.5, fill=INK,
                ))
            bullet_y += 22

    # ---- 底部：本周体量统计 ----
    parts.append(_wavy_rect(
        rng, 58, stats_y, 864, stats_h, fill=PANEL, stroke=MUTED,
    ))
    parts.append(_text(490, stats_y + 28, "本周体量（来自已发布教程的实际统计）",
                       size=13.5, weight=600, anchor="middle"))
    stat_items = [
        f"教程正文 {stats.get('chars_wan', '—')} 万字",
        f"技术图 {stats.get('images', '—')} 张",
        f"代码/IR 文件 {stats.get('code_files', '—')} 个",
        f"run_all 一键脚本 {stats.get('run_all_days', '—')} 天",
    ]
    parts.append(_text(
        490, stats_y + 56, " ｜ ".join(stat_items), size=13, anchor="middle",
    ))
    parts.append(_text(
        490, stats_y + 82,
        f"预计投入：学习 {stats.get('learning_min', 0) // 60} 小时 "
        f"{stats.get('learning_min', 0) % 60} 分钟 ＋ 实践 "
        f"{stats.get('practice_min', 0) // 60} 小时 "
        f"{stats.get('practice_min', 0) % 60} 分钟（阶段 {phase_index + 1}/6）",
        size=13, fill=MUTED, anchor="middle",
    ))

    # 图注。
    parts.append(_text(
        WIDTH / 2, height - 16,
        f"图 {number}：第 {number} 周整体框架——每日学习/实践/产出、"
        f"集成与复盘节点及本周实际体量",
        size=12, fill=MUTED, anchor="middle",
    ))
    parts.append("</svg>")
    return "\n".join(parts)
