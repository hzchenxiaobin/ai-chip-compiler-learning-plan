"""公开内容页面（设计文档 §4）。

公开页面（首页/日课/周/阶段/计划）服务端渲染完整 HTML；
匿名响应缓存 300s（键含页面缓存世代 epoch），缓存命中时完全不触碰数据库——
MySQL 不可用时已缓存公开页面继续可读（§9.4）。
登录响应不缓存任何用户字段。
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .importer.rendering import render_markdown_html
from .models import ContentDay, ContentDayVersion, ReleaseStatus, SiteState
from .phases import ROADMAP

WEEK_TITLE_RE = re.compile(r"^## 第 (\d+) 周[：:](.+)$", re.MULTILINE)

TYPE_LABELS = {
    "concept_lab": "概念与实验",
    "environment_lab": "环境闭环",
    "integration": "集成",
    "review": "复盘",
    "documentation": "文档",
    "presentation": "表达",
    "final_assessment": "最终验收",
}
TASK_LABELS = (
    ("reading", "阅读"), ("exercise", "练习"),
    ("experiment", "实验"), ("acceptance", "验收"),
)
TASK_STATUS_LABELS = (
    ("not_started", "未开始"), ("in_progress", "进行中"),
    ("done", "已完成"), ("blocked", "有卡点"),
)
STATE_LABELS = {
    "not_started": "未开始", "in_progress": "进行中",
    "ready_for_review": "待验收", "completed": "已完成", "blocked": "有卡点",
}


def get_active_release():
    return SiteState.get_active_release()


def _release_or_503(request):
    """内容版本查询；区分「未发布」与「数据库不可用」（设计文档 §9.4）。"""
    try:
        release = get_active_release()
    except DatabaseError:
        return None, render(request, "content/maintenance.html", status=503)
    if release is None:
        return release, render(
            request, "content/no_content.html", status=503,
            context={"hint": "内容尚未导入：请先运行 python manage.py import_tutorial --commit HEAD"},
        )
    return release, None


def _week_titles(release) -> dict[int, str]:
    titles = {}
    for number, title in WEEK_TITLE_RE.findall(release.plan_markdown or ""):
        titles[int(number)] = title.strip()
    return titles


def _version_rows(release, **filters):
    rows = (
        ContentDayVersion.objects.filter(release=release, **filters)
        .order_by("day_id")
        .values("day_id", "metadata_json", "content_sha")
    )
    return list(rows)


def _anonymous_cache(request, prefix, render_fn):
    """匿名页面缓存优先（设计文档 §9.4：MySQL 不可用时缓存页继续可读）。

    先查 Redis（世代键 + 页面键），命中则完全不触碰数据库；
    未命中才执行 render_fn（惰性查库）；只缓存 200 响应；
    Redis 异常时直接渲染。登录用户始终直渲染（不缓存用户字段）。
    """
    if request.user.is_authenticated:
        return render_fn()
    epoch = SiteState.page_epoch()
    if epoch > 0:
        try:
            html = cache.get(f"{prefix}:{epoch}")
            if html is not None:
                return HttpResponse(html)
        except Exception:
            pass  # Redis 不可用：直接渲染。
    response = render_fn()
    if request.user.is_authenticated:  # render_fn 过程中登录则不缓存。
        return response
    if epoch > 0 and response.status_code == 200:
        try:
            cache.set(f"{prefix}:{epoch}", response.content, 300)
        except Exception:
            pass
    return response


def _task_groups(meta, day_view):
    groups = []
    for task_id, label in TASK_LABELS:
        applicable = task_id in meta["required_tasks"]
        current = "not_started"
        if day_view:
            current = day_view["tasks"].get(task_id, {}).get("status", "not_started")
            if not applicable:
                current = "not_applicable"
        options = [
            {"value": value, "label": status_label, "checked": value == current}
            for value, status_label in TASK_STATUS_LABELS
        ]
        groups.append({
            "task_id": task_id, "label": label, "applicable": applicable,
            "options": options,
        })
    return groups


# ---------------------------------------------------------------------------
# 首页
# ---------------------------------------------------------------------------

@require_GET
def home(request):
    def render_page():
        release, error = _release_or_503(request)
        if error:
            return error
        days = _version_rows(release)
        week_titles = _week_titles(release)
        context = {
            "release": release,
            "days": days,
            "week_titles": week_titles,
            "phases": ROADMAP,
            "day_count": len(days),
        }
        if request.user.is_authenticated:
            from apps.learning.services import get_dashboard_view, get_week_view_model

            all_metas = [row["metadata_json"] for row in days]
            context["view"] = get_dashboard_view(request.user, release, all_metas)
            # 本周关键产出与卡点摘要（设计文档 §4.1）。
            target = context["view"]["continue_target"]
            target_week = target["meta"]["week"]
            week_metas = [m for m in all_metas if m["week"] == target_week]
            context["week_view"] = get_week_view_model(request.user, week_metas)
            context["target_week"] = target_week
        return render(request, "content/home.html", context)

    return _anonymous_cache(request, "page:home", render_page)


# ---------------------------------------------------------------------------
# 日课页（URL 保持 /tutorials/week-NNN/day-NNN/）
# ---------------------------------------------------------------------------

@require_GET
def day_page(request, week: int, day_id: str):
    def render_page():
        release, error = _release_or_503(request)
        if error:
            return error
        version = (
            ContentDayVersion.objects.filter(release=release, day_id=day_id)
            .select_related("day_ref")
            .first()
        )
        if version is None or version.day_ref.week != week:
            raise Http404("日课不存在")

        meta = version.metadata_json
        prev_version = None
        next_version = None
        if meta["day"] > 1:
            prev_version = ContentDayVersion.objects.filter(
                release=release, day_id=f"day-{meta['day'] - 1:03d}"
            ).values("day_id", "metadata_json").first()
        if meta["day"] < 168:
            next_version = ContentDayVersion.objects.filter(
                release=release, day_id=f"day-{meta['day'] + 1:03d}"
            ).values("day_id", "metadata_json").first()

        context = {
            "release": release,
            "version": version,
            "meta": meta,
            "type_label": TYPE_LABELS.get(meta["type"], meta["type"]),
            "rendered_html": version.rendered_html,
            "source_zip_url": (
                settings.PUBLIC_ASSET_URL + meta["source_zip"]
                if meta.get("source_zip") else None
            ),
            "prev": prev_version,
            "next": next_version,
            "week_title": _week_titles(release).get(meta["week"], ""),
            "day_view": None,
            "state_label": None,
        }
        if request.user.is_authenticated:
            from apps.learning.services import get_day_view_model

            context["day_view"] = get_day_view_model(request.user, release, meta)
            context["state_label"] = STATE_LABELS.get(
                context["day_view"]["overall"], ""
            )
        context["task_groups"] = _task_groups(meta, context["day_view"])
        response = render(request, "content/day.html", context)
        if request.user.is_authenticated:
            response["Cache-Control"] = "private, no-store"
            from apps.learning.services import touch_visit

            touch_visit(request.user, meta)
        return response

    return _anonymous_cache(request, f"page:day:{day_id}", render_page)


# ---------------------------------------------------------------------------
# 周页 / 阶段页 / 计划页
# ---------------------------------------------------------------------------

@require_GET
def week_page(request, week: int):
    def render_page():
        release, error = _release_or_503(request)
        if error:
            return error
        days = [row for row in _version_rows(release)
                if row["metadata_json"]["week"] == week]
        if not days:
            raise Http404("周不存在")
        context = {
            "release": release,
            "week": week,
            "days": days,
            "week_title": _week_titles(release).get(week, ""),
            "phase": days[0]["metadata_json"]["phase"],
        }
        if request.user.is_authenticated:
            from apps.learning.services import get_week_view_model

            days_meta = [row["metadata_json"] for row in days]
            context["week_view"] = get_week_view_model(request.user, days_meta)
        return render(request, "content/week.html", context)

    return _anonymous_cache(request, f"page:week:{week}", render_page)


@require_GET
def phase_page(request, phase: int):
    if not 1 <= phase <= 6:
        raise Http404("阶段不存在")

    def render_page():
        release, error = _release_or_503(request)
        if error:
            return error
        days = [row for row in _version_rows(release)
                if row["metadata_json"]["phase"] == phase]
        weeks = {}
        for row in days:
            weeks.setdefault(row["metadata_json"]["week"], []).append(row)
        context = {
            "release": release,
            "phase": phase,
            "phase_info": ROADMAP[phase - 1],
            "week_groups": [weeks[w] for w in sorted(weeks)],
            "week_titles": _week_titles(release),
        }
        if request.user.is_authenticated:
            from apps.learning.services import get_phase_view_model

            context["phase_view"] = get_phase_view_model(
                request.user, [row["metadata_json"] for row in days]
            )
        return render(request, "content/phase.html", context)

    return _anonymous_cache(request, f"page:phase:{phase}", render_page)


@require_GET
def plan_page(request):
    def render_page():
        release, error = _release_or_503(request)
        if error:
            return error
        if not release.plan_markdown:
            raise Http404("计划文件未导入")
        plan_html = render_markdown_html(release.plan_markdown)
        return render(request, "content/plan.html", {
            "release": release, "plan_html": plan_html, "nav_plan": True,
        })

    return _anonymous_cache(request, "page:plan", render_page)


# ---------------------------------------------------------------------------
# 静态资产 / SEO / 健康检查
# ---------------------------------------------------------------------------

@require_GET
def public_asset(request, key: str):
    """公开资产（图片/源码 ZIP）。开发环境由 Django 提供；生产建议 Nginx 直出。"""
    root = Path(settings.PUBLIC_ASSET_ROOT).resolve()
    target = (root / key).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise Http404("资源不存在")
    content_type = "application/zip" if target.suffix == ".zip" else "application/octet-stream"
    if target.suffix in {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        content_type = (
            "image/svg+xml" if target.suffix == ".svg"
            else f"image/{target.suffix.lstrip('.')}"
        )
    response = FileResponse(target.open("rb"), content_type=content_type)
    response["Cache-Control"] = "public, max-age=86400"
    return response


def _absolute(request, path: str) -> str:
    return request.build_absolute_uri(path)


@require_GET
def sitemap_xml(request):
    """站点地图（设计文档 §10.4）。数据库故障时输出最小集。"""
    try:
        release = get_active_release()
    except DatabaseError:
        release = None
    urls = [
        _absolute(request, "/"), _absolute(request, "/plan/"),
        _absolute(request, "/search/"),
    ]
    if release is not None:
        for row in _version_rows(release):
            meta = row["metadata_json"]
            urls.append(_absolute(request, "/" + meta["url"]))
            urls.append(_absolute(request, f"/weeks/week-{meta['week']}/"))
            urls.append(_absolute(request, f"/phases/phase-{meta['phase']}/"))
    urls = sorted(set(urls))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        loc = (
            url.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        parts.append(f"<url><loc>{loc}</loc></url>")
    parts.append("</urlset>")
    return HttpResponse("\n".join(parts), content_type="application/xml")


@require_GET
def robots_txt(request):
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /dashboard/\n"
        "Disallow: /settings/\n"
        f"Sitemap: {_absolute(request, '/sitemap.xml')}\n"
    )
    return HttpResponse(body, content_type="text/plain")


def healthz(request):
    try:
        release = get_active_release()
        release_part = f'"{release.commit[:12]}"' if release else "null"
        status = "ok" if release else "no_content"
    except DatabaseError:
        release_part, status = "null", "db_unavailable"
    return HttpResponse(
        content_type="application/json",
        content='{"status":"%s","active_release":%s,"now":"%s"}'
        % (status, release_part, timezone.now().isoformat()),
    )
