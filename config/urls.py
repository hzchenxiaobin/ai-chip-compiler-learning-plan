"""根 URL 配置。

公开路由（设计文档 §3.1）：
/                     首页
/plan/                完整计划
/tutorials/week-NNN/day-NNN/   日课（URL 保持稳定）
/weeks/week-NNN/      周页
/phases/phase-N/      阶段页
/search/              搜索页
/login/ /register/    账号
/dashboard/           我的学习
/settings/            设置
/api/v1/              JSON API
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.content.urls")),
    path("", include("apps.search.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.learning.urls")),
    path("api/v1/", include("apps.content.urls_api")),
    path("api/v1/", include("apps.learning.urls_api")),
    path("api/v1/", include("apps.search.urls_api")),
]
