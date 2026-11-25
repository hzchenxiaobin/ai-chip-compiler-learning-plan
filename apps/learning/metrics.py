"""学习指标聚合（设计文档 §11）。

只做服务端聚合（不新增埋点）；指标回答漏斗问题而非停留时长：
有效开始 → 第 1 周闭环 → Day 029 环境通过 → 阶段推进。
"""
from django.db.models import Count

from apps.content.models import ContentDayVersion, SiteState

from .models import DataJobKind, DayProgress, LearningDataJob, TaskProgress, TaskStatus


def _users_with_tasks_done(day_id: str) -> int:
    required = _required_tasks(day_id)
    if not required:
        return 0
    rows = (
        TaskProgress.objects.filter(day_id=day_id, status=TaskStatus.DONE)
        .values("user_id")
        .annotate(done=Count("task_id"))
    )
    return sum(1 for row in rows if row["done"] >= len(required))


def _required_tasks(day_id: str) -> list[str]:
    release = SiteState.get_active_release()
    if release is None:
        return []
    version = (
        ContentDayVersion.objects.filter(release=release, day_id=day_id)
        .values("metadata_json")
        .first()
    )
    if not version:
        return []
    return version["metadata_json"].get("required_tasks", [])


def _users_visited(day_id: str) -> int:
    return DayProgress.objects.filter(day_id=day_id).count()


def compute_metrics() -> dict:
    """聚合漏斗指标（供管理后台展示）。"""
    release = SiteState.get_active_release()
    total_users = (
        DayProgress.objects.values("user_id").distinct().count()
    )
    day001_started = (
        TaskProgress.objects.filter(
            day_id="day-001",
            status__in=(TaskStatus.IN_PROGRESS, TaskStatus.DONE, TaskStatus.BLOCKED),
        )
        .values("user_id").distinct().count()
    )
    metrics = {
        "release": {
            "commit": release.commit[:12] if release else None,
            "day_count": release.day_count if release else 0,
        },
        "users": {
            "with_progress": total_users,
            "day001_started": day001_started,
            "day001_visited": _users_visited("day-001"),
        },
        "week1": {
            "closed": _users_with_tasks_done("day-007"),
            "visited": _users_visited("day-007"),
        },
        "day029": {
            "completed": _users_with_tasks_done("day-029"),
            "visited": _users_visited("day-029"),
        },
        "blocked_tasks": TaskProgress.objects.filter(
            status=TaskStatus.BLOCKED
        ).count(),
        "needs_review_days": DayProgress.objects.filter(
            needs_review=True
        ).values("user_id", "day_id").distinct().count(),
        "jobs": {
            kind: LearningDataJob.objects.filter(kind=kind).count()
            for kind in DataJobKind.values
        },
    }
    # 第 1 周闭环率 / Day 029 通过率（避免除零）。
    base = metrics["users"]["day001_started"] or 1
    metrics["rates"] = {
        "week1_closed_of_started": round(
            metrics["week1"]["closed"] / base * 100, 1
        ),
        "day029_completed_of_started": round(
            metrics["day029"]["completed"] / base * 100, 1
        ),
    }
    return metrics
