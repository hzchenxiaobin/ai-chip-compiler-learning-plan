"""教程导入器（设计文档 §7.1、§13.1 WP-01）。

从指定 Git commit 快照（git archive，不跟随移动分支）解析 168 天教程：
解析 → 覆盖 → content_sha → 白名单 HTML → 搜索 chunk/posting → 源码 ZIP →
全量校验 → ready → 原子激活。任何失败：release 标记 failed，仅保留诊断，
不切换 active_release，旧版本继续服务。
"""
import hashlib
import re
import shutil
import tempfile
import time
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.content.models import (
    ContentAsset,
    ContentChunk,
    ContentDay,
    ContentDayVersion,
    ContentRelease,
    ReleaseStatus,
    SiteState,
)
from apps.search import service as search_service
from apps.search.models import SearchPosting, SearchToken

from .chunking import build_chunks, collect_code_paths, collect_error_tokens, heading_anchors
from .content_hash import compute_content_sha
from .errors import ImporterError
from .overrides import canonical_override_payload, load_day_overrides
from .parsing import (
    KEY_OUTPUT_DEFAULT_TYPES,
    TYPE_TASKS,
    infer_day_type,
    parse_estimated_minutes,
    parse_readme,
)
from .rendering import render_markdown_html, rewrite_asset_links
from .zip_builder import build_source_zip

GITHUB_REPO_URL = "https://github.com/hzchenxiaobin/ai-chip-compiler-learning-plan"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

# 固定样例查询（设计文档 §7.5）：必须命中预期日课。
SAMPLE_QUERIES = [
    ("MLIR", ["day-029"]),
    ("mlir-opt", ["day-029"]),
    ("FileCheck", ["day-029"]),
    ("run_all.sh", []),
    ("常量折叠", []),
    ("Roofline", []),
]


def resolve_commit(repo_root: Path, commit: str) -> str:
    """解析 HEAD/分支名到 40 位提交；禁止导入过程中跟随移动引用。"""
    if COMMIT_RE.match(commit):
        return commit
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", commit + "^{commit}"],
            cwd=repo_root, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ImporterError("COMMIT_UNRESOLVED", f"无法解析提交：{commit}") from None
    resolved = result.stdout.strip()
    if result.returncode != 0 or not COMMIT_RE.match(resolved):
        raise ImporterError("COMMIT_UNRESOLVED", f"无法解析提交：{commit}") from None
    return resolved


def git_archive_snapshot(repo_root: Path, commit: str, dest: Path):
    """把指定 commit 的内容导出到 dest（tutorials + 覆盖配置）。"""
    import subprocess

    env = {"GIT_DIR": str(repo_root / ".git")}
    try:
        result = subprocess.run(
            ["git", "archive", "--format=tar", commit,
             "tutorials", "config/learning/day-overrides.json",
             "AI芯片编译器学习计划.md"],
            cwd=repo_root, capture_output=True, timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ImporterError("ARCHIVE_FAILED", "git archive 执行失败") from None
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace")[:300]
        raise ImporterError("ARCHIVE_FAILED", f"git archive 失败：{stderr}")
    import tarfile
    import io

    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
        tar.extractall(dest, filter="data")
    # git archive 在无该路径时也会成功但内容为空，这里显式校验。
    if not (dest / "tutorials").is_dir():
        raise ImporterError(
            "ARCHIVE_EMPTY", f"提交 {commit[:12]} 中不包含 tutorials/ 目录"
        )


class PreparedDay:
    __slots__ = ("doc", "record", "chunks", "rendered", "images", "zip_info")

    def __init__(self, doc, record, chunks, rendered, images, zip_info):
        self.doc = doc
        self.record = record
        self.chunks = chunks
        self.rendered = rendered
        self.images = images
        self.zip_info = zip_info


def _safe_path(value: str) -> bool:
    if not value:
        return False
    if value.startswith("/") or "\\" in value:
        return False
    parts = value.split("/")
    return ".." not in parts


def _copy_images(day_rel: str, day_dir: Path, asset_dir: Path) -> list[tuple[Path, Path, str]]:
    """复制日课图片到公开资产目录。返回 [(源, 目标, 相对key)]。"""
    images_dir = day_dir / "images"
    if not images_dir.is_dir():
        return []
    copied = []
    for path in sorted(images_dir.rglob("*")):
        if path.is_symlink() or not path.is_file():
            if path.is_symlink():
                raise ImporterError("IMAGE_SYMLINK", f"图片不允许符号链接：{path}", source=images_dir)
            continue
        rel = path.relative_to(images_dir).as_posix()
        target = asset_dir / day_rel / "images" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append((path, target, rel))
    return copied


def import_release(*, content_commit: str, config_version: int = 1,
                   source_root: Path | None = None, repo_root: Path | None = None,
                   expected_days: int = 168, activate: bool = True,
                   logger=None) -> ContentRelease:
    """导入并（默认）激活一个内容版本。失败时抛 ImporterError。"""
    log = logger or (lambda msg: None)
    started = time.monotonic()

    if not COMMIT_RE.match(content_commit):
        raise ImporterError("COMMIT_INVALID", f"提交哈希格式无效：{content_commit!r}")

    base_dir = Path(getattr(settings, "BASE_DIR", Path(".")))
    repo_root = repo_root or base_dir
    public_asset_root = Path(settings.PUBLIC_ASSET_ROOT)
    asset_dir = public_asset_root / "releases" / content_commit

    # 重复导入处理：active/ready 拒绝；失败/中断版本清理后重建。
    existing = ContentRelease.objects.filter(
        commit=content_commit, config_version=config_version
    ).first()
    if existing and existing.status in (ReleaseStatus.ACTIVE, ReleaseStatus.READY):
        raise ImporterError(
            "RELEASE_EXISTS",
            f"该 (commit, config_version) 已存在且状态为 {existing.status}；"
            "如需重新导入请提升 config_version",
        )
    if existing:
        existing.delete()
        shutil.rmtree(asset_dir, ignore_errors=True)

    temp_dir = None
    if source_root is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="import-"))
        git_archive_snapshot(repo_root, content_commit, temp_dir)
        source_root = temp_dir
    source_root = Path(source_root)

    plan_path = source_root / "AI芯片编译器学习计划.md"
    plan_markdown = ""
    if plan_path.is_file():
        try:
            plan_markdown = plan_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ImporterError(
                "ENCODING_INVALID", "计划文件不是合法 UTF-8", source=plan_path
            ) from None

    release = ContentRelease.objects.create(
        commit=content_commit, config_version=config_version,
        status=ReleaseStatus.VALIDATING, plan_markdown=plan_markdown,
    )
    log(f"[import] release {content_commit[:12]} validating")

    try:
        prepared = _prepare_all_days(source_root, content_commit, expected_days, asset_dir)
        _persist(release, prepared, logger=log)
        _validate_release(release, prepared, expected_days, log)
        if activate:
            with transaction.atomic():
                release.activate()
            log(f"[import] release activated: {content_commit[:12]}")
        else:
            log(f"[import] release ready (未激活): {content_commit[:12]}")
    except ImporterError as exc:
        _mark_failed(release, exc)
        shutil.rmtree(asset_dir, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001 —— 未知异常同样进入失败诊断。
        _mark_failed(release, ImporterError("IMPORT_CRASH", f"{type(exc).__name__}: {exc}"))
        shutil.rmtree(asset_dir, ignore_errors=True)
        raise
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)

    elapsed = time.monotonic() - started
    log(
        f"[import] done: {release.day_count} days / {release.chunk_count} chunks / "
        f"{SearchPosting.objects.filter(version__release=release).count()} postings / "
        f"{SearchToken.objects.count()} tokens in {elapsed:.1f}s"
    )
    return release


def _mark_failed(release: ContentRelease, exc: ImporterError):
    """失败版本只保留诊断：删除读模型行，保留 release 行与错误报告。"""
    release.day_versions.all().delete()  # 级联删除 chunk/asset/posting
    release.status = ReleaseStatus.FAILED
    release.day_count = 0
    release.chunk_count = 0
    release.error_report = exc.as_report()
    release.save(update_fields=["status", "error_report", "day_count", "chunk_count"])
    SiteState.invalidate_cache()


def _prepare_all_days(source_root: Path, commit: str, expected_days: int,
                      asset_dir: Path) -> list[PreparedDay]:
    readmes = sorted(source_root.glob("tutorials/week-*/day-*/README.md"))
    if not readmes:
        raise ImporterError("NO_TUTORIALS", "没有找到 tutorials/week-*/day-*/README.md")

    overrides = load_day_overrides(source_root)
    docs = [parse_readme(path) for path in readmes]

    # 时间回退：正文解析失败时允许覆盖配置修正（设计文档 §7.3）。
    for doc in docs:
        if doc.time is None:
            fallback = overrides.get(doc.day_id, {}).get("time")
            if fallback:
                doc.time = fallback
            else:
                raise ImporterError(
                    "TIME_REQUIRED",
                    f"预计时间无法解析且覆盖配置未提供 time",
                    source=doc.source,
                )

    # 完整性：日号 1..N 连续且唯一。
    day_numbers = [doc.day for doc in docs]
    if day_numbers != list(range(1, expected_days + 1)):
        missing = sorted(set(range(1, expected_days + 1)) - set(day_numbers))
        raise ImporterError(
            "DAY_SEQUENCE_INVALID",
            f"日课数量 {len(docs)}（期望 {expected_days}）；缺失：{missing[:8]}",
        )

    known_ids = {doc.day_id for doc in docs}
    unused = sorted(set(overrides) - known_ids)
    if unused:
        raise ImporterError(
            "CONFIG_UNUSED_OVERRIDE", f"覆盖配置引用了不存在的日课：{unused}"
        )

    prepared = []
    for doc in docs:
        override = overrides.get(doc.day_id, {})
        day_dir = doc.source_dir
        day_rel = f"tutorials/week-{doc.week:03d}/{doc.day_id}"
        phase = (doc.day - 1) // 28 + 1

        day_type = override.get("type") or infer_day_type(doc.day, phase)
        required_tasks = list(TYPE_TASKS[day_type])
        skills = override.get("skills", [])
        key_output = override.get("key_output", day_type in KEY_OUTPUT_DEFAULT_TYPES)
        source_include = override.get("source_include", [])

        code_dir = None
        for name in ("code", "examples"):
            candidate = day_dir / name
            if candidate.is_dir():
                code_dir = candidate
                break
        code_rel = f"{day_rel}/{code_dir.name}" if code_dir else None
        run_all = bool(code_dir and (code_dir / "run_all.sh").is_file()
                       and not (code_dir / "run_all.sh").is_symlink())
        outputs_dir = code_dir / "outputs" if code_dir else None
        has_outputs = bool(outputs_dir and outputs_dir.is_dir())

        content_sha = compute_content_sha(day_dir, canonical_override_payload(override))

        code_paths = collect_code_paths(code_dir).paths if code_dir else []
        error_tokens = collect_error_tokens(doc.markdown)
        chunks = build_chunks(doc.markdown, doc.day_id)

        asset_url_base = f"{settings.PUBLIC_ASSET_URL}releases/{commit}/{day_rel}/"
        github_blob_base = f"{GITHUB_REPO_URL}/blob/{commit}/{day_rel}"
        rewritten = rewrite_asset_links(doc.markdown, asset_url_base, github_blob_base, day_dir)
        rendered = render_markdown_html(rewritten)

        # 锚点一致性：分片锚点必须来自真实标题。
        anchors = set(heading_anchors(doc.markdown))
        for chunk in chunks:
            if chunk.anchor and chunk.anchor not in anchors:
                raise ImporterError(
                    "ANCHOR_INVALID",
                    f"分片锚点 {chunk.anchor!r} 不存在于标题锚点",
                    source=doc.source,
                )

        record = {
            "day_id": doc.day_id,
            "day": doc.day,
            "week": doc.week,
            "phase": phase,
            "type": day_type,
            "key_output": key_output,
            "title": doc.title,
            "objective": doc.objective,
            "time": doc.time,
            "prerequisites": override.get("prerequisites", doc.prerequisites),
            "deliverable": override.get("deliverable", doc.deliverable),
            "source_path": f"{day_rel}/README.md",
            "code_path": code_rel,
            "url": f"{day_rel}/",
            "code_paths": code_paths,
            "error_tokens": error_tokens,
            "source_zip": None,  # 由资产阶段填充。
            "code_url": f"{GITHUB_REPO_URL}/tree/{commit}/{code_rel}" if code_rel else None,
            "outputs_url": (
                f"{GITHUB_REPO_URL}/tree/{commit}/{code_rel}/outputs"
                if code_rel and has_outputs else None
            ),
            "run_all": run_all,
            "skills": skills,
            "required_tasks": required_tasks,
            "content_sha": content_sha,
        }

        # 集合级业务校验（设计文档 §7.3）。
        if record["week"] != (record["day"] - 1) // 7 + 1:
            raise ImporterError("WEEK_RULE_INVALID", "周号与日号不一致", source=doc.source)
        if record["phase"] != (record["day"] - 1) // 28 + 1:
            raise ImporterError("PHASE_RULE_INVALID", "阶段号与日号不一致", source=doc.source)
        for path_field in ("source_path", "code_path", "url"):
            if record[path_field] and not _safe_path(record[path_field]):
                raise ImporterError(
                    "PATH_UNSAFE", f"路径不安全：{record[path_field]!r}", source=doc.source
                )

        # 图片与源码 ZIP 写入公开资产目录（文件操作幂等；失败整体清理）。
        images = _copy_images(day_rel, day_dir, asset_dir)
        zip_info = None
        if code_dir is not None:
            staging_zip = asset_dir / "downloads" / f"{doc.day_id}-source.zip"
            zip_info = build_source_zip(staging_zip, code_dir, source_include)
            record["source_zip"] = (
                f"releases/{commit}/downloads/{doc.day_id}-source.zip"
                if zip_info else None
            )

        prepared.append(PreparedDay(doc, record, chunks, rendered, images, zip_info))
    return prepared


def _persist(release: ContentRelease, prepared: list[PreparedDay], logger):
    all_tokens: set[str] = set()
    for item in prepared:
        all_tokens.update(
            search_service.collect_day_tokens(
                {**item.record}, _chunk_dicts(item)
            )
        )
    token_map = search_service.bulk_create_tokens(all_tokens)
    logger(f"[import] tokens: {len(token_map)}")

    postings_total = 0
    with transaction.atomic():
        for item in prepared:
            record = item.record
            day, _ = ContentDay.objects.update_or_create(
                day_id=record["day_id"],
                defaults={
                    "day": record["day"],
                    "week": record["week"],
                    "phase": record["phase"],
                },
            )
            version = ContentDayVersion.objects.create(
                release=release,
                day_ref=day,
                day_id=record["day_id"],
                metadata_json={
                    k: v for k, v in record.items()
                    if k not in ("code_paths", "error_tokens")
                },
                rendered_html=item.rendered,
                content_sha=record["content_sha"],
            )

            meta_text = "\n".join(
                part for part in (
                    record["title"], record["objective"], record["deliverable"],
                    " ".join(record["skills"]),
                ) if part
            )
            chunk_rows = [
                ContentChunk(
                    version=version, chunk_id=f"{record['day_id']}:meta",
                    day_id=record["day_id"], heading="", anchor="", text=meta_text,
                )
            ]
            for chunk in item.chunks:
                chunk_rows.append(
                    ContentChunk(
                        version=version, chunk_id=chunk.chunk_id,
                        day_id=record["day_id"], heading=chunk.heading,
                        anchor=chunk.anchor, text=chunk.text,
                    )
                )
            ContentChunk.objects.bulk_create(chunk_rows, batch_size=500)

            # 资产记录：图片 + 源码 ZIP。
            day_rel = f"tutorials/week-{record['week']:03d}/{record['day_id']}"
            for source_path, _target, rel in item.images:
                digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
                ContentAsset.objects.create(
                    version=version, kind="image", day_id=record["day_id"],
                    storage_key=f"releases/{release.commit}/{day_rel}/images/{rel}",
                    sha256=digest, size=source_path.stat().st_size,
                    visibility="public",
                )
            if item.zip_info:
                zip_sha, zip_size, _entries = item.zip_info
                ContentAsset.objects.create(
                    version=version, kind="source_zip", day_id=record["day_id"],
                    storage_key=record["source_zip"], sha256=zip_sha,
                    size=zip_size, visibility="public",
                )

            postings_total += search_service.build_postings(
                version, record, _chunk_dicts(item), token_map
            )

            day.current_version = version
            day.save(update_fields=["current_version"])

        release.day_count = len(prepared)
        release.chunk_count = sum(len(item.chunks) + 1 for item in prepared)
        release.save(update_fields=["day_count", "chunk_count"])
    logger(f"[import] postings: {postings_total}")


def _chunk_dicts(item: PreparedDay) -> list[dict]:
    return [
        {"chunk_id": chunk.chunk_id, "heading": chunk.heading, "text": chunk.text}
        for chunk in item.chunks
    ]


def _validate_release(release: ContentRelease, prepared: list[PreparedDay],
                      expected_days: int, log):
    """全量校验：168 天、Schema 业务规则、固定样例查询、资产存在性。"""
    versions = release.day_versions.select_related("day_ref")
    if versions.count() != expected_days:
        raise ImporterError(
            "DAY_COUNT_INVALID",
            f"导入日课数 {versions.count()}，期望 {expected_days}",
        )
    seen_days = set()
    for version in versions:
        meta = version.metadata_json
        day_id = meta["day_id"]
        if day_id in seen_days:
            raise ImporterError("DAY_DUPLICATE", f"重复日课：{day_id}")
        seen_days.add(day_id)
        if meta["required_tasks"] != list(TYPE_TASKS[meta["type"]]):
            raise ImporterError(
                "TASKS_MAPPING_INVALID", f"{day_id} 任务映射与类型不一致"
            )
        if not version.rendered_html or "<script" in version.rendered_html:
            raise ImporterError(
                "RENDER_INVALID", f"{day_id} 渲染结果为空或含脚本"
            )

    # 固定样例查询（在事务外对本 release 直接验证）。
    for query, expected_days_for_query in SAMPLE_QUERIES:
        items, total, _cursor = search_service.search(release, query, page_size=10)
        if total == 0:
            raise ImporterError(
                "SAMPLE_QUERY_EMPTY", f"样例查询无结果：{query!r}"
            )
        hit_ids = {item["day_id"] for item in items}
        for expected in expected_days_for_query:
            if expected not in hit_ids:
                raise ImporterError(
                    "SAMPLE_QUERY_MISS",
                    f"样例查询 {query!r} 未命中 {expected}（命中 {sorted(hit_ids)[:5]}）",
                )
    log("[import] sample queries passed")

    # 资产存在性：source_zip 与图片文件真实存在。
    public_root = Path(settings.PUBLIC_ASSET_ROOT)
    for asset in ContentAsset.objects.filter(version__release=release):
        if not (public_root / asset.storage_key).is_file():
            raise ImporterError(
                "ASSET_MISSING", f"资产文件缺失：{asset.storage_key}"
            )

    # release 校验和：全部日课 content_sha 顺序拼接后哈希。
    shas = "".join(
        v["content_sha"] for v in sorted(
            release.day_versions.values("content_sha", "day_id"),
            key=lambda r: r["day_id"],
        )
    )
    release.checksum = hashlib.sha256(shas.encode("ascii")).hexdigest()
    release.status = ReleaseStatus.READY
    release.save(update_fields=["checksum", "status"])
    SiteState.invalidate_cache()
