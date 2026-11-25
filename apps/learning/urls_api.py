"""学习 JSON API 路由（/api/v1/）。"""
from django.urls import path

from . import api

urlpatterns = [
    path("me/dashboard/", api.me_dashboard, name="api_dashboard"),
    path("me/progress/<str:day_id>/", api.me_progress, name="api_progress"),
    path("me/progress/<str:day_id>/update/", api.me_progress_update, name="api_progress_update"),
    path("me/progress/<str:day_id>/heartbeat/", api.me_progress_heartbeat,
         name="api_progress_heartbeat"),
    path("me/plan/", api.me_plan, name="api_plan"),
    path("me/exports/", api.me_exports, name="api_exports"),
    path("me/exports/<int:job_id>/download/", api.me_export_download, name="api_export_download"),
    path("me/imports/", api.me_imports, name="api_imports"),
    path("me/imports/<int:job_id>/", api.me_import_detail, name="api_import_detail"),
    path("me/imports/<int:job_id>/apply/", api.me_import_apply, name="api_import_apply"),
    path("me/data/", api.me_data_delete, name="api_data_delete"),
    path("me/account/", api.me_account_delete, name="api_account_delete"),
]
