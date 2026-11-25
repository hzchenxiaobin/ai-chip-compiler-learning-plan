"""我的学习 / 设置页面（设计文档 §4.5）。

设置页的导出/导入/删除同时提供标准表单 POST 基础路径（无 JS 可用），
前端 ES Modules 仅做渐进增强。
"""
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.content.models import ContentDayVersion, SiteState

from . import transfer
from .models import DataJobKind, LearningDataJob
from .services import get_dashboard_view


def _all_metas(release):
    return [
        row["metadata_json"]
        for row in ContentDayVersion.objects.filter(release=release)
        .order_by("day_id").values("metadata_json")
    ]


@login_required
def dashboard(request):
    release = SiteState.get_active_release()
    if release is None:
        return render(request, "content/no_content.html", status=503)
    view = get_dashboard_view(request.user, release, _all_metas(release))
    meta_by_day = {m["day_id"]: m for m in _all_metas(release)}
    return render(request, "learning/dashboard.html", {
        "release": release,
        "view": view,
        "meta_by_day": meta_by_day,
    })


@login_required
def settings_page(request):
    release = SiteState.get_active_release()
    preview_job = None
    job_id = request.GET.get("preview")
    if job_id and job_id.isdigit():
        preview_job = LearningDataJob.objects.filter(
            pk=int(job_id), user=request.user, kind=DataJobKind.IMPORT
        ).first()

    jobs = LearningDataJob.objects.filter(user=request.user).order_by("-created_at")[:10]
    from apps.accounts.models import Profile

    profile, _ = Profile.objects.get_or_create(user=request.user)
    context = {
        "release": release,
        "profile": profile,
        "jobs": jobs,
        "preview_job": preview_job,
        "conflicts": list(preview_job.conflicts.all()) if preview_job else [],
        "report": preview_job.report_json if preview_job else None,
    }
    return render(request, "learning/settings.html", context)


@login_required
@require_http_methods(["POST"])
def settings_export(request):
    release = SiteState.get_active_release()
    job = transfer.create_export_job(request.user, release)
    token = transfer.make_download_token(job.pk)
    messages.success(request, f"导出完成：{job.report_json.get('day_count', 0)} 天记录。")
    return redirect(f"/api/v1/me/exports/{job.pk}/download/?token={token}")


@login_required
@require_http_methods(["POST"])
def settings_import_upload(request):
    release = SiteState.get_active_release()
    upload = request.FILES.get("file")
    if upload is None:
        messages.error(request, "请选择 JSON 备份文件。")
        return redirect("/settings/")
    raw = upload.read()
    if len(raw) > transfer.MAX_FILE_BYTES:
        messages.error(request, "文件超过 5 MiB 上限。")
        return redirect("/settings/")
    job = transfer.create_import_job(request.user, release, raw)
    if job.status == "precheck_failed":
        messages.error(
            request,
            "预检失败：" + str(job.report_json.get("error", {}).get("message", "")),
        )
        return redirect("/settings/")
    counts = job.report_json.get("counts", {})
    messages.info(
        request,
        f"预检完成：新增 {counts.get('add', 0)}、未变化 {counts.get('unchanged', 0)}、"
        f"冲突 {counts.get('conflict', 0)}、跳过 {counts.get('skip', 0)}。请确认应用方式。",
    )
    return redirect(f"/settings/?preview={job.pk}#import")


@login_required
@require_http_methods(["POST"])
def settings_import_apply(request):
    release = SiteState.get_active_release()
    job_id = request.POST.get("job_id", "")
    if not job_id.isdigit():
        messages.error(request, "无效的导入任务。")
        return redirect("/settings/")
    job = LearningDataJob.objects.filter(
        pk=int(job_id), user=request.user, kind=DataJobKind.IMPORT
    ).first()
    if job is None:
        messages.error(request, "导入任务不存在。")
        return redirect("/settings/")
    mode = request.POST.get("mode", "merge")
    resolutions = {}
    for conflict in job.conflicts.all():
        choice = request.POST.get(f"conflict-{conflict.day_id}", "")
        if choice in ("local", "incoming"):
            resolutions[conflict.day_id] = choice
    try:
        result = transfer.apply_import(
            request.user, release, job, mode=mode, resolutions=resolutions
        )
    except transfer.TransferError as exc:
        messages.error(request, f"导入失败：{exc.message}")
        return redirect(f"/settings/?preview={job.pk}#import")
    messages.success(
        request,
        f"导入完成：新增 {result['added']}、更新 {result['updated']}、"
        f"未变化 {result['unchanged']}、跳过 {result['skipped']}、"
        f"冲突保留本机 {result['conflict_local']}、采用导入 {result['conflict_incoming']}。",
    )
    return redirect("/settings/")


@login_required
@require_http_methods(["POST"])
def settings_restore_snapshot(request, job_id: int):
    """从替换前快照恢复：以快照文件走标准导入预检流程。"""
    from django.conf import settings as dj_settings

    snapshot = LearningDataJob.objects.filter(
        pk=job_id, user=request.user, kind=DataJobKind.SNAPSHOT
    ).first()
    if snapshot is None:
        messages.error(request, "快照不存在。")
        return redirect("/settings/#import")
    path = Path(dj_settings.PRIVATE_ASSET_ROOT) / snapshot.private_file
    if not path.is_file():
        messages.error(request, "快照文件已过期或丢失。")
        return redirect("/settings/#import")
    job = transfer.create_import_job(
        request.user, SiteState.get_active_release(), path.read_bytes()
    )
    if job.status == "precheck_failed":
        messages.error(
            request,
            "快照预检失败：" + str(job.report_json.get("error", {}).get("message", "")),
        )
        return redirect("/settings/#import")
    messages.info(
        request,
        "快照已载入预检。请在下方确认应用方式（建议选择“替换”以完整恢复快照时的状态）。",
    )
    return redirect(f"/settings/?preview={job.pk}#import")


@login_required
@require_http_methods(["POST"])
def settings_delete_data(request):
    if request.POST.get("confirm") != "yes":
        messages.error(request, "请在删除学习数据前勾选确认。")
        return redirect("/settings/#data")
    password = request.POST.get("password", "")
    if not request.user.check_password(password):
        messages.error(request, "密码不正确。")
        return redirect("/settings/#data")
    days = transfer.delete_learning_data(request.user)
    messages.success(request, f"已删除 {days} 天学习记录（账号与偏好保留）。")
    return redirect("/settings/")


@login_required
@require_http_methods(["POST"])
def settings_delete_account(request):
    password = request.POST.get("password", "")
    if not request.user.check_password(password):
        messages.error(request, "密码不正确（账号删除需重新认证）。")
        return redirect("/settings/#account")
    from django.contrib.auth import logout

    from .models import AuditEvent

    AuditEvent.objects.create(
        actor=None, action="account.delete", object_type="account",
        object_id=str(request.user.pk),
        safe_metadata={"username": request.user.username},
    )
    user = request.user
    logout(request)
    user.delete()
    messages.success(request, "账号已删除。感谢使用。")
    return redirect("/")
