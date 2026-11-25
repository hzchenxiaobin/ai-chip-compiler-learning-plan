"""学习状态机与视图模型（设计文档 §5.3—§5.4）。

整体状态派生优先级：
1. 任一适用任务 blocked → blocked；
2. 全部适用任务 done → completed；
3. 除验收外均 done 且验收未完成 → ready_for_review；
4. 已有活动（in_progress/done）→ in_progress；
5. 否则 not_started。

继续学习：LearningPlan 优先；无计划时取最近更新且未完成的日课；
从未访问返回 day-001；全部完成返回最终验收日。
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import DayProgress, LearningPlan, TaskProgress, TaskStatus, AuditEvent

TASK_STATUSES = set(TaskStatus.values)

DAY_STATES = (
    "not_started", "in_progress", "ready_for_review", "completed", "blocked",
)

_TOTAL_DAYS = 168


class PreconditionFailed(Exception):
    """If-Match 校验失败；携带当前服务端记录供 412 响应。"""

    def __init__(self, current: dict | None, message="版本不匹配"):
        self.current = current
        self.message = message
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


# ---------------------------------------------------------------------------
# 状态机（纯函数）
# ---------------------------------------------------------------------------

def derive_day_state(required_tasks: list[str], tasks: dict[str, str]) -> str:
    statuses = [tasks.get(task_id, TaskStatus.NOT_STARTED) for task_id in required_tasks]
    if any(status == TaskStatus.BLOCKED for status in statuses):
        return "blocked"
    if all(status == TaskStatus.DONE for status in statuses):
        return "completed"
    acceptance = "acceptance" in required_tasks
    non_acceptance = [s for t, s in zip(required_tasks, statuses) if t != "acceptance"]
    if (
        acceptance
        and all(s == TaskStatus.DONE for s in non_acceptance)
        and tasks.get("acceptance", TaskStatus.NOT_STARTED) in (TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS)
    ):
        return "ready_for_review"
    if any(status in (TaskStatus.IN_PROGRESS, TaskStatus.DONE) for status in statuses):
        return "in_progress"
    return "not_started"


def _default_tasks(required_tasks: list[str]) -> dict[str, dict]:
    tasks = {}
    for task_id in ("reading", "exercise", "experiment", "acceptance"):
        if task_id in required_tasks:
            tasks[task_id] = {"status": TaskStatus.NOT_STARTED, "updated_at": None}
        else:
            tasks[task_id] = {"status": TaskStatus.NOT_APPLICABLE, "updated_at": None}
    return tasks


# ---------------------------------------------------------------------------
# 视图模型（读路径）
# ---------------------------------------------------------------------------

def get_tasks_map(user, day_ids: list[str]) -> dict[str, dict[str, dict]]:
    rows = TaskProgress.objects.filter(user=user, day_id__in=day_ids)
    result = {day_id: {} for day_id in day_ids}
    for row in rows:
        result.setdefault(row.day_id, {})[row.task_id] = {
            "status": row.status, "updated_at": row.updated_at,
        }
    return result


def get_day_view_model(user, release, meta: dict) -> dict:
    day_id = meta["day_id"]
    progress = DayProgress.objects.filter(user=user, day_id=day_id).first()
    tasks_map = get_tasks_map(user, [day_id])[day_id]
    tasks = _default_tasks(meta["required_tasks"])
    for task_id, entry in tasks.items():
        if task_id in tasks_map:
            tasks[task_id] = tasks_map[task_id]
    plan = LearningPlan.objects.filter(user=user).first()
    return {
        "day_id": day_id,
        "tasks": tasks,
        "overall": derive_day_state(meta["required_tasks"],
                                    {k: v["status"] for k, v in tasks.items()
                                     if k in meta["required_tasks"]}),
        "planned": bool(plan and plan.current_day_id == day_id),
        "needs_review": bool(progress and progress.needs_review),
        "ack_content_sha": progress.ack_content_sha if progress else "",
        "revision": progress.revision if progress else 0,
        "has_progress": progress is not None,
        "last_visited_at": progress.last_visited_at if progress else None,
        "content_sha": meta["content_sha"],
    }


def summarize_days(user, metas: list[dict]) -> dict:
    day_ids = [meta["day_id"] for meta in metas]
    tasks_map = get_tasks_map(user, day_ids)
    progress_rows = {
        row.day_id: row for row in DayProgress.objects.filter(user=user, day_id__in=day_ids)
    }
    plan = LearningPlan.objects.filter(user=user).first()
    summary = {
        "days": {}, "counts": {
            "not_started": 0, "in_progress": 0, "ready_for_review": 0,
            "completed": 0, "blocked": 0, "needs_review": 0, "visited": 0,
        }, "planned_day_id": plan.current_day_id if plan else None,
    }
    for meta in metas:
        day_id = meta["day_id"]
        tasks = _default_tasks(meta["required_tasks"])
        for task_id, entry in tasks.items():
            if task_id in tasks_map.get(day_id, {}):
                tasks[task_id] = tasks_map[day_id][task_id]
        overall = derive_day_state(
            meta["required_tasks"],
            {k: v["status"] for k, v in tasks.items() if k in meta["required_tasks"]},
        )
        progress = progress_rows.get(day_id)
        summary["days"][day_id] = {
            "overall": overall,
            "tasks": tasks,
            "planned": plan is not None and plan.current_day_id == day_id,
            "needs_review": bool(progress and progress.needs_review),
            "visited": progress is not None,
            "last_task_update": max(
                (entry["updated_at"] for entry in tasks.values()
                 if entry["updated_at"]), default=None,
            ),
        }
        if progress is not None:
            summary["counts"]["visited"] += 1
            if progress.needs_review:
                summary["counts"]["needs_review"] += 1
        summary["counts"][overall] += 1
    return summary


def get_week_view_model(user, days_meta: list[dict]) -> dict:
    """周状态：关键产出（key_output）、Day 6 集成与 Day 7 复盘派生。"""
    summary = summarize_days(user, days_meta)
    key_items = [m for m in days_meta if m.get("key_output") or m["day"] % 7 in (0,)]
    day6 = next((m for m in days_meta if m["day"] % 7 == 6), None)
    day7 = next((m for m in days_meta if m["day"] % 7 == 0), None)

    def state_of(meta):
        entry = summary["days"].get(meta["day_id"])
        return entry["overall"] if entry else "not_started"

    states = [state_of(m) for m in key_items]
    day6_state = state_of(day6) if day6 else "not_started"
    day7_state = state_of(day7) if day7 else "not_started"
    if "blocked" in states or day6_state == "blocked" or day7_state == "blocked":
        week_state = "blocked"
    elif all(s == "completed" for s in states) and day6_state == "completed" and day7_state == "completed":
        week_state = "completed"
    elif day6_state == "completed" and day7_state != "completed":
        week_state = "ready_for_review"
    elif any(s in ("in_progress", "completed", "ready_for_review") for s in states + [day6_state, day7_state]):
        week_state = "in_progress"
    else:
        week_state = "not_started"

    return {
        "summary": summary,
        "week_state": week_state,
        "day6_state": day6_state,
        "day7_state": day7_state,
        "key_items": [
            {"day_id": m["day_id"], "day": m["day"], "title": m["title"], "state": state_of(m)}
            for m in key_items
        ],
    }


def get_phase_view_model(user, days_meta: list[dict]) -> dict:
    week_views = []
    for week in sorted({m["week"] for m in days_meta}):
        week_days = [m for m in days_meta if m["week"] == week]
        week_views.append({
            "week": week,
            "view": get_week_view_model(user, week_days),
        })
    day28 = next((m for m in days_meta if m["day"] % 28 == 0), None)
    week_states = [w["view"]["week_state"] for w in week_views]
    day28_state = "not_started"
    if day28:
        summary = summarize_days(user, [day28])
        day28_state = summary["days"][day28["day_id"]]["overall"]
    if "blocked" in week_states or day28_state == "blocked":
        phase_state = "blocked"
    elif all(s == "completed" for s in week_states) and day28_state == "completed":
        phase_state = "completed"
    elif any(s in ("in_progress", "completed", "ready_for_review")
             for s in week_states + [day28_state]):
        phase_state = "in_progress"
    else:
        phase_state = "not_started"
    return {"weeks": week_views, "phase_state": phase_state, "day28_state": day28_state}


def get_continue_target(user, release, all_metas: list[dict]) -> dict:
    """继续学习目标（设计文档 §5.4）。"""
    meta_by_day = {m["day_id"]: m for m in all_metas}
    plan = LearningPlan.objects.filter(user=user).first()
    if plan and plan.current_day_id and plan.current_day_id in meta_by_day:
        meta = meta_by_day[plan.current_day_id]
        return {"day_id": meta["day_id"], "meta": meta, "reason": "plan"}

    summary = summarize_days(user, all_metas)
    # 最近更新且未完成的日课。
    candidates = []
    for day_id, entry in summary["days"].items():
        if entry["overall"] in ("completed",):
            continue
        if entry["last_task_update"]:
            candidates.append((entry["last_task_update"], day_id))
    if candidates:
        candidates.sort(reverse=True)
        day_id = candidates[0][1]
        # 周复盘优先（设计文档 §5.4）：最近活动所在周的 Day 7 已开始未完成时，
        # 优先返回该周复盘日，不被普通旧课浏览打断。
        week = (int(day_id.removeprefix("day-")) - 1) // 7 + 1
        day7_id = f"day-{(week - 1) * 7 + 7:03d}"
        day7_entry = summary["days"].get(day7_id)
        if day7_entry and day7_entry["visited"] and day7_entry["overall"] != "completed":
            return {"day_id": day7_id, "meta": meta_by_day[day7_id], "reason": "week_review"}
        return {"day_id": day_id, "meta": meta_by_day[day_id], "reason": "recent"}
    if summary["counts"]["visited"] == 0:
        return {"day_id": "day-001", "meta": meta_by_day["day-001"], "reason": "first"}
    # 全部完成。
    return {"day_id": "day-168", "meta": meta_by_day["day-168"], "reason": "finished"}


def get_dashboard_view(user, release, all_metas: list[dict]) -> dict:
    summary = summarize_days(user, all_metas)
    continue_target = get_continue_target(user, release, all_metas)
    recent = DayProgress.objects.filter(user=user).order_by("-last_visited_at")[:8]
    recent_metas = []
    for row in recent:
        meta = next((m for m in all_metas if m["day_id"] == row.day_id), None)
        if meta:
            entry = summary["days"].get(row.day_id, {})
            recent_metas.append({
                "day_id": row.day_id, "title": meta["title"], "url": meta["url"],
                "overall": entry.get("overall", "not_started"),
                "visited_at": row.last_visited_at,
            })
    blocked = []
    for meta in all_metas:
        entry = summary["days"].get(meta["day_id"])
        if not entry:
            continue
        for task_id, task in entry["tasks"].items():
            if task["status"] == TaskStatus.BLOCKED:
                blocked.append({
                    "day_id": meta["day_id"], "day": meta["day"],
                    "title": meta["title"], "url": meta["url"], "task_id": task_id,
                })
    needs_review = [
        {"day_id": m["day_id"], "title": m["title"], "url": m["url"]}
        for m in all_metas
        if summary["days"].get(m["day_id"], {}).get("needs_review")
    ]
    return {
        "summary": summary,
        "continue_target": continue_target,
        "recent": recent_metas[:6],
        "blocked": blocked[:20],
        "needs_review": needs_review[:20],
        "counts": summary["counts"],
    }


# ---------------------------------------------------------------------------
# 写路径
# ---------------------------------------------------------------------------

def _audit(user, action, object_type="", object_id="", metadata=None):
    AuditEvent.objects.create(
        actor=user, action=action, object_type=object_type,
        object_id=str(object_id), safe_metadata=metadata or {},
    )


def _current_sha(release, day_id: str) -> str | None:
    from apps.content.models import ContentDayVersion

    row = (
        ContentDayVersion.objects.filter(release=release, day_id=day_id)
        .values("content_sha").first()
    )
    return row["content_sha"] if row else None


def day_representation(user, release, meta: dict) -> dict:
    view = get_day_view_model(user, release, meta)
    progress = DayProgress.objects.filter(user=user, day_id=view["day_id"]).first()
    return {
        "schema_version": 1,
        "day_id": view["day_id"],
        "content_sha": view["ack_content_sha"] or "",
        "planned": view["planned"],
        "tasks": view["tasks"],
        "reading_position": round(progress.reading_position, 4) if progress else 0.0,
        "reading_seconds": progress.reading_seconds if progress else 0,
        "last_visited_at": (
            view["last_visited_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            if view["last_visited_at"] else None
        ),
        "needs_review": view["needs_review"],
        "revision": view["revision"],
        "current_content_sha": view["content_sha"],
        "overall": view["overall"],
    }


def touch_visit(user, meta: dict):
    """浏览旧课只更新最近访问；60 秒内重复访问不写库。"""
    now = timezone.now()
    progress, created = DayProgress.objects.get_or_create(
        user=user, day_id=meta["day_id"],
        defaults={
            "ack_content_sha": meta["content_sha"],
            "last_visited_at": now,
        },
    )
    if created:
        _audit(user, "day.visit.first", "day", meta["day_id"])
        return
    if progress.last_visited_at is None or now - progress.last_visited_at > timedelta(seconds=60):
        DayProgress.objects.filter(pk=progress.pk).update(last_visited_at=now)


def update_progress(user, release, meta: dict, *, tasks: dict | None,
                    acknowledge: bool = False, if_match: str | None,
                    if_none_match: str | None) -> dict:
    """PATCH 语义：任务状态更新与内容复核。失败抛 PreconditionFailed/ValidationError。"""
    now = timezone.now()
    day_id = meta["day_id"]
    current_sha = meta["content_sha"]

    if tasks is not None:
        if not isinstance(tasks, dict) or not tasks:
            raise ValidationError("BODY_INVALID", "tasks 必须为非空对象")
        for task_id, status in tasks.items():
            if task_id not in ("reading", "exercise", "experiment", "acceptance"):
                raise ValidationError("TASK_ID_INVALID", f"未知任务：{task_id!r}")
            if status not in TASK_STATUSES:
                raise ValidationError("TASK_STATUS_INVALID", f"未知状态：{status!r}")
            if status == TaskStatus.NOT_APPLICABLE:
                raise ValidationError(
                    "TASK_STATUS_FORBIDDEN",
                    "not_applicable 由日课类型派生，不允许客户端写入",
                )
            if task_id not in meta["required_tasks"]:
                raise ValidationError(
                    "TASK_NOT_APPLICABLE", f"{day_id} 不要求任务 {task_id}"
                )

    with transaction.atomic():
        progress = DayProgress.objects.select_for_update().filter(
            user=user, day_id=day_id
        ).first()
        if progress is None:
            if if_match is not None:
                raise PreconditionFailed(None, "记录不存在；新建请使用 If-None-Match: *")
            progress = DayProgress.objects.create(
                user=user, day_id=day_id, ack_content_sha=current_sha,
                revision=1,
            )
        else:
            if if_match is None and if_none_match != "*":
                raise PreconditionFailed(
                    None, "已存在记录必须提供 If-Match（当前 revision 见响应）"
                )
            if if_match is not None and str(progress.revision) != if_match:
                raise PreconditionFailed(_snapshot(user, release, meta, progress))

        if tasks:
            for task_id, status in tasks.items():
                TaskProgress.objects.update_or_create(
                    user=user, day_id=day_id, task_id=task_id,
                    defaults={"status": status},
                )
        if acknowledge:
            progress.ack_content_sha = current_sha
            progress.needs_review = False
        progress.last_visited_at = now
        progress.revision += 1
        progress.save()

    _audit(user, "progress.update", "day", day_id, {
        "tasks": sorted(tasks.keys()) if tasks else [], "acknowledge": acknowledge,
        "revision": progress.revision,
    })
    return day_representation(user, release, meta)


def _snapshot(user, release, meta, progress) -> dict:
    tasks = get_tasks_map(user, [meta["day_id"]])[meta["day_id"]]
    return {
        "day_id": meta["day_id"],
        "revision": progress.revision,
        "ack_content_sha": progress.ack_content_sha,
        "needs_review": progress.needs_review,
        "tasks": {
            task_id: tasks.get(task_id, {"status": "not_started", "updated_at": None})
            for task_id in ("reading", "exercise", "experiment", "acceptance")
        },
        "last_visited_at": (
            progress.last_visited_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            if progress.last_visited_at else None
        ),
    }


def record_reading_heartbeat(user, meta: dict, *, scroll_ratio: float,
                             elapsed_seconds: int) -> dict:
    """阅读心跳（自动进度，产品决策：含自动完成）。

    - 幂等式单向推进：不做 If-Match（仅创建/累加/推进 reading 状态）；
    - 纯位置/时长更新不增加 revision（避免与任务写入产生 412 风暴）；
    - 状态变化（not_started→in_progress→done）才增加 revision 并写审计；
    - 自动完成条件（settings.AUTO_COMPLETE_READING）：累计时长达阈值
      且本次心跳滚动比例达阈值 → reading=done（audit: reading.auto_done）。
    """
    from django.conf import settings as dj_settings

    now = timezone.now()
    day_id = meta["day_id"]

    # 输入规整：单次 elapsed 上限 60 秒（防时钟漂移灌水），比例夹取 [0,1]。
    elapsed_seconds = max(0, min(int(elapsed_seconds), 60))
    scroll_ratio = min(1.0, max(0.0, float(scroll_ratio)))

    auto_completed = False
    with transaction.atomic():
        progress = DayProgress.objects.select_for_update().filter(
            user=user, day_id=day_id
        ).first()
        if progress is None:
            progress = DayProgress.objects.create(
                user=user, day_id=day_id, ack_content_sha=meta["content_sha"],
                last_visited_at=now, revision=0,
            )
        progress.reading_position = scroll_ratio
        progress.reading_seconds = min(
            progress.reading_seconds + elapsed_seconds, 24 * 3600
        )
        if progress.last_visited_at is None or now - progress.last_visited_at > timedelta(seconds=60):
            progress.last_visited_at = now
        progress.save()

        task = TaskProgress.objects.select_for_update().filter(
            user=user, day_id=day_id, task_id="reading"
        ).first()
        if task is None:
            task = TaskProgress(user=user, day_id=day_id, task_id="reading")
        current = task.status if task.pk else TaskStatus.NOT_STARTED

        reading_applicable = "reading" in meta.get("required_tasks", ())
        new_status = current
        if reading_applicable:
            if current in (TaskStatus.NOT_STARTED, TaskStatus.NOT_APPLICABLE):
                new_status = TaskStatus.IN_PROGRESS  # 真实活动信号：自动进入进行中。
            if (current in (TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS)
                    and getattr(dj_settings, "AUTO_COMPLETE_READING", True)
                    and progress.reading_seconds >= int(
                        getattr(dj_settings, "READING_DONE_MIN_SECONDS", 180))
                    and scroll_ratio >= float(
                        getattr(dj_settings, "READING_DONE_SCROLL_RATIO", 0.95))):
                # 自动完成（产品开关控制）；blocked/done 等人工状态永不覆盖。
                new_status = TaskStatus.DONE
                auto_completed = True
        if new_status != current:
            task.status = new_status
            task.save()
            progress.revision += 1
            progress.save(update_fields=["revision"])
            _audit(user, "reading.heartbeat" if not auto_completed else
                    "reading.auto_done", "day", day_id, {
                        "status": new_status,
                        "reading_seconds": progress.reading_seconds,
                    })

    return {
        "day_id": day_id,
        "reading_position": round(progress.reading_position, 4),
        "reading_seconds": progress.reading_seconds,
        "reading_status": new_status,
        "auto_completed": auto_completed,
        "revision": progress.revision,
    }


def set_plan(user, release, day_id: str | None, if_match: str | None) -> dict:
    """PUT /api/v1/me/plan/：显式设置当前计划日；浏览不触发。"""
    if day_id is not None and release is not None:
        from apps.content.models import ContentDayVersion

        if not ContentDayVersion.objects.filter(
            release=release, day_id=day_id
        ).exists():
            raise ValidationError("DAY_NOT_FOUND", f"日课不存在：{day_id}")

    with transaction.atomic():
        plan = LearningPlan.objects.select_for_update().filter(user=user).first()
        if plan is None:
            plan = LearningPlan.objects.create(
                user=user, current_day_id=day_id, revision=1
            )
        else:
            if if_match is not None and str(plan.revision) != if_match:
                raise PreconditionFailed({
                    "current_day_id": plan.current_day_id, "revision": plan.revision,
                })
            plan.current_day_id = day_id
            plan.revision += 1
            plan.save(update_fields=["current_day_id", "revision", "updated_at"])

    _audit(user, "plan.set", "day", day_id or "")
    return {"current_day_id": plan.current_day_id, "revision": plan.revision}
