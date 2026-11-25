"""内容页面路由。"""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("plan/", views.plan_page, name="plan"),
    path("weeks/week-<int:week>/", views.week_page, name="week"),
    path("phases/phase-<int:phase>/", views.phase_page, name="phase"),
    path("tutorials/week-<int:week>/<str:day_id>/", views.day_page, name="day"),
    path("assets/public/<path:key>", views.public_asset, name="public_asset"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("healthz", views.healthz, name="healthz"),
]
