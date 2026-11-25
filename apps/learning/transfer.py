"""导出 / 导入 / 替换 / 删除（设计文档 §8.4、§4.5）。

导出：版本化 JSON（schema_version/kind/exported_at/content_commit/plan/days），
不含 Django/MySQL 内部主键、会话或密钥。

导入：先上传到私有临时区完整预检（严格 UTF-8、重复键检测、字段白名单、
数组与字符串长度限制），用户确认合并/替换后单用户事务应用；
合并按 day_id＋完整内容比较，内容不同（无论 revision）列为冲突等待选择；
替换先生成可恢复快照。任何失败不改变原数据。
"""
import hashlib
import hmac
import json
import re
import time
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    DataJobKind,
    DataJobStatus,
    DayProgress,
    LearningDataJob,
    LearningImportConflict,
    LearningPlan,
    TaskProgress,
    TaskStatus,
)
from .services import _audit, get_tasks_map

EXPORT_KIND = "ai-chip-compiler-learning-progress"
MAX_FILE_BYTES = settings.IMPORT_MAX_FILE_BYTES
MAX_DAY_RECORDS = settings.IMPORT_MAX_DAY_RECORDS

_DAY_ID_RE = re.compile(r"^day-\d{3}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def iso_z(dt) -> str:
    """统一 RFC 3339 UTC、秒级（导出/导入往返一致）。"""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TransferError(Exception):
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

def build_export_payload(user, release) -> dict:
    day_ids = list(
        DayProgress.objects.filter(user=user).values_list("day_id", flat=True)
    )
    tasks_map = get_tasks_map(user, day_ids)
    progress_rows = {
        row["day_id"]: row for row in DayProgress.objects.filter(
            user=user, day_id__in=day_ids
        ).values("day_id", "ack_content_sha", "needs_review", "revision", "last_visited_at")
    }
    plan = LearningPlan.objects.filter(user=user).first()
    days = []
    for day_id in sorted(day_ids):
        row = progress_rows[day_id]
        tasks = tasks_map.get(day_id, {})
        days.append({
            "day_id": day_id,
            "content_sha": row["ack_content_sha"],
            "tasks": {
                task_id: {
                    "status": tasks.get(task_id, {}).get("status", "not_started"),
                    "updated_at": (
                        iso_z(tasks[task_id]["updated_at"])
                        if task_id in tasks and tasks[task_id].get("updated_at") else None
                    ),
                }
                for task_id in ("reading", "exercise", "experiment", "acceptance")
            },
            "last_visited_at": (
                iso_z(row["last_visited_at"]) if row["last_visited_at"] else None
            ),
            "needs_review": row["needs_review"],
            "revision": row["revision"],
        })
    return {
        "schema_version": 1,
        "kind": EXPORT_KIND,
        "exported_at": iso_z(timezone.now()),
        "content_commit": release.commit if release else None,
        "plan": {
            "current_day_id": plan.current_day_id if plan else None,
            "revision": plan.revision if plan else 0,
        },
        "days": days,
    }


def create_export_job(user, release) -> LearningDataJob:
    payload = build_export_payload(user, release)
    job = LearningDataJob.objects.create(
        user=user, kind=DataJobKind.EXPORT, status=DataJobStatus.APPLIED,
        report_json={"day_count": len(payload["days"])},
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    private_dir = Path(settings.PRIVATE_ASSET_ROOT) / "exports"
    private_dir.mkdir(parents=True, exist_ok=True)
    path = private_dir / f"export-{job.pk}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    job.private_file = f"exports/export-{job.pk}.json"
    job.save(update_fields=["private_file"])
    _audit(user, "data.export", "job", job.pk, {"days": len(payload["days"])})
    return job


# ---------------------------------------------------------------------------
# 签名下载 URL
# ---------------------------------------------------------------------------

def _signing_key() -> bytes:
    return str(getattr(settings, "PRIVATE_SIGNING_KEY", "dev-signing-key")).encode("utf-8")


def make_download_token(job_id: int, ttl: int | None = None) -> str:
    ttl = ttl or settings.SIGNED_URL_TTL
    expires = int(time.time()) + ttl
    digest = hmac.new(
        _signing_key(), f"{job_id}:{expires}".encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{expires}:{digest}"


def verify_download_token(job_id: int, token: str) -> bool:
    try:
        expires_raw, digest = token.split(":", 1)
        expires = int(expires_raw)
    except (ValueError, AttributeError):
        return False
    if expires < int(time.time()):
        return False
    expected = hmac.new(
        _signing_key(), f"{job_id}:{expires}".encode("ascii"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, digest)


# ---------------------------------------------------------------------------
# 导入预检
# ---------------------------------------------------------------------------

def _no_duplicate_keys(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise TransferError("JSON_DUPLICATE_KEY", f"JSON 重复键：{key!r}")
        seen.add(key)
    return dict(pairs)


def parse_import_bytes(raw: bytes) -> dict:
    if len(raw) > MAX_FILE_BYTES:
        raise TransferError(
            "FILE_TOO_LARGE", f"文件超过 {MAX_FILE_BYTES} 字节上限"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise TransferError("ENCODING_INVALID", "文件不是合法 UTF-8") from None
    if text.startswith("﻿"):
        raise TransferError("BOM_INVALID", "文件不应包含 BOM")
    try:
        payload = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise TransferError(
            "JSON_INVALID", f"JSON 解析失败：{exc.msg}（行 {exc.lineno}）"
        ) from None
    if not isinstance(payload, dict):
        raise TransferError("JSON_INVALID", "顶层必须是对象")
    return payload


def _validate_day_record(record, index) -> dict:
    if not isinstance(record, dict):
        raise TransferError("RECORD_INVALID", f"days[{index}] 必须为对象")
    allowed = {
        "day_id", "content_sha", "tasks", "last_visited_at",
        "needs_review", "revision", "planned", "schema_version",
        "latest_evidence_id", "stuck_item_ids",
    }
    unknown = sorted(set(record) - allowed)
    if unknown:
        raise TransferError(
            "FIELD_UNKNOWN", f"days[{index}] 含未知字段：{unknown}", {"unknown": unknown}
        )
    day_id = record.get("day_id")
    if not isinstance(day_id, str) or not _DAY_ID_RE.match(day_id):
        raise TransferError("DAY_ID_INVALID", f"days[{index}].day_id 格式无效")
    tasks = record.get("tasks")
    if not isinstance(tasks, dict):
        raise TransferError("TASKS_INVALID", f"{day_id} tasks 必须为对象")
    clean_tasks = {}
    for task_id in ("reading", "exercise", "experiment", "acceptance"):
        entry = tasks.get(task_id)
        if entry is None:
            entry = {"status": "not_started", "updated_at": None}
        if isinstance(entry, str):  # 宽松历史格式。
            entry = {"status": entry, "updated_at": None}
        if not isinstance(entry, dict):
            raise TransferError("TASKS_INVALID", f"{day_id}.{task_id} 必须为对象")
        status = entry.get("status", "not_started")
        if status not in set(TaskStatus.values):
            raise TransferError(
                "TASK_STATUS_INVALID", f"{day_id}.{task_id} 状态非法：{status!r}"
            )
        updated_at = entry.get("updated_at")
        if updated_at is not None and (
            not isinstance(updated_at, str) or not _TIMESTAMP_RE.match(updated_at)
        ):
            raise TransferError(
                "TIMESTAMP_INVALID", f"{day_id}.{task_id} updated_at 格式无效"
            )
        clean_tasks[task_id] = {"status": status, "updated_at": updated_at}
    sha = record.get("content_sha", "")
    if sha is not None and (not isinstance(sha, str) or (sha and not _SHA_RE.match(sha))):
        raise TransferError("SHA_INVALID", f"{day_id} content_sha 格式无效")
    revision = record.get("revision", 0)
    if (
        not isinstance(revision, int) or isinstance(revision, bool)
        or not 0 <= revision <= 2147483647
    ):
        raise TransferError("REVISION_INVALID", f"{day_id} revision 超出范围")
    needs_review = record.get("needs_review", False)
    if not isinstance(needs_review, bool):
        raise TransferError("FIELD_INVALID", f"{day_id} needs_review 必须为布尔")
    return {
        "day_id": day_id,
        "content_sha": sha or "",
        "tasks": clean_tasks,
        "last_visited_at": record.get("last_visited_at"),
        "needs_review": needs_review,
        "revision": revision,
    }


def precheck(user, release, payload: dict):
    """完整预检（不写业务表）。返回 (report, incoming_records, plan_current_day_id)。"""
    if payload.get("schema_version") != 1:
        raise TransferError(
            "VERSION_UNSUPPORTED",
            f"schema_version 必须为 1，收到 {payload.get('schema_version')!r}",
        )
    if payload.get("kind") != EXPORT_KIND:
        raise TransferError("KIND_INVALID", f"kind 必须为 {EXPORT_KIND!r}")
    exported_at = payload.get("exported_at")
    if not isinstance(exported_at, str) or not _TIMESTAMP_RE.match(exported_at):
        raise TransferError("TIMESTAMP_INVALID", "exported_at 格式无效")
    days = payload.get("days")
    if not isinstance(days, list):
        raise TransferError("DAYS_INVALID", "days 必须为数组")
    if len(days) > MAX_DAY_RECORDS:
        raise TransferError("TOO_MANY_RECORDS", f"days 超过 {MAX_DAY_RECORDS} 条上限")
    plan = payload.get("plan")
    plan_current = None
    if plan is not None:
        if not isinstance(plan, dict):
            raise TransferError("PLAN_INVALID", "plan 必须为对象")
        plan_current = plan.get("current_day_id")
        if plan_current is not None and (
            not isinstance(plan_current, str) or not _DAY_ID_RE.match(plan_current)
        ):
            raise TransferError("PLAN_INVALID", "plan.current_day_id 格式无效")

    seen = set()
    incoming = []
    for index, record in enumerate(days):
        clean = _validate_day_record(record, index)
        if clean["day_id"] in seen:
            raise TransferError("DAY_DUPLICATE", f"days 中重复出现 {clean['day_id']}")
        seen.add(clean["day_id"])
        incoming.append(clean)

    known = set()
    if release is not None:
        from apps.content.models import ContentDayVersion

        known = set(
            ContentDayVersion.objects.filter(release=release)
            .values_list("day_id", flat=True)
        )

    local_rows = {
        row["day_id"]: row for row in DayProgress.objects.filter(user=user)
        .values("day_id", "ack_content_sha", "needs_review", "revision")
    }
    local_tasks = get_tasks_map(user, list(local_rows))

    report = {
        "counts": {"add": 0, "unchanged": 0, "conflict": 0, "skip": 0},
        "skipped_unknown": [],
        "conflicts": [],
        "plan": {"current_day_id": plan_current},
    }
    for record in incoming:
        day_id = record["day_id"]
        if day_id not in known:
            report["counts"]["skip"] += 1
            report["skipped_unknown"].append(day_id)
            continue
        local = local_rows.get(day_id)
        if local is None:
            report["counts"]["add"] += 1
            continue
        local_content = {
            "tasks": {
                task_id: local_tasks.get(day_id, {}).get(task_id, {}).get(
                    "status", "not_started"
                )
                for task_id in ("reading", "exercise", "experiment", "acceptance")
            },
            "needs_review": local["needs_review"],
            "content_sha": local["ack_content_sha"],
        }
        incoming_content = {
            "tasks": {k: v["status"] for k, v in record["tasks"].items()},
            "needs_review": record["needs_review"],
            "content_sha": record["content_sha"],
        }
        if local_content == incoming_content:
            report["counts"]["unchanged"] += 1
        else:
            report["counts"]["conflict"] += 1
            report["conflicts"].append({
                "day_id": day_id,
                "local": {
                    "revision": local["revision"],
                    "tasks": local_content["tasks"],
                    "needs_review": local["needs_review"],
                },
                "incoming": {
                    "revision": record["revision"],
                    "tasks": incoming_content["tasks"],
                    "needs_review": record["needs_review"],
                },
            })
    return report, incoming, plan_current


def create_import_job(user, release, raw: bytes) -> LearningDataJob:
    """上传 + 完整预检。预检失败也保留 job（状态 precheck_failed + 报告）。"""
    payload = parse_import_bytes(raw)
    try:
        report, incoming, plan_current = precheck(user, release, payload)
    except TransferError as exc:
        job = LearningDataJob.objects.create(
            user=user, kind=DataJobKind.IMPORT,
            status=DataJobStatus.PRECHECK_FAILED,
            report_json={"error": {
                "code": exc.code, "message": exc.message, "details": exc.details,
            }},
        )
        return job

    job = LearningDataJob.objects.create(
        user=user, kind=DataJobKind.IMPORT, status=DataJobStatus.PRECHECK_OK,
        report_json=report, expires_at=timezone.now() + timezone.timedelta(hours=24),
    )
    private_dir = Path(settings.PRIVATE_ASSET_ROOT) / "imports"
    private_dir.mkdir(parents=True, exist_ok=True)
    path = private_dir / f"import-{job.pk}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    job.private_file = f"imports/import-{job.pk}.json"
    job.save(update_fields=["private_file"])

    for conflict in report["conflicts"]:
        LearningImportConflict.objects.create(
            job=job, day_id=conflict["day_id"],
            local_payload=conflict["local"],
            incoming_payload=conflict["incoming"],
        )
    _audit(user, "data.import.precheck", "job", job.pk, {"counts": report["counts"]})
    return job


# ---------------------------------------------------------------------------
# 导入应用
# ---------------------------------------------------------------------------

def _write_day(user, record: dict, revision: int):
    DayProgress.objects.update_or_create(
        user=user, day_id=record["day_id"],
        defaults={
            "ack_content_sha": record["content_sha"],
            "needs_review": record["needs_review"],
            "revision": revision,
        },
    )
    for task_id, entry in record["tasks"].items():
        if entry["status"] == TaskStatus.NOT_APPLICABLE:
            continue  # not_applicable 由类型派生，导入不写入。
        TaskProgress.objects.update_or_create(
            user=user, day_id=record["day_id"], task_id=task_id,
            defaults={"status": entry["status"]},
        )


def apply_import(user, release, job: LearningDataJob, *, mode: str,
                 resolutions: dict[str, str] | None) -> dict:
    """应用导入：merge 或 replace（先快照）。单用户事务；失败回滚。"""
    if job.status != DataJobStatus.PRECHECK_OK:
        raise TransferError("JOB_NOT_READY", f"导入任务状态为 {job.status}，无法应用")
    if job.expires_at and job.expires_at < timezone.now():
        job.status = DataJobStatus.EXPIRED
        job.save(update_fields=["status"])
        raise TransferError("JOB_EXPIRED", "预检结果已过期，请重新上传")
    if mode not in ("merge", "replace"):
        raise TransferError("MODE_INVALID", "mode 必须为 merge 或 replace")

    path = Path(settings.PRIVATE_ASSET_ROOT) / job.private_file
    if not path.is_file():
        raise TransferError("FILE_MISSING", "导入文件丢失，请重新上传")
    payload = json.loads(path.read_text(encoding="utf-8"))
    report, incoming, plan_current = precheck(user, release, payload)

    if report["counts"]["conflict"] and mode == "merge":
        pending = [c["day_id"] for c in report["conflicts"]]
        unresolved = [day_id for day_id in pending
                      if (resolutions or {}).get(day_id) not in ("local", "incoming")]
        if unresolved:
            raise TransferError(
                "CONFLICTS_UNRESOLVED",
                "存在未处理的冲突，请为每条冲突选择 保留本机/使用导入",
                {"unresolved": unresolved},
            )

    known = set()
    if release is not None:
        from apps.content.models import ContentDayVersion

        known = set(
            ContentDayVersion.objects.filter(release=release)
            .values_list("day_id", flat=True)
        )
    local_rows = {
        row["day_id"]: row for row in DayProgress.objects.filter(user=user)
        .values("day_id", "revision")
    }

    result = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0,
              "conflict_local": 0, "conflict_incoming": 0}

    with transaction.atomic():
        snapshot_job = None
        if mode == "replace":
            snapshot_job = _create_snapshot(user)
            DayProgress.objects.filter(user=user).delete()
            TaskProgress.objects.filter(user=user).delete()

        for record in incoming:
            day_id = record["day_id"]
            if day_id not in known:
                result["skipped"] += 1
                continue
            local = local_rows.get(day_id)
            conflict_choice = None
            if local is not None and any(
                c["day_id"] == day_id for c in report["conflicts"]
            ):
                conflict_choice = (resolutions or {}).get(day_id)

            if local is None:
                _write_day(user, record, max(record["revision"], 1))
                result["added"] += 1
            elif conflict_choice == "local":
                result["conflict_local"] += 1
            elif conflict_choice == "incoming":
                # 基于最新 revision 应用导入内容。
                revision = max(local["revision"], record["revision"]) + 1
                _write_day(user, record, revision)
                result["conflict_incoming"] += 1
            elif mode == "replace":
                revision = max(local["revision"], record["revision"]) + 1
                _write_day(user, record, revision)
                result["updated"] += 1
            else:
                # 内容未变化（合并模式默认保守路径）。
                result["unchanged"] += 1

        if mode == "replace" or (mode == "merge" and plan_current):
            if plan_current is None and mode == "replace":
                LearningPlan.objects.filter(user=user).update(
                    current_day_id=None, revision=1,
                )
            else:
                LearningPlan.objects.update_or_create(
                    user=user,
                    defaults={"current_day_id": plan_current},
                )

        job.status = DataJobStatus.APPLIED
        job.report_json = {**report, "result": result,
                           "mode": mode,
                           "snapshot_job_id": snapshot_job.pk if snapshot_job else None}
        job.save(update_fields=["status", "report_json"])

    _audit(user, "data.import.apply", "job", job.pk, {"mode": mode, "result": result})
    return result


def _create_snapshot(user) -> LearningDataJob:
    """替换前快照：当前完整数据写入私有文件，可恢复。"""
    from apps.content.models import SiteState

    payload = build_export_payload(user, SiteState.get_active_release())
    job = LearningDataJob.objects.create(
        user=user, kind=DataJobKind.SNAPSHOT, status=DataJobStatus.APPLIED,
        report_json={"day_count": len(payload["days"])},
    )
    private_dir = Path(settings.PRIVATE_ASSET_ROOT) / "snapshots"
    private_dir.mkdir(parents=True, exist_ok=True)
    path = private_dir / f"snapshot-{job.pk}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    job.private_file = f"snapshots/snapshot-{job.pk}.json"
    job.save(update_fields=["private_file"])
    return job


def delete_learning_data(user) -> int:
    """删除学习数据（保留账号、主题偏好与审计事件）。"""
    with transaction.atomic():
        days = DayProgress.objects.filter(user=user).delete()[0]
        TaskProgress.objects.filter(user=user).delete()
        LearningPlan.objects.filter(user=user).delete()
        _audit(user, "data.delete", "account", user.pk, {"days_deleted": days})
    return days
