"""学习数据模型（设计文档 §8.2）。

MySQL 是学习数据唯一权威源：
- LearningPlan：每用户唯一当前计划（浏览旧课不回退计划）；
- DayProgress：(user, day_id) 唯一，保存 ack_content_sha、needs_review、revision；
- TaskProgress：四任务独立状态；
- LearningDataJob / LearningImportConflict：导出、导入预检与冲突暂存；
- AuditEvent：账号生命周期与破坏性操作审计。
整体状态只在服务层派生，不落库。
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class TaskStatus(models.TextChoices):
    NOT_STARTED = "not_started", "未开始"
    IN_PROGRESS = "in_progress", "进行中"
    DONE = "done", "已完成"
    BLOCKED = "blocked", "有卡点"
    NOT_APPLICABLE = "not_applicable", "不适用"


class LearningPlan(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_plan"
    )
    current_day_id = models.CharField(max_length=16, null=True, blank=True)
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"plan({self.user_id}): {self.current_day_id}"


class DayProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="day_progress"
    )
    day_id = models.CharField(max_length=16, db_index=True)
    ack_content_sha = models.CharField(max_length=64, blank=True, default="")
    last_visited_at = models.DateTimeField(null=True, blank=True)
    needs_review = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "day_id"], name="uniq_progress_user_day")
        ]
        indexes = [models.Index(fields=["user", "last_visited_at"])]


class TaskProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_progress"
    )
    day_id = models.CharField(max_length=16, db_index=True)
    task_id = models.CharField(max_length=16)
    status = models.CharField(
        max_length=16, choices=TaskStatus.choices, default=TaskStatus.NOT_STARTED
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "day_id", "task_id"], name="uniq_task_user_day_task"
            )
        ]
        indexes = [models.Index(fields=["user", "day_id"])]


class DataJobKind(models.TextChoices):
    EXPORT = "export", "导出"
    IMPORT = "import", "导入"
    SNAPSHOT = "snapshot", "替换前快照"
    DELETE_DATA = "delete_data", "删除学习数据"
    DELETE_ACCOUNT = "delete_account", "删除账号"


class DataJobStatus(models.TextChoices):
    UPLOADED = "uploaded", "已上传待预检"
    PRECHECK_OK = "precheck_ok", "预检通过待确认"
    PRECHECK_FAILED = "precheck_failed", "预检失败"
    APPLIED = "applied", "已应用"
    FAILED = "failed", "失败"
    EXPIRED = "expired", "已过期"


class LearningDataJob(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="data_jobs"
    )
    kind = models.CharField(max_length=16, choices=DataJobKind.choices)
    status = models.CharField(
        max_length=16, choices=DataJobStatus.choices, default=DataJobStatus.UPLOADED
    )
    private_file = models.CharField(max_length=255, blank=True)
    report_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "kind", "status"])]

    def __str__(self):
        return f"job({self.user_id},{self.kind},{self.status})"


class LearningImportConflict(models.Model):
    job = models.ForeignKey(
        LearningDataJob, on_delete=models.CASCADE, related_name="conflicts"
    )
    day_id = models.CharField(max_length=16)
    local_payload = models.JSONField()
    incoming_payload = models.JSONField()
    resolution = models.CharField(
        max_length=16,
        choices=[("pending", "待选择"), ("local", "保留本机"), ("incoming", "使用导入")],
        default="pending",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "day_id"], name="uniq_conflict_job_day")
        ]


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=32, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    safe_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
