#!/usr/bin/env python3
"""Build the daily tutorials as a static GitHub Pages website."""

import html
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TUTORIALS_DIR = ROOT / "tutorials"
PLAN_PATH = ROOT / "AI芯片编译器学习计划.md"
PUBLIC_DIR = ROOT / "public"
STATIC_DIR = ROOT / "static"
GITHUB_REPO_URL = "https://github.com/hzchenxiaobin/ai-chip-compiler-learning-plan"
TITLE_RE = re.compile(r"^#\s+第\s*(\d+)\s*天[：:]\s*(.+)$")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def escape_for_template_string(text):
    return (
        text.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
        .replace("</script>", "\\x3c/script>")
    )


def load_tutorials():
    tutorials = []
    for readme in sorted(TUTORIALS_DIR.glob("day-*/README.md")):
        day_dir = readme.parent
        try:
            directory_day = int(day_dir.name.removeprefix("day-"))
        except ValueError as exc:
            raise ValueError(f"教程目录名称无效：{day_dir.name}") from exc

        text = readme.read_text(encoding="utf-8")
        lines = text.strip().splitlines()
        match = TITLE_RE.match(lines[0]) if lines else None
        if not match:
            raise ValueError(f"无法从首行解析教程标题：{readme}")
        if int(match.group(1)) != directory_day:
            raise ValueError(f"教程目录与标题天数不一致：{readme}")

        for target in IMAGE_RE.findall(text):
            target = target.strip().split()[0].strip("<>")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            if not (day_dir / target).is_file():
                raise FileNotFoundError(f"教程图片不存在：{day_dir / target}")

        tutorials.append(
            {
                "number": directory_day,
                "slug": day_dir.name,
                "title": f"第 {directory_day} 天：{match.group(2).strip()}",
                "markdown": "\n".join(lines[1:]).strip(),
                "source": day_dir,
            }
        )

    if not tutorials:
        raise ValueError("没有找到 tutorials/day-N/README.md")
    return tutorials


def day_pills(tutorials, root_prefix="", current_day=None):
    return [
        {
            "num": day["number"],
            "label": f"Day {day['number']}",
            "title": day["title"],
            "href": f"{root_prefix}tutorials/{day['slug']}/",
            "active": current_day == day["number"],
        }
        for day in tutorials
    ]


def page_template(
    title,
    markdown,
    *,
    root_prefix="",
    pills=None,
    back_link=None,
    prev_link=None,
    next_link=None,
    home=False,
):
    escaped_title = html.escape(title)
    escaped_markdown = escape_for_template_string(markdown)

    pills_html = ""
    body_class = "vp-page vp-home" if home else "vp-page"
    if pills:
        def pill_link(item, css_class="vp-pill"):
            active = " active" if item.get("active") else ""
            current = ' aria-current="page"' if item.get("active") else ""
            return (
                f'<a class="{css_class}{active}" href="{item["href"]}"'
                f' title="{html.escape(item["title"], quote=True)}"{current}>'
                f'{html.escape(str(item["label"]))}</a>'
            )

        if len(pills) > 10:
            active_day = next((item for item in pills if item.get("active")), None)
            toggle_label = active_day["label"] if active_day else f"{len(pills)} 天教程"
            weeks = {}
            for item in pills:
                weeks.setdefault((item["num"] - 1) // 7 + 1, []).append(item)
            groups = []
            for week, items in weeks.items():
                links = "".join(pill_link(item, "vp-day-link") for item in items)
                groups.append(
                    f'<section class="vp-day-week"><div class="vp-day-week-title">'
                    f'<strong>第 {week} 周</strong><span>{items[0]["label"]}–{items[-1]["label"]}</span>'
                    f'</div><div class="vp-day-week-links">{links}</div></section>'
                )
            pills_html = (
                '<nav class="vp-nav-pills vp-nav-pills-grouped" aria-label="每日教程导航">'
                f'<details class="vp-day-nav"><summary class="vp-day-nav-toggle">'
                f'<span>{toggle_label}</span><span class="vp-day-nav-chevron" aria-hidden="true">⌄</span>'
                f'</summary><div class="vp-day-menu"><div class="vp-day-menu-header">'
                f'<strong>按周学习</strong><span>已发布 {len(pills)} 天</span></div>'
                f'<div class="vp-day-weeks">{"".join(groups)}</div></div></details></nav>'
            )
            body_class += " vp-page-grouped-nav"
        else:
            pills_html = '<nav class="vp-nav-pills">' + "".join(pill_link(item) for item in pills) + "</nav>"

    back_html = ""
    if back_link:
        href, label = back_link
        back_html = f'<nav class="back-nav"><a href="{href}">← {html.escape(label)}</a></nav>'

    def pager(link, css_class, label):
        if not link:
            return "<span></span>"
        href, text = link
        return (
            f'<a class="pager-link {css_class}" href="{href}"><span class="desc">{label}</span>'
            f'<span class="title">{html.escape(text)}</span></a>'
        )

    pager_html = ""
    if prev_link or next_link:
        pager_html = (
            '<div class="prev-next">'
            + pager(prev_link, "prev", "上一篇")
            + pager(next_link, "next", "下一篇")
            + "</div>"
        )

    if home:
        main_html = f'<main class="home-main">{markdown}</main>'
        render_call = "VPPage.init();"
    else:
        main_html = f"""<div class="vp-main"><div class="vp-doc-wrap"><div class="vp-container">
        <div class="vp-content"><div class="vp-content-container">
            {back_html}
            <main class="main"><article class="vp-doc">
                <h1>{escaped_title}</h1>
                <div id="doc-content"></div>
            </article></main>
            <footer class="vp-doc-footer">{pager_html}</footer>
        </div></div>
        <div class="vp-aside"><div class="vp-aside-container"><div class="vp-aside-content">
            <nav class="vp-outline" aria-labelledby="outline-title">
                <div class="outline-title" id="outline-title">本页目录</div>
                <div class="outline-content"><div class="outline-marker"></div>
                    <ul class="outline-root" id="outline-root"></ul>
                </div>
            </nav>
        </div></div></div>
    </div></div></div>"""
        render_call = "VPPage.render(pageMarkdown);"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="24 周、168 天 AI 芯片编译器实战学习计划：Modern C++、MLIR、图优化、Lowering、Tiling、LLVM 与 Runtime。">
    <title>{escaped_title} · AI 芯片编译器学习计划</title>
    <script>
    (function() {{
        try {{
            var t = localStorage.getItem('vp-theme') || 'dark';
            if (t === 'dark') document.documentElement.classList.add('dark');
        }} catch (e) {{ document.documentElement.classList.add('dark'); }}
    }})();
    </script>
    <link rel="stylesheet" href="{root_prefix}css/vp-solution.css?v=6">
    <script src="{root_prefix}js/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="{root_prefix}js/markdown-math.js"></script>
    <script src="{root_prefix}js/prism.min.js"></script>
    <script src="{root_prefix}js/prism-c.min.js"></script>
    <script src="{root_prefix}js/prism-cpp.min.js"></script>
    <script src="{root_prefix}js/prism-bash.min.js"></script>
    <script src="{root_prefix}js/prism-python.min.js"></script>
</head>
<body class="{body_class}">
    <header class="vp-navbar">
        <div class="vp-navbar-inner">
            <a class="vp-brand" href="{root_prefix}index.html">AI Chip <span>Compiler</span></a>
            {pills_html}
            <div class="vp-navbar-spacer"></div>
            <nav class="vp-menu" aria-label="站点导航">
                <a href="{root_prefix}plan.html">168 天计划</a>
                <a class="vp-roadmap-link" href="{root_prefix}index.html#roadmap">学习路线</a>
                <a href="{root_prefix}index.html#tutorials">每日教程</a>
                <a class="vp-github-link" href="{GITHUB_REPO_URL}" target="_blank" rel="noopener noreferrer">GitHub ↗</a>
            </nav>
            <div class="vp-appearance">
                <button class="vp-switch" type="button" aria-label="切换深色/浅色外观">
                    <span class="check"><span class="icon sun">☀</span><span class="icon moon">☾</span></span>
                </button>
            </div>
        </div>
    </header>
    {main_html}
    <footer class="vp-footer"><span>AI 芯片编译器学习计划 · Deployed on GitHub Pages</span></footer>
    <button class="vp-back-to-top" aria-label="回到顶部">↑</button>
    <script src="{root_prefix}js/vp-solution.js?v=5"></script>
    <script>
        const pageMarkdown = `{escaped_markdown}`;
        try {{
            if (typeof marked === 'undefined' || !window.VPPage) {{
                throw new Error('页面脚本加载失败。');
            }}
            {render_call}
        }} catch (err) {{
            const content = document.getElementById('doc-content');
            if (content) content.textContent = '页面渲染失败：' + err.message;
            console.error('Markdown render error:', err);
        }}
    </script>
</body>
</html>
"""


ROADMAP = [
    (
        "阶段一",
        "C++ 与编译器基础",
        "Modern C++ → 计算图 IR → SSA → 优化 Pass",
        [
            "搭建 CMake 工程，实现最小 Tensor",
            "Graph / Node / Value 与 Use-Def",
            "CFG、支配关系与活跃变量分析",
            "常量折叠、DCE、CSE 与 PassManager",
        ],
    ),
    (
        "阶段二",
        "MLIR 核心能力",
        "IR 结构 → mini Dialect → Shape 推导 → 算子融合",
        [
            "Operation / Region / Block 与类型系统",
            "ODS 定义 mini Dialect 与 Verifier",
            "Shape Inference / Canonicalization / Fold",
            "算子融合与多使用者约束",
        ],
    ),
    (
        "阶段三",
        "AI 计算图与图优化",
        "Layout → 冗余消除 → Cost Model → 数值验证",
        [
            "Shape、Stride、Broadcast 与动态 Shape",
            "Layout 转换与冗余算子消除",
            "融合流量、资源代价与 Cost Model",
            "浮点误差、INT8 量化与数值验证",
        ],
    ),
    (
        "阶段四",
        "Lowering、Tiling 与性能",
        "循环 IR → Tiling → 内存规划 → 自动调优",
        [
            "DialectConversion 与三重循环生成",
            "循环顺序、Tiling、Unroll 与实验",
            "生命周期、内存复用与 Double Buffering",
            "Auto-tuning、GFLOPS 与 Roofline",
        ],
    ),
    (
        "阶段五",
        "端到端编译与 Runtime",
        "LLVM → 统一编译入口 → Runtime → 回归体系",
        [
            "LLVM Dialect、LLVM IR 与 JIT / AOT",
            "统一 CLI、IR Dump 与端到端项目",
            "动态 Shape、特化、内存与异步模型",
            "随机测试、Pass 定位与性能回归",
        ],
    ),
    (
        "阶段六",
        "项目收口与面试转化",
        "扩展方向 → 性能归因 → 项目材料 → 最终验收",
        [
            "扩展方向设计、实现与验收",
            "性能基线、瓶颈分析与优化验证",
            "架构、Pass、Lowering 与复现材料",
            "面试标准回答与最终项目验收",
        ],
    ),
]


def plan_heading_slug(text):
    slug = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", slug.strip())).strip("-")


def build_home(tutorials):
    plan_text = PLAN_PATH.read_text(encoding="utf-8")
    week_titles = {
        int(number): title.strip()
        for number, title in re.findall(r"^## 第 (\d+) 周：(.+)$", plan_text, re.MULTILINE)
    }

    phases = []
    for phase_index, (label, title, description, summaries) in enumerate(ROADMAP):
        week_cards = []
        for offset, summary in enumerate(summaries):
            number = phase_index * 4 + offset + 1
            week_title = week_titles[number]
            anchor = plan_heading_slug(f"第 {number} 周：{week_title}")
            week_cards.append(
                f'<a class="week-card" href="plan.html#{anchor}">'
                f'<div class="week-card-top"><span class="week-number">W{number}</span>'
                '<span class="week-arrow" aria-hidden="true">→</span></div>'
                f'<h4>{html.escape(week_title)}</h4><p>{html.escape(summary)}</p></a>'
            )
        phases.append(
            '<section class="phase-block">'
            f'<div class="phase-heading"><span class="phase-badge">{label}</span>'
            f'<h3>{html.escape(title)}</h3><p>{html.escape(description)}</p></div>'
            f'<div class="week-cards">{"".join(week_cards)}</div></section>'
        )

    tutorial_cards = []
    for day in tutorials:
        title = re.sub(r"^第\s*\d+\s*天[：:]\s*", "", day["title"])
        goal = re.search(r"^> \*\*今日目标\*\*：(.+)$", day["markdown"], re.MULTILINE)
        summary = re.sub(r"[`*_]", "", goal.group(1)) if goal else "概念讲解、技术图解、动手实现与结果验证。"
        tutorial_cards.append(
            f'<a class="tutorial-card" href="tutorials/{day["slug"]}/">'
            f'<div class="week-card-top"><span class="week-number">Day {day["number"]}</span>'
            '<span class="week-arrow" aria-hidden="true">→</span></div>'
            f'<h3>{html.escape(title)}</h3><p>{html.escape(summary)}</p>'
            '<span class="tutorial-card-link">开始阅读 <span aria-hidden="true">↗</span></span></a>'
        )

    first_day = tutorials[0]
    content = f"""
<section class="home-hero">
    <div class="home-hero-inner">
        <div class="hero-badge">工程实战 · 24 周渐进式路线</div>
        <h1>AI 芯片编译器 <span>168 天学习计划</span></h1>
        <p class="hero-subtitle">从「写好 Modern C++」进阶到「交付端到端编译器」</p>
        <p class="hero-description">贯通编译器 IR、MLIR、图优化、Lowering、Tiling、LLVM 与 Runtime<br> 每天 1～1.5 小时，每周集成与复盘</p>
        <div class="hero-actions">
            <a class="hero-button hero-button-primary" href="tutorials/{first_day["slug"]}/">开始 Day {first_day["number"]} <span aria-hidden="true">→</span></a>
            <a class="hero-button hero-button-secondary" href="plan.html">查看完整计划</a>
        </div>
        <div class="hero-stats" aria-label="学习计划概览">
            <div><strong>24</strong><span>周学习路线</span></div>
            <div><strong>168</strong><span>每日实战任务</span></div>
            <div><strong>6</strong><span>阶段能力进阶</span></div>
            <div><strong>1</strong><span>端到端编译器</span></div>
        </div>
    </div>
</section>
<section class="home-section roadmap-section" id="roadmap">
    <div class="section-heading"><h2>学习路线</h2><p>六个阶段、24 个主题，从 Modern C++ 一路走到端到端 AI 芯片编译器。</p></div>
    {"".join(phases)}
</section>
<section class="home-section tutorials-section" id="tutorials">
    <div class="section-heading section-heading-row"><div><h2>每日教程</h2><p>已发布 {len(tutorials)} 篇图文教程，每篇都包含讲解、实践、练习与验收。</p></div><span class="section-status">持续更新</span></div>
    <div class="tutorial-cards">{"".join(tutorial_cards)}</div>
</section>
"""
    output = page_template("AI 芯片编译器学习计划", content, home=True)
    (PUBLIC_DIR / "index.html").write_text(output, encoding="utf-8")


def build_plan(tutorials):
    text = PLAN_PATH.read_text(encoding="utf-8")
    text = re.sub(r"^\s*#\s+.+\n", "", text, count=1)
    output = page_template(
        "AI 芯片编译器 168 天学习计划",
        text,
        pills=day_pills(tutorials),
        back_link=("index.html", "返回首页"),
    )
    (PUBLIC_DIR / "plan.html").write_text(output, encoding="utf-8")


def build_tutorials(tutorials):
    for index, day in enumerate(tutorials):
        output_dir = PUBLIC_DIR / "tutorials" / day["slug"]
        output_dir.mkdir(parents=True, exist_ok=True)
        images = day["source"] / "images"
        if images.exists():
            shutil.copytree(images, output_dir / "images", dirs_exist_ok=True)

        prev_link = None
        next_link = None
        if index > 0:
            previous = tutorials[index - 1]
            prev_link = (f"../{previous['slug']}/", previous["title"])
        if index + 1 < len(tutorials):
            following = tutorials[index + 1]
            next_link = (f"../{following['slug']}/", following["title"])

        output = page_template(
            day["title"],
            day["markdown"],
            root_prefix="../../",
            pills=day_pills(tutorials, root_prefix="../../", current_day=day["number"]),
            back_link=("../../index.html#tutorials", "返回每日教程"),
            prev_link=prev_link,
            next_link=next_link,
        )
        (output_dir / "index.html").write_text(output, encoding="utf-8")
        print(f"Generated tutorials/{day['slug']}/index.html")


def main():
    tutorials = load_tutorials()
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir()
    shutil.copytree(STATIC_DIR / "css", PUBLIC_DIR / "css")
    shutil.copytree(STATIC_DIR / "js", PUBLIC_DIR / "js")
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")

    build_home(tutorials)
    build_plan(tutorials)
    build_tutorials(tutorials)
    print(f"Website built successfully: {len(tutorials)} tutorials in {PUBLIC_DIR}")


if __name__ == "__main__":
    main()
