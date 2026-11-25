#!/usr/bin/env python3
"""学习模块页面构建（WP-03）。

对应 docs/development/03_页面集成与交互.md：
- 日课页：任务卡（四项 radio）+ 源码资源卡 + body 数据属性注入
- 周页 /weeks/week-NNN/、阶段页 /phases/phase-N/、搜索页 /search/、设置页 /settings/
- 全部页面先输出静态可读 HTML，JavaScript 只增强（data-learning-* 挂载点）

本模块不直接依赖 build.py；页面外壳通过 ``render_page`` 回调复用
build.page_template，避免循环导入。
"""

from __future__ import annotations

import html
from pathlib import Path

# ---------------------------------------------------------------------------
# 展示映射
# ---------------------------------------------------------------------------

TYPE_LABELS = {
    "concept_lab": "概念+实验",
    "environment_lab": "环境搭建",
    "integration": "集成",
    "review": "复盘",
    "documentation": "文档",
    "presentation": "展示",
    "final_assessment": "最终验收",
}

TASK_LABELS = {
    "reading": "阅读",
    "exercise": "练习",
    "experiment": "实验",
    "acceptance": "验收",
}

STATUS_LABELS = {
    "not_started": "未开始",
    "in_progress": "进行中",
    "done": "已完成",
    "blocked": "有卡点",
}


def esc(value):
    return html.escape(str(value), quote=True)


# ---------------------------------------------------------------------------
# 资源引用（learning.css / app.js）
# ---------------------------------------------------------------------------


def learning_head_links(root_prefix=""):
    return f'<link rel="stylesheet" href="{esc(root_prefix)}css/learning.css?v=1">'


def learning_script_tags(root_prefix=""):
    return f'<script type="module" src="{esc(root_prefix)}js/learning/app.js?v=1"></script>'


def days_url(root_prefix=""):
    return f"{root_prefix}learning/days.json"


# ---------------------------------------------------------------------------
# 日课页：body 属性 + 前置卡
# ---------------------------------------------------------------------------


def tutorial_body_attrs(record, root_prefix="", base_path=""):
    return {
        "data-page-type": "tutorial",
        "data-day-id": record["day_id"],
        "data-base-path": base_path,
        "data-content-sha": record["content_sha"],
        "data-days-url": days_url(root_prefix),
    }


def tutorial_prelude(record, root_prefix=""):
    """日课页正文前的学习任务卡与源码资源卡（静态可读，JS 增强）。"""
    day_id = record["day_id"]
    applicable = record["required_tasks"]
    time = record["time"]
    skills = record["skills"]

    meta_bits = [
        f'<span class="learning-type-badge learning-type-{esc(record["type"])}">{esc(TYPE_LABELS[record["type"]])}</span>',
        f'<span class="learning-meta-item">预计 {esc(time["learning_min"])}＋{esc(time["practice_min"])} 分钟</span>',
    ]
    if record["key_output"]:
        meta_bits.append('<span class="learning-meta-item learning-key-output">★ 关键产出日</span>')
    if skills:
        chips = "".join(f'<span class="learning-skill-chip">{esc(s)}</span>' for s in skills)
        meta_bits.append(f'<span class="learning-meta-item learning-skills">{chips}</span>')

    fieldsets = []
    for task_id in ("reading", "exercise", "experiment", "acceptance"):
        if task_id not in applicable:
            continue
        options = "".join(
            f'<label class="learning-task-option">'
            f'<input type="radio" name="task-{esc(day_id)}-{esc(task_id)}" value="{esc(status)}" '
            f'data-task-status="{esc(status)}"> {esc(label)}</label>'
            for status, label in STATUS_LABELS.items()
        )
        fieldsets.append(
            f'<fieldset class="learning-task" data-task-id="{esc(task_id)}">'
            f"<legend>{esc(TASK_LABELS[task_id])}</legend>{options}</fieldset>"
        )
    not_applicable = [TASK_LABELS[t] for t in ("reading", "exercise", "experiment", "acceptance") if t not in applicable]
    na_note = (
        f'<p class="learning-task-na">本日类型不要求：{"、".join(not_applicable)}</p>' if not_applicable else ""
    )

    task_card = f"""
<section class="learning-card" data-learning="day-progress" data-day-id="{esc(day_id)}">
  <div class="learning-card-head"><h2>学习任务</h2>
  <span class="learning-save-state" data-learning="save-state" aria-live="polite"></span></div>
  <div class="learning-day-meta">{''.join(meta_bits)}</div>
  <noscript><p class="learning-noscript-note">学习进度仅在启用 JavaScript 后记录；正文阅读与源码下载不受影响。</p></noscript>
  <div class="learning-tasks">{''.join(fieldsets)}</div>
  {na_note}
  <p class="learning-review-hint" data-learning="review-hint" hidden>本日教程或代码已更新。你的任务状态已保留，请复核变化后再继续。
    <button type="button" class="learning-button" data-learning="acknowledge-button">已复核新版内容</button></p>
  <div class="learning-day-state" data-learning="day-state" aria-live="polite"></div>
  <label class="learning-planned-toggle"><input type="checkbox" data-learning="planned-toggle"> 设为当前学习计划</label>
</section>"""

    resource_items = []
    if record["source_zip"]:
        resource_items.append(
            f'<li><a href="{esc(root_prefix)}downloads/{esc(day_id)}-source.zip" download>下载源码 ZIP</a>'
            "<span class=\"learning-res-note\">（不含冻结输出）</span></li>"
        )
    if record["code_url"]:
        resource_items.append(
            f'<li><a href="{esc(record["code_url"])}" target="_blank" rel="noopener noreferrer">在 GitHub 查看代码</a></li>'
        )
    if record["outputs_url"]:
        resource_items.append(
            f'<li><a href="{esc(record["outputs_url"])}" target="_blank" rel="noopener noreferrer">查看冻结输出</a></li>'
        )
    if record["run_all"]:
        resource_items.append(
            "<li><span class=\"learning-res-label\">运行方式：</span><code>unzip "
            f"{esc(day_id)}-source.zip -d {esc(day_id)}-source &amp;&amp; cd {esc(day_id)}-source &amp;&amp; bash run_all.sh</code></li>"
        )
    else:
        resource_items.append('<li><span class="learning-res-label">运行方式：</span>查看本日 README 中的实际步骤</li>')

    resource_card = ""
    if resource_items:
        resource_card = f"""
<section class="learning-card" data-learning="day-resources">
  <h2>源码与实验资源</h2>
  <ul class="learning-resource-list">{''.join(resource_items)}</ul>
</section>"""

    return f'<div class="learning-prelude">{task_card}{resource_card}</div>'


# ---------------------------------------------------------------------------
# 首页学习区
# ---------------------------------------------------------------------------


def home_learning_sections(root_prefix="", first_day_href="#", first_day_label="Day 001"):
    return f"""
<section class="home-section learning-home-section" id="my-learning">
  <div class="section-heading"><h2>我的学习</h2><p>学习记录保存在本浏览器（IndexedDB），不会自动上传；换设备请先在「我的数据」导出备份。</p></div>
  <div class="learning-home-grid">
    <div class="learning-card learning-continue-card" data-learning="continue">
      <h3>继续学习</h3>
      <p class="learning-continue-static">学习进度仅在启用 JavaScript 后读取。可以从 <a href="{esc(first_day_href)}">{esc(first_day_label)}</a> 开始，或查看<a href="{esc(root_prefix)}plan.html">完整学习计划</a>。</p>
    </div>
    <div class="learning-card" data-learning="overview">
      <h3>学习概览</h3>
      <p class="learning-overview-static">启用 JavaScript 后，这里会显示已完成、进行中、卡点与待复核的课程数量。</p>
    </div>
    <form class="learning-card learning-quick-search" data-learning="quick-search" action="{esc(root_prefix)}search/" method="get" role="search">
      <h3><label for="learning-quick-q">快速检索</label></h3>
      <div class="learning-quick-row">
        <input id="learning-quick-q" type="search" name="q" placeholder="搜索课程，如 MLIR、Tile、Roofline" autocomplete="off">
        <button class="learning-button" type="submit">搜索</button>
      </div>
      <p class="learning-res-note">搜索在本地进行，搜索词不上传。</p>
    </form>
  </div>
</section>"""


# ---------------------------------------------------------------------------
# 周页 / 阶段页 / 搜索页 / 设置页
# ---------------------------------------------------------------------------


def _day_row(record, root_prefix, show_week=False):
    badges = [f'<span class="learning-type-badge learning-type-{esc(record["type"])}">{esc(TYPE_LABELS[record["type"]])}</span>']
    if record["key_output"]:
        badges.append('<span class="learning-key-output">★ 关键产出</span>')
    badges.append('<span class="learning-day-state" data-learning="day-state-mark" hidden></span>')
    prefix = f"W{record['week']} · " if show_week else ""
    objective = record["objective"]
    if len(objective) > 140:
        objective = objective[:137] + "…"
    time = record["time"]
    return f"""
<li class="learning-day-row" data-day-id="{esc(record['day_id'])}">
  <a class="learning-day-link" href="{esc(root_prefix)}tutorials/week-{record['week']:03d}/{record['day_id']}/">
    <span class="learning-day-num">{prefix}Day {record['day']}</span>
    <span class="learning-day-title">{esc(record['title'])}</span>
    <span class="learning-day-badges">{''.join(badges)}</span>
    <span class="learning-day-objective">{esc(objective)}</span>
    <span class="learning-day-time">{esc(time['learning_min'])}＋{esc(time['practice_min'])} 分钟</span>
  </a>
</li>"""


def build_week_pages(days, output_dir, base_path, render_page, roadmap):
    """生成 24 个周页：静态 7 天清单 + 进度挂载点。root_prefix 固定为 ../../。"""
    output_dir = Path(output_dir)
    root_prefix = "../../"
    week_theme = {}
    for phase_index, (_label, _title, _desc, summaries) in enumerate(roadmap):
        for offset, summary in enumerate(summaries):
            week_theme[phase_index * 4 + offset + 1] = summary

    weeks = sorted({d["week"] for d in days})
    for week in weeks:
        week_days = [d for d in days if d["week"] == week]
        phase = week_days[0]["phase"]
        phase_info = roadmap[phase - 1]
        day_rows = "".join(_day_row(d, root_prefix) for d in week_days)
        total_learning = sum(d["time"]["learning_min"] for d in week_days)
        total_practice = sum(d["time"]["practice_min"] for d in week_days)

        prev_html = f'<a class="pager-link prev" href="{root_prefix}weeks/week-{week-1:03d}/"><span class="desc">上一周</span><span class="title">第 {week-1} 周</span></a>' if week > 1 else "<span></span>"
        next_html = f'<a class="pager-link next" href="{root_prefix}weeks/week-{week+1:03d}/"><span class="desc">下一周</span><span class="title">第 {week+1} 周</span></a>' if week < max(weeks) else "<span></span>"

        content = f"""
<nav class="learning-breadcrumb"><a href="{root_prefix}index.html">首页</a> › <a href="{root_prefix}phases/phase-{phase}/">{esc(phase_info[0])}·{esc(phase_info[1])}</a> › <span>第 {week} 周</span></nav>
<p class="learning-page-desc">本属{esc(phase_info[0])}（{esc(phase_info[1])}）；预计学习 {total_learning} 分钟＋实践 {total_practice} 分钟。Day 6 为集成日、Day 7 为复盘日（最终周按实际类型覆盖）。</p>
<div class="learning-card" data-learning="week-progress" data-week="{week}">
  <h2>本周进度</h2>
  <p class="learning-progress-static">学习进度仅在启用 JavaScript 后读取；下方清单始终可用。</p>
</div>
<h2>本周 7 天</h2>
<ul class="learning-day-list">{day_rows}</ul>
<a class="learning-continue-link" data-learning="continue-week" href="#" hidden>继续本周 →</a>
<nav class="prev-next">{prev_html}{next_html}</nav>
<a class="learning-phase-link" href="{root_prefix}phases/phase-{phase}/">查看所属阶段 →</a>"""
        output = render_page(
            f"第 {week} 周 · AI 芯片编译器学习计划",
            content,
            root_prefix=root_prefix,
            static_html=content,
            body_attrs={
                "data-page-type": "week",
                "data-week": str(week),
                "data-base-path": base_path,
                "data-days-url": days_url(root_prefix),
            },
        )
        target = output_dir / "weeks" / f"week-{week:03d}" / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")


def build_phase_pages(days, output_dir, base_path, render_page, roadmap):
    """生成 6 个阶段页：能力目标、四周导航、28 天清单与关键产出证据清单。"""
    output_dir = Path(output_dir)
    root_prefix = "../../"
    for phase in range(1, 7):
        label, title, description, summaries = roadmap[phase - 1]
        phase_days = [d for d in days if d["phase"] == phase]
        week_cards = []
        for offset, summary in enumerate(summaries):
            week = (phase - 1) * 4 + offset + 1
            week_cards.append(
                f'<a class="learning-week-card" href="{root_prefix}../weeks/week-{week:03d}/">'
                f'<span class="learning-week-num">W{week}</span><span class="learning-week-theme">{esc(summary)}</span></a>'
            )
        day_rows = "".join(_day_row(d, root_prefix, show_week=True) for d in phase_days)
        key_outputs = [d for d in phase_days if d["key_output"]]
        key_items = "".join(
            f'<li>Day {d["day"]} {esc(d["title"])}（{esc(TYPE_LABELS[d["type"]])}）</li>' for d in key_outputs
        )
        content = f"""
<nav class="learning-breadcrumb"><a href="{root_prefix}index.html">首页</a> › <a href="../index.html">阶段</a> › <span>{esc(label)}</span></nav>
<p class="learning-page-desc">{esc(description)}</p>
<div class="learning-card" data-learning="phase-progress" data-phase="{phase}">
  <h2>阶段进度</h2>
  <p class="learning-progress-static">学习进度仅在启用 JavaScript 后读取；阶段主状态由四周关键产出与第 28 天综合复盘共同派生。</p>
</div>
<h2>四周递进</h2>
<div class="learning-week-cards">{''.join(week_cards)}</div>
<h2>关键产出综合证据清单</h2>
<ul class="learning-key-output-list">{key_items}</ul>
<h2>28 天清单</h2>
<ul class="learning-day-list">{day_rows}</ul>
<a class="learning-continue-link" data-learning="continue-phase" href="#" hidden>继续本阶段 →</a>"""
        output = render_page(
            f"{label}·{title} · AI 芯片编译器学习计划",
            content,
            root_prefix=root_prefix,
            static_html=content,
            body_attrs={
                "data-page-type": "phase",
                "data-phase": str(phase),
                "data-base-path": base_path,
                "data-days-url": days_url(root_prefix),
            },
        )
        target = output_dir / "phases" / f"phase-{phase}" / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")


def build_phases_index(output_dir, base_path, render_page, roadmap):
    output_dir = Path(output_dir)
    root_prefix = "../"
    cards = []
    for phase in range(1, 7):
        label, title, description, _summaries = roadmap[phase - 1]
        cards.append(
            f'<a class="learning-phase-index-card" href="{root_prefix}phases/phase-{phase}/">'
            f'<span class="phase-badge">{esc(label)}</span><h3>{esc(title)}</h3><p>{esc(description)}</p></a>'
        )
    content = f"""
<p class="learning-page-desc">每阶段 4 周、28 天；从 Modern C++ 一路走到端到端 AI 编译器与项目收口。</p>
<div class="learning-phase-index-grid">{''.join(cards)}</div>"""
    output = render_page(
        "学习阶段 · AI 芯片编译器学习计划",
        content,
        root_prefix=root_prefix,
        static_html=content,
        body_attrs={"data-page-type": "phases", "data-base-path": base_path, "data-days-url": days_url(root_prefix)},
    )
    target = output_dir / "phases" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output, encoding="utf-8")


def build_search_page(output_dir, base_path, render_page):
    output_dir = Path(output_dir)
    root_prefix = "../"
    type_options = "".join(f'<option value="{esc(t)}">{esc(label)}</option>' for t, label in TYPE_LABELS.items())
    phase_options = '<option value="">全部阶段</option>' + "".join(
        f'<option value="{p}">阶段 {p}</option>' for p in range(1, 7)
    )
    week_options = '<option value="">全部周</option>' + "".join(
        f'<option value="{w}">第 {w} 周</option>' for w in range(1, 25)
    )
    content = f"""
<p class="learning-page-desc">搜索在你的浏览器本地进行：搜索词不写入日志、不上传服务器、不进入分析系统。</p>
<form class="learning-search-form" data-learning="search-form" role="search">
  <div class="learning-search-row">
    <label class="visually-hidden" for="learning-search-q">搜索关键词</label>
    <input id="learning-search-q" type="search" name="q" placeholder="关键词、命令、错误码，如 mlir-opt / Roofline / 内存规划" autocomplete="off">
    <button class="learning-button learning-button-primary" type="submit">搜索</button>
  </div>
  <div class="learning-search-filters">
    <label>范围 <select name="scope" data-learning="scope-select">
      <option value="lite">课程信息</option>
      <option value="full">全文（六阶段正文）</option>
    </select></label>
    <label>阶段 <select name="phase" data-learning="phase-select">{phase_options}</select></label>
    <label>周 <select name="week" data-learning="week-select">{week_options}</select></label>
    <label>类型 <select name="type" data-learning="type-select"><option value="">全部类型</option>{type_options}</select></label>
  </div>
</form>
<p class="learning-search-status" data-learning="lite-status" aria-live="polite"></p>
<p class="learning-search-status" data-learning="phase-status" aria-live="polite"></p>
<div class="learning-search-results" data-learning="search-results"></div>
<noscript>
  <p class="learning-noscript-note">搜索需要启用 JavaScript。你可以浏览<a href="{root_prefix}plan.html">168 天总计划</a>，或前往
  <a href="https://github.com/hzchenxiaobin/ai-chip-compiler-learning-plan" target="_blank" rel="noopener noreferrer">GitHub 仓库</a>使用站内搜索。</p>
</noscript>"""
    output = render_page(
        "搜索 · AI 芯片编译器学习计划",
        content,
        root_prefix=root_prefix,
        static_html=content,
        body_attrs={"data-page-type": "search", "data-base-path": base_path, "data-days-url": days_url(root_prefix)},
    )
    target = output_dir / "search" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output, encoding="utf-8")


def build_settings_page(output_dir, base_path, render_page):
    output_dir = Path(output_dir)
    root_prefix = "../"
    content = f"""
<p class="learning-page-desc">学习记录默认保存在此浏览器（IndexedDB），不会自动上传。换浏览器、清除站点数据或使用隐私窗口可能导致记录不可用——导出备份是你的责任，本站不做云同步。</p>
<section class="learning-card" data-learning="storage-status">
  <h2>存储状态</h2>
  <p class="learning-progress-static">存储状态在启用 JavaScript 后显示：可保存 / 临时状态 / 配额异常。</p>
</section>
<section class="learning-card" data-learning="data-management">
  <h2>导出进度备份</h2>
  <p>导出为 JSON 文件（包含任务状态、计划与访问时间），可用于备份或迁移到其他浏览器。</p>
  <button class="learning-button" type="button" data-learning="export-button">导出学习进度</button>
  <p class="learning-action-result" data-learning="export-result" aria-live="polite"></p>
  <h2>导入进度备份</h2>
  <p>导入前会完整预检并显示预览；默认合并模式不删除现有记录。相同版本但内容不同的记录会等待你逐项选择。</p>
  <form data-learning="import-form">
    <label class="learning-file-label">选择 JSON 备份文件
      <input type="file" accept=".json,application/json" data-learning="import-file"></label>
    <fieldset class="learning-import-mode">
      <legend>导入模式</legend>
      <label class="learning-task-option"><input type="radio" name="import-mode" value="merge" checked> 合并（默认）</label>
      <label class="learning-task-option"><input type="radio" name="import-mode" value="replace"> 替换（破坏性，先自动备份）</label>
    </fieldset>
    <button class="learning-button" type="submit">预检并导入</button>
  </form>
  <div class="learning-import-preview" data-learning="import-preview"></div>
  <div class="learning-import-conflicts" data-learning="import-conflicts"></div>
  <p class="learning-action-result" data-learning="import-result" aria-live="polite"></p>
  <p><button class="learning-button" type="button" data-learning="restore-backup">从替换前备份恢复</button>
     用最近一次“替换导入”前的完整备份覆盖当前进度（替换模式自动创建）。</p>
  <h2>清空与重置</h2>
  <p><button class="learning-button learning-button-danger" type="button" data-learning="clear-progress">清空学习记录…</button>
     清空 progress 数据，不影响主题等偏好；需二次确认，建议先导出。</p>
  <p><button class="learning-button" type="button" data-learning="clear-prefs">清除全部本地偏好</button>
     仅重置主题、侧栏等 UI 偏好键，不影响学习记录。</p>
  <p class="learning-action-result" data-learning="clear-result" aria-live="polite"></p>
</section>
<noscript><p class="learning-noscript-note">导入导出需要启用 JavaScript。教程阅读与下载不受影响。</p></noscript>"""
    output = render_page(
        "我的数据 · AI 芯片编译器学习计划",
        content,
        root_prefix=root_prefix,
        static_html=content,
        body_attrs={"data-page-type": "settings", "data-base-path": base_path, "data-days-url": days_url(root_prefix)},
    )
    target = output_dir / "settings" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output, encoding="utf-8")

