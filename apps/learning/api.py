"""学习 JSON API（设计文档 §9.3）。

统一 /api/v1/ 前缀，浏览器同源 Session＋CSRF。
错误结构 {code, message, details}；412 附带当前服务端记录。
"""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import logout
from django.db import DatabaseError
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.content.models import ContentDayVersion, SiteState

from . import transfer
from .models import DayProgress, LearningDataJob
from .services import (
    PreconditionFailed,
    ValidationError,
    day_representation,
    get_dashboard_view,
    set_plan,
    update_progress,
)


def api_auth(view):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"code": "NOT_AUTHENTICATED", "message": "请先登录"}, status=401
            )
        return view(request, *args, **kwargs)

    wrapped.__name__ = view.__name__
    return wrapped


def _error(code, message, status=400, details=None):
    return JsonResponse(
        {"code": code, "message": message, "details": details or {}}, status=status
    )


def _rate_limit(request, bucket: str, limit: int, window: int = 3600) -> bool:
    """简单 Redis 计数限流；Redis 不可用时放行（§10.3 登录与上传限流）。"""
    from django.core.cache import cache

    key = f"rl:{bucket}:{request.user.pk}"
    try:
        count = cache.get(key, 0)
        if count is None:
            count = 0
        if count >= limit:
            return False
        cache.set(key, count + 1, window)
    except Exception:
        return True
    return True


EXPORT_RATE_LIMIT = 10       # 次/小时
IMPORT_RATE_LIMIT = 10       # 次/小时


def db_unavailable(view):
    """数据库不可用时返回明确失败（设计文档 §9.4：写入明确失败）。"""

    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except DatabaseError:
            return _error(
                "STORAGE_UNAVAILABLE",
                "数据存储暂时不可用，本次更改未保存；你的历史数据不会丢失。",
                503,
            )

    wrapped.__name__ = view.__name__
    return wrapped


def _parse_etag(value):
    """If-Match: "N" → N；支持 W/ 前缀与裸数字。"""
    if value is None:
        return None
    value = value.strip()
    if value == "*":
        return "*"
    if value.startswith("W/"):
        value = value[2:]
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value or None


def _json_body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("BODY_INVALID", "请求体不是合法 JSON")
    if not isinstance(data, dict):
        raise ValidationError("BODY_INVALID", "请求体必须是 JSON 对象")
    return data


def _meta_or_none(release, day_id):
    row = (
        ContentDayVersion.objects.filter(release=release, day_id=day_id)
        .values("metadata_json")
        .first()
    )
    return row["metadata_json"] if row else None


def _all_metas(release):
    return [
        row["metadata_json"]
        for row in ContentDayVersion.objects.filter(release=release)
        .order_by("day_id").values("metadata_json")
    ]


# ---------------------------------------------------------------------------
# 进度
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
@api_auth
def me_dashboard(request):
    release = SiteState.get_active_release()
    if release is None:
        return _error("NO_ACTIVE_RELEASE", "内容尚未发布", 503)
    return JsonResponse(get_dashboard_view(request.user, release, _all_metas(release)))


@require_http_methods(["GET"])
@api_auth
def me_progress(request, day_id: str):
    release = SiteState.get_active_release()
    if release is None:
        return _error("NO_ACTIVE_RELEASE", "内容尚未发布", 503)
    meta = _meta_or_none(release, day_id)
    if meta is None:
        return _error("DAY_NOT_FOUND", f"日课不存在：{day_id}", 404)
    representation = day_representation(request.user, release, meta)
    response = JsonResponse(representation)
    response["ETag"] = f'"{representation["revision"]}"'
    return response


@require_http_methods(["PATCH", "PUT"])
@db_unavailable
@api_auth
def me_progress_update(request, day_id: str):
    release = SiteState.get_active_release()
    if release is None:
        return _error("NO_ACTIVE_RELEASE", "内容尚未发布", 503)
    meta = _meta_or_none(release, day_id)
    if meta is None:
        return _error("DAY_NOT_FOUND", f"日课不存在：{day_id}", 404)
    try:
        body = _json_body(request)
        tasks = body.get("tasks")
        if tasks is not None and not isinstance(tasks, dict):
            raise ValidationError("BODY_INVALID", "tasks 必须为对象")
        acknowledge = bool(body.get("acknowledge_content"))
        if tasks is None and not acknowledge:
            raise ValidationError("BODY_INVALID", "需要 tasks 或 acknowledge_content")
        representation = update_progress(
            request.user, release, meta,
            tasks=tasks, acknowledge=acknowledge,
            if_match=_parse_etag(request.headers.get("If-Match")),
            if_none_match=request.headers.get("If-None-Match"),
        )
    except ValidationError as exc:
        return _error(exc.code, exc.message, 400, exc.details)
    except PreconditionFailed as exc:
        return JsonResponse(
            {
                "code": "PRECONDITION_FAILED",
                "message": exc.message,
                "current": exc.current,
            },
            status=412,
        )
    response = JsonResponse(representation)
    response["ETag"] = f'"{representation["revision"]}"'
    return response


@require_http_methods(["GET", "PUT"])
@db_unavailable
@api_auth
def me_plan(request):
    release = SiteState.get_active_release()
    if release is None:
        return _error("NO_ACTIVE_RELEASE", "内容尚未发布", 503)
    if request.method == "GET":
        from .models import LearningPlan

        plan = LearningPlan.objects.filter(user=request.user).first()
        return JsonResponse({
            "current_day_id": plan.current_day_id if plan else None,
            "revision": plan.revision if plan else 0,
        })
    try:
        body = _json_body(request)
        current_day_id = body.get("current_day_id", None)
        if current_day_id is not None and not isinstance(current_day_id, str):
            raise ValidationError("BODY_INVALID", "current_day_id 必须为字符串或 null")
        result = set_plan(
            request.user, release, current_day_id,
            if_match=_parse_etag(request.headers.get("If-Match")),
        )
    except ValidationError as exc:
        return _error(exc.code, exc.message, 400, exc.details)
    except PreconditionFailed as exc:
        return JsonResponse(
            {"code": "PRECONDITION_FAILED", "message": exc.message,
             "current": exc.current},
            status=412,
        )
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# 导出 / 导入 / 删除
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@db_unavailable
@api_auth
def me_exports(request):
    if not _rate_limit(request, "export", EXPORT_RATE_LIMIT):
        return _error("RATE_LIMITED", "导出过于频繁，请稍后再试", 429)
    release = SiteState.get_active_release()
    job = transfer.create_export_job(request.user, release)
    token = transfer.make_download_token(job.pk)
    return JsonResponse({
        "job_id": job.pk,
        "day_count": job.report_json.get("day_count", 0),
        "download_url": f"/api/v1/me/exports/{job.pk}/download/?token={token}",
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
    }, status=201)


@require_http_methods(["GET"])
@api_auth
def me_export_download(request, job_id: int):
    job = LearningDataJob.objects.filter(
        pk=job_id, user=request.user, kind="export"
    ).first()
    if job is None:
        return _error("JOB_NOT_FOUND", "导出任务不存在", 404)
    if job.expires_at and job.expires_at < timezone.now():
        return _error("JOB_EXPIRED", "导出已过期", 410)
    token = request.GET.get("token", "")
    if not transfer.verify_download_token(job.pk, token):
        return _error("TOKEN_INVALID", "下载令牌无效或已过期", 403)
    path = Path(settings.PRIVATE_ASSET_ROOT) / job.private_file
    if not path.is_file():
        return _error("FILE_MISSING", "导出文件丢失", 410)
    response = FileResponse(
        path.open("rb"), as_attachment=True,
        filename=f"ai-chip-compiler-learning-backup-{timezone.now().strftime('%Y%m%d')}.json",
        content_type="application/json",
    )
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["POST"])
@db_unavailable
@api_auth
def me_imports(request):
    if not _rate_limit(request, "import", IMPORT_RATE_LIMIT):
        return _error("RATE_LIMITED", "导入过于频繁，请稍后再试", 429)
    release = SiteState.get_active_release()
    upload = request.FILES.get("file")
    if upload is None:
        return _error("FILE_REQUIRED", "请上传 JSON 文件（字段名 file）")
    raw = upload.read()
    if len(raw) > transfer.MAX_FILE_BYTES:
        return _error("FILE_TOO_LARGE", "文件超过大小上限", 413)
    job = transfer.create_import_job(request.user, release, raw)
    if job.status == "precheck_failed":
        return JsonResponse(
            {"job_id": job.pk, "status": job.status, "report": job.report_json},
            status=400,
        )
    return JsonResponse({
        "job_id": job.pk, "status": job.status, "report": job.report_json,
    }, status=201)


@require_http_methods(["GET"])
@api_auth
def me_import_detail(request, job_id: int):
    job = LearningDataJob.objects.filter(
        pk=job_id, user=request.user, kind="import"
    ).first()
    if job is None:
        return _error("JOB_NOT_FOUND", "导入任务不存在", 404)
    return JsonResponse({
        "job_id": job.pk, "status": job.status, "report": job.report_json,
        "conflicts": [
            {
                "day_id": c.day_id,
                "local": c.local_payload,
                "incoming": c.incoming_payload,
                "resolution": c.resolution,
            }
            for c in job.conflicts.all()
        ],
    })


@require_http_methods(["POST"])
@db_unavailable
@api_auth
def me_import_apply(request, job_id: int):
    release = SiteState.get_active_release()
    job = LearningDataJob.objects.filter(
        pk=job_id, user=request.user, kind="import"
    ).first()
    if job is None:
        return _error("JOB_NOT_FOUND", "导入任务不存在", 404)
    try:
        body = _json_body(request)
        mode = body.get("mode", "merge")
        resolutions = body.get("resolutions") or {}
        if not isinstance(resolutions, dict):
            raise transfer.TransferError("BODY_INVALID", "resolutions 必须为对象")
        result = transfer.apply_import(
            request.user, release, job, mode=mode, resolutions=resolutions
        )
    except transfer.TransferError as exc:
        return _error(exc.code, exc.message, 409, exc.details)
    return JsonResponse({"job_id": job.pk, "status": job.status, "result": result})


@require_http_methods(["DELETE"])
@db_unavailable
@api_auth
def me_data_delete(request):
    try:
        body = _json_body(request)
        if not body.get("confirm"):
            raise ValidationError("CONFIRM_REQUIRED", "请确认删除（confirm: true）")
        password = body.get("password", "")
        if not request.user.check_password(password):
            raise ValidationError("PASSWORD_INVALID", "密码不正确")
        days = transfer.delete_learning_data(request.user)
    except ValidationError as exc:
        return _error(exc.code, exc.message, 400, exc.details)
    return JsonResponse({"deleted_day_records": days})


@require_http_methods(["DELETE"])
@db_unavailable
@api_auth
def me_account_delete(request):
    try:
        body = _json_body(request)
        password = body.get("password", "")
        if not request.user.check_password(password):
            raise ValidationError("PASSWORD_INVALID", "密码不正确（账号删除需重新认证）")
        from .models import AuditEvent

        AuditEvent.objects.create(
            actor=None, action="account.delete", object_type="account",
            object_id=str(request.user.pk),
            safe_metadata={"username": request.user.username},
        )
        user = request.user
        logout(request)
        user.delete()
    except ValidationError as exc:
        return _error(exc.code, exc.message, 400, exc.details)
    return JsonResponse({"deleted": True})
