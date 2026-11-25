"""学习页面路由。"""
from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("settings/", views.settings_page, name="settings"),
    path("settings/export/", views.settings_export, name="settings_export"),
    path("settings/import/upload/", views.settings_import_upload, name="settings_import_upload"),
    path("settings/import/apply/", views.settings_import_apply, name="settings_import_apply"),
    path("settings/restore-snapshot/<int:job_id>/", views.settings_restore_snapshot,
         name="settings_restore_snapshot"),
    path("settings/delete-data/", views.settings_delete_data, name="settings_delete_data"),
    path("settings/delete-account/", views.settings_delete_account, name="settings_delete_account"),
]
