"""发布后台（设计文档 §2.1 内容维护者：导入、发布、回滚）+ 指标页。

管理员可在 /admin 中：
- 触发内容导入（import 表单，同步执行并显示结果）；
- 激活/回滚任意 ready/retired release；
- 查看学习漏斗指标（§11，服务端聚合，无新增埋点）。
"""
import time
from pathlib import Path

from django.contrib import admin, messages
from django.conf import settings as dj_settings
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from .importer.errors import ImporterError
from .importer.importer import import_release, resolve_commit
from .models import (
    ContentAsset,
    ContentChunk,
    ContentDay,
    ContentDayVersion,
    ContentRelease,
    ReleaseStatus,
    SiteState,
)


@admin.register(ContentRelease)
class ContentReleaseAdmin(admin.ModelAdmin):
    list_display = ("commit", "config_version", "status", "day_count",
                    "chunk_count", "created_at", "activated_at", "release_actions")
    list_filter = ("status",)
    search_fields = ("commit",)
    readonly_fields = ("created_at", "activated_at", "checksum",
                       "day_count", "chunk_count", "error_report")
    change_list_template = "admin/content/release_list.html"

    def release_actions(self, obj):
        from django.utils.html import format_html

        if obj.status in (ReleaseStatus.READY, ReleaseStatus.RETIRED):
            return format_html(
                '<a class="button" href="{}">{}该版本</a>',
                reverse("admin:content_release_activate", args=[obj.pk]),
                "回滚到" if obj.status == ReleaseStatus.RETIRED else "激活",
            )
        return "—"

    release_actions.short_description = "操作"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name="content_release_import",
            ),
            path(
                "<int:pk>/activate/",
                self.admin_site.admin_view(self.activate_view),
                name="content_release_activate",
            ),
        ]
        return custom + urls

    def import_view(self, request):
        """触发导入（同步执行；168 天约 1 分钟，需耐心等待）。"""
        result = None
        error = None
        if request.method == "POST":
            commit_arg = request.POST.get("commit", "HEAD").strip()
            config_version = int(request.POST.get("config_version", "1") or 1)
            activate = request.POST.get("activate") == "on"
            use_working_tree = request.POST.get("use_working_tree") == "on"
            try:
                if commit_arg == "local" or use_working_tree:
                    # 工作树导入：用于开发验证；commit 仍解析为 HEAD。
                    commit = resolve_commit(Path(dj_settings.BASE_DIR), "HEAD")
                    source_root = Path(dj_settings.BASE_DIR)
                else:
                    commit = resolve_commit(Path(dj_settings.BASE_DIR), commit_arg)
                    source_root = None
                started = time.monotonic()
                release = import_release(
                    content_commit=commit,
                    config_version=config_version,
                    source_root=source_root,
                    repo_root=Path(dj_settings.BASE_DIR),
                    expected_days=int(request.POST.get("expected_days", "168")),
                    activate=activate,
                    logger=lambda msg: None,
                )
                result = {
                    "commit": release.commit,
                    "status": release.status,
                    "day_count": release.day_count,
                    "chunk_count": release.chunk_count,
                    "seconds": round(time.monotonic() - started, 1),
                }
                messages.success(
                    request,
                    f"导入完成：{release.day_count} 天，状态 {release.status}。",
                )
            except ImporterError as exc:
                error = exc.format()
                messages.error(request, f"导入失败：{error}")
            except ValueError:
                error = "config_version 必须是整数"
        context = dict(
            self.admin_site.each_context(request),
            title="导入内容版本",
            result=result,
            error=error,
        )
        return render(request, "admin/content/import_form.html", context)

    def activate_view(self, request, pk):
        """激活/回滚：只有 ready/retired 可激活（active 不可变）。"""
        release = self.get_object(request, pk)
        if release is None or release.status not in (
            ReleaseStatus.READY, ReleaseStatus.RETIRED
        ):
            messages.error(request, "仅 ready/retired 版本可激活。")
            return HttpResponseRedirect("../")
        if request.method == "POST":
            with transaction.atomic():
                release.activate()
            messages.success(
                request, f"已激活 release {release.commit[:12]}（回滚完成）。"
            )
            return HttpResponseRedirect("../")
        context = dict(
            self.admin_site.each_context(request),
            title="确认激活",
            release=release,
        )
        return render(request, "admin/content/activate_confirm.html", context)


@admin.register(ContentDay)
class ContentDayAdmin(admin.ModelAdmin):
    list_display = ("day_id", "day", "week", "phase", "current_version")
    search_fields = ("day_id",)


@admin.register(ContentDayVersion)
class ContentDayVersionAdmin(admin.ModelAdmin):
    list_display = ("day_id", "release", "content_sha")
    search_fields = ("day_id",)


@admin.register(ContentChunk)
class ContentChunkAdmin(admin.ModelAdmin):
    list_display = ("chunk_id", "day_id", "heading")
    search_fields = ("day_id",)


@admin.register(ContentAsset)
class ContentAssetAdmin(admin.ModelAdmin):
    list_display = ("kind", "day_id", "storage_key", "size", "visibility")
    search_fields = ("day_id", "storage_key")


@admin.register(SiteState)
class SiteStateAdmin(admin.ModelAdmin):
    list_display = ("id", "active_release", "updated_at")
