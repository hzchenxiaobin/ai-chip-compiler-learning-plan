from django.contrib import admin
from django.urls import path
from django.shortcuts import render

from .metrics import compute_metrics
from .models import (
    AuditEvent,
    DayProgress,
    LearningDataJob,
    LearningImportConflict,
    LearningPlan,
    TaskProgress,
)


@admin.register(LearningPlan)
class LearningPlanAdmin(admin.ModelAdmin):
    list_display = ("user", "current_day_id", "revision", "updated_at")


@admin.register(DayProgress)
class DayProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "day_id", "revision", "needs_review", "last_visited_at")
    list_filter = ("needs_review",)
    search_fields = ("day_id", "user__username")


@admin.register(TaskProgress)
class TaskProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "day_id", "task_id", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("day_id", "user__username")


@admin.register(LearningDataJob)
class LearningDataJobAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "status", "created_at", "expires_at")
    list_filter = ("kind", "status")


@admin.register(LearningImportConflict)
class LearningImportConflictAdmin(admin.ModelAdmin):
    list_display = ("job", "day_id", "resolution")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "metrics/",
                self.admin_site.admin_view(self.metrics_view),
                name="learning_metrics",
            ),
        ]
        return custom + urls

    def metrics_view(self, request):
        context = dict(
            self.admin_site.each_context(request),
            title="学习指标（服务端聚合）",
            metrics=compute_metrics(),
        )
        return render(request, "admin/learning/metrics.html", context)



    list_display = ("action", "actor", "object_type", "object_id", "created_at")
    list_filter = ("action",)
    search_fields = ("object_id",)
    readonly_fields = ("actor", "action", "object_type", "object_id",
                       "created_at", "safe_metadata")
