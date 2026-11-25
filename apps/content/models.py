"""内容读模型（设计文档 §7.2）。

Git 是唯一权威源；本模块只保存可由同一 commit 完整重建的读模型：
ContentRelease → ContentDayVersion（元数据 + 白名单 HTML + content_sha）
              → ContentChunk（搜索分片） / ContentAsset（源码 ZIP、图片）。

发布状态机：validating → ready → active；失败 failed；停用 retired。
只有 ready 可激活；激活在单行 SiteState 事务中切换。
"""
from django.db import models
from django.utils import timezone


class ReleaseStatus(models.TextChoices):
    VALIDATING = "validating", "校验中"
    READY = "ready", "待激活"
    ACTIVE = "active", "当前发布"
    FAILED = "failed", "失败"
    RETIRED = "retired", "已停用"


class ContentRelease(models.Model):
    commit = models.CharField(max_length=40, db_index=True)
    config_version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16, choices=ReleaseStatus.choices, default=ReleaseStatus.VALIDATING
    )
    checksum = models.CharField(max_length=64, blank=True)
    day_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    error_report = models.JSONField(null=True, blank=True)
    plan_markdown = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["commit", "config_version"], name="uniq_release_commit_config"
            )
        ]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"release {self.commit[:12]}@{self.config_version} {self.status}"

    def activate(self):
        """在事务中切换 SiteState（由调用方包 transaction.atomic）。"""
        previous = SiteState.get_solo()
        old_release = previous.active_release
        self.status = ReleaseStatus.ACTIVE
        self.activated_at = timezone.now()
        self.save(update_fields=["status", "activated_at"])
        if old_release and old_release.pk != self.pk:
            ContentRelease.objects.filter(pk=old_release.pk).exclude(
                status=ReleaseStatus.RETIRED
            ).update(status=ReleaseStatus.RETIRED)
        previous.active_release = self
        previous.updated_at = timezone.now()
        previous.save(update_fields=["active_release", "updated_at"])


class ContentDay(models.Model):
    """日课稳定实体：day_id/day 唯一，指向当前版本。"""

    day_id = models.CharField(max_length=16, unique=True)
    day = models.PositiveSmallIntegerField(unique=True)
    week = models.PositiveSmallIntegerField()
    phase = models.PositiveSmallIntegerField()
    current_version = models.ForeignKey(
        "content.ContentDayVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_for",
    )

    class Meta:
        ordering = ["day"]

    def __str__(self):
        return self.day_id


class ContentDayVersion(models.Model):
    release = models.ForeignKey(
        ContentRelease, on_delete=models.CASCADE, related_name="day_versions"
    )
    day_ref = models.ForeignKey(
        ContentDay, on_delete=models.PROTECT, related_name="versions"
    )
    day_id = models.CharField(max_length=16, db_index=True)
    metadata_json = models.JSONField()
    rendered_html = models.TextField()
    content_sha = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["release", "day_id"], name="uniq_version_release_day"
            )
        ]
        indexes = [models.Index(fields=["day_id"])]

    @property
    def meta(self) -> dict:
        return self.metadata_json

    def __str__(self):
        return f"{self.day_id}@{self.release.commit[:12]}"


class ContentChunk(models.Model):
    """正文分片：heading/anchor/text + token_data（供检索与摘要）。"""

    version = models.ForeignKey(
        ContentDayVersion, on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_id = models.CharField(max_length=32)
    day_id = models.CharField(max_length=16, db_index=True)
    heading = models.CharField(max_length=200, blank=True)
    anchor = models.CharField(max_length=200, blank=True)
    text = models.TextField()
    token_data = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "chunk_id"], name="uniq_chunk_version_id"
            )
        ]
        indexes = [models.Index(fields=["day_id"])]


class AssetKind(models.TextChoices):
    SOURCE_ZIP = "source_zip", "源码包"
    IMAGE = "image", "图片"


class AssetVisibility(models.TextChoices):
    PUBLIC = "public", "公开"
    PRIVATE = "private", "私有"


class ContentAsset(models.Model):
    version = models.ForeignKey(
        ContentDayVersion, on_delete=models.CASCADE, related_name="assets"
    )
    kind = models.CharField(max_length=16, choices=AssetKind.choices)
    day_id = models.CharField(max_length=16, db_index=True)
    storage_key = models.CharField(max_length=255, unique=True)
    sha256 = models.CharField(max_length=64)
    size = models.BigIntegerField()
    visibility = models.CharField(
        max_length=8, choices=AssetVisibility.choices, default=AssetVisibility.PUBLIC
    )

    def __str__(self):
        return self.storage_key


class SiteState(models.Model):
    """全站单行：当前激活的内容版本。"""

    active_release = models.ForeignKey(
        ContentRelease,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="active_state",
    )
    updated_at = models.DateTimeField(auto_now=True)

    CACHE_KEY = "site_state_solo"
    PAGE_EPOCH_KEY = "site:page:epoch"

    @classmethod
    def get_solo(cls) -> "SiteState":
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    @classmethod
    def page_epoch(cls) -> int:
        """页面缓存世代（保存在 Redis；激活内容时递增）。

        世代与 active_release 解耦：MySQL 不可用时，匿名页面仍可按世代命中
        Redis 缓存继续可读（设计文档 §9.4）。Redis 异常返回 -1（退化为直查）。
        """
        from django.core.cache import cache

        try:
            value = cache.get(cls.PAGE_EPOCH_KEY)
            if value is None:
                obj = cls.get_solo()
                value = (obj.active_release_id or 0) or 1
                cache.set(cls.PAGE_EPOCH_KEY, value, None)
            return int(value)
        except Exception:
            return -1

    @classmethod
    def get_active_release(cls):
        """带 60s 缓存的当前发布版本查询（公开页面高频调用）。"""
        from django.core.cache import cache

        release_id = cache.get(cls.CACHE_KEY)
        if release_id is None:
            obj = cls.get_solo()
            release_id = obj.active_release_id or 0
            cache.set(cls.CACHE_KEY, release_id, 60)
        if release_id == 0:
            return None
        return ContentRelease.objects.filter(
            pk=release_id, status=ReleaseStatus.ACTIVE
        ).first()

    @classmethod
    def invalidate_cache(cls):
        from django.core.cache import cache

        cache.delete(cls.CACHE_KEY)
        cls.bump_page_epoch()

    @classmethod
    def bump_page_epoch(cls):
        """激活内容后递增页面缓存世代，旧缓存自然失效。"""
        from django.core.cache import cache

        try:
            try:
                cache.incr(cls.PAGE_EPOCH_KEY)
            except ValueError:
                cache.set(cls.PAGE_EPOCH_KEY, 1, None)
        except Exception:
            pass  # Redis 不可用：缓存本就不可用，直查路径不受影响。

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invalidate_cache()
