"""内容 JSON API（/api/v1/）。"""
from django.http import Http404, JsonResponse
from django.urls import path
from django.views.decorators.http import require_GET

from .models import ContentDayVersion, SiteState


@require_GET
def days_list(request):
    """GET /api/v1/days/ —— 当前 active release 的日课清单（公开、可缓存）。"""
    release = SiteState.get_active_release()
    if release is None:
        return JsonResponse(
            {"code": "NO_ACTIVE_RELEASE", "message": "内容尚未发布"}, status=503
        )
    rows = (
        ContentDayVersion.objects.filter(release=release)
        .order_by("day_id")
        .values("day_id", "metadata_json", "content_sha")
    )
    return JsonResponse({
        "schema_version": 1,
        "content_commit": release.commit,
        "days": [
            {**row["metadata_json"], "content_sha": row["content_sha"]} for row in rows
        ],
    })


@require_GET
def day_detail(request, day_id: str):
    """GET /api/v1/days/{day_id}/ —— 单日元数据 + 渲染 HTML。"""
    release = SiteState.get_active_release()
    if release is None:
        return JsonResponse(
            {"code": "NO_ACTIVE_RELEASE", "message": "内容尚未发布"}, status=503
        )
    version = (
        ContentDayVersion.objects.filter(release=release, day_id=day_id)
        .values("metadata_json", "rendered_html", "content_sha")
        .first()
    )
    if version is None:
        raise Http404
    return JsonResponse({
        "schema_version": 1,
        "content_commit": release.commit,
        **version["metadata_json"],
        "content_sha": version["content_sha"],
        "rendered_html": version["rendered_html"],
    })


urlpatterns = [
    path("days/", days_list, name="api_days"),
    path("days/<str:day_id>/", day_detail, name="api_day_detail"),
]
