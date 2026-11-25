"""搜索索引模型（设计文档 §7.5）。

search_token：规范化 token；search_posting：关联 chunk、字段、权重和位置。
中文以二元词召回；英文命令、错误码、路径和 IR token 保留完整形式。
"""
from django.db import models


class SearchToken(models.Model):
    token = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.token


class SearchField(models.TextChoices):
    TITLE = "title", "标题"
    SKILL = "skill", "技能"
    OBJECTIVE = "objective", "目标"
    DELIVERABLE = "deliverable", "产出"
    HEADING = "heading", "章节"
    CODE_PATH = "code_path", "代码路径"
    BODY = "body", "正文"


FIELD_WEIGHTS = {
    SearchField.TITLE: 12,
    SearchField.SKILL: 8,
    SearchField.OBJECTIVE: 5,
    SearchField.DELIVERABLE: 5,
    SearchField.HEADING: 4,
    SearchField.CODE_PATH: 3,
    SearchField.BODY: 1,
}

EXACT_BONUS = 10


class SearchPosting(models.Model):
    version = models.ForeignKey(
        "content.ContentDayVersion", on_delete=models.CASCADE, related_name="postings"
    )
    day_id = models.CharField(max_length=16, db_index=True)
    chunk_id = models.CharField(max_length=32)
    field = models.CharField(max_length=16, choices=SearchField.choices)
    token = models.ForeignKey(
        SearchToken, on_delete=models.CASCADE, related_name="postings"
    )
    weight = models.PositiveSmallIntegerField()
    position = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["token", "field"]),
            models.Index(fields=["version", "day_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "chunk_id", "field", "token"],
                name="uniq_posting_version_chunk_field_token",
            )
        ]
