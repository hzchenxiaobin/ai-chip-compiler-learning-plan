"""搜索页面与 API（设计文档 §4.4、§9.3）。

搜索表单由服务端处理 GET，结果支持无 JavaScript 翻页；
ES Modules 仅增加防抖建议与取消旧请求。
"""
from django.db import DatabaseError
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.content.models import SiteState

from . import service

PAGE_SIZE = 20
TYPES = [
    ("", "全部类型"),
    ("concept_lab", "概念与实验"),
    ("environment_lab", "环境闭环"),
    ("integration", "集成"),
    ("review", "复盘"),
    ("documentation", "文档"),
    ("presentation", "表达"),
    ("final_assessment", "最终验收"),
]


def _params(request):
    query = (request.GET.get("q") or "").strip()[:200]
    phase_raw = request.GET.get("phase") or ""
    week_raw = request.GET.get("week") or ""
    day_type = request.GET.get("type") or ""
    phase = int(phase_raw) if phase_raw.isdigit() and 1 <= int(phase_raw) <= 6 else None
    week = int(week_raw) if week_raw.isdigit() and 1 <= int(week_raw) <= 24 else None
    if day_type and day_type not in dict(TYPES[1:]):
        day_type = ""
    return query, phase, week, day_type


def _run_search(release, request):
    """执行查询；数据库异常时返回可重试的失败状态（不伪装成无结果）。"""
    query, phase, week, day_type = _params(request)
    if not query:
        return query, phase, week, day_type, [], 0, None
    try:
        offset = service.decode_cursor(request.GET.get("cursor"))
        items, total, next_cursor = service.search(
            release, query, phase=phase, week=week, day_type=day_type,
            page_size=PAGE_SIZE, offset=offset,
        )
        return query, phase, week, day_type, items, total, next_cursor
    except DatabaseError:
        raise SearchUnavailable()
        # 由调用方渲染失败状态。


class SearchUnavailable(Exception):
    pass


@require_GET
def search_page(request):
    release = SiteState.get_active_release()
    if release is None:
        return render(request, "content/no_content.html", status=503)
    try:
        query, phase, week, day_type, items, total, next_cursor = _run_search(release, request)
    except SearchUnavailable:
        return render(request, "search/search.html", {
            "release": release,
            "week_numbers": range(1, 25),
            "query": "", "phase": "", "week": "", "type": "",
            "types": TYPES, "items": [], "total": 0,
            "next_cursor": None, "page_size": PAGE_SIZE,
            "search_failed": True,
        }, status=503)
    return render(request, "search/search.html", {
        "release": release,
        "week_numbers": range(1, 25),
        "query": query,
        "phase": phase or "",
        "week": week or "",
        "type": day_type,
        "types": TYPES,
        "items": items,
        "total": total,
        "next_cursor": next_cursor,
        "page_size": PAGE_SIZE,
        "prev_cursor": _prev_cursor(request),
        "matched_fields_count": True,
        "nav_search": True,
    })


def _prev_cursor(request):
    """上一页 cursor（无 JS 翻页的基础路径）。"""
    query = (request.GET.get("q") or "").strip()
    if not query:
        return None
    offset = service.decode_cursor(request.GET.get("cursor"))
    if offset <= 0:
        return None
    return service.encode_cursor(max(0, offset - PAGE_SIZE))


@require_GET
def api_search(request):
    release = SiteState.get_active_release()
    if release is None:
        return {"error": "NO_ACTIVE_RELEASE"}
    query, phase, week, day_type, items, total, next_cursor = _run_search(release, request)
    return {
        "schema_version": 1,
        "content_commit": release.commit,
        "query": query,
        "filters": {"phase": phase, "week": week, "type": day_type},
        "results": items,
        "total_days": total,
        "next_cursor": next_cursor,
    }
