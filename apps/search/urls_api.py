"""搜索 JSON API 路由（/api/v1/search/）。"""
from django.db import DatabaseError
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.http import require_GET

from . import views as search_views
from .views import SearchUnavailable


@require_GET
def search_endpoint(request):
    try:
        result = search_views.api_search(request)
    except (DatabaseError, SearchUnavailable):
        return JsonResponse(
            {"code": "SEARCH_UNAVAILABLE",
             "message": "搜索服务暂时不可用，请稍后重试"},
            status=503,
        )
    if "error" in result:
        return JsonResponse(result, status=503)
    return JsonResponse(result)


urlpatterns = [
    path("search/", search_endpoint, name="api_search"),
]
