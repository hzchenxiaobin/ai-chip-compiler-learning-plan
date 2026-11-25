"""验收用例证据测试（设计文档 §12）。

覆盖：TC-B02（导入失败不切换）、TC-B04（图片资产）、TC-B08（无代码日）、
TC-F08（搜索失败明示）、TC-F12（存储不可用 + 缓存公开页可读）、
TC-A05（发布与回滚演练）与激活后的缓存世代失效。
"""
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import TestCase, override_settings

from apps.content.importer import importer as importer_module
from apps.content.importer.errors import ImporterError
from apps.content.importer.importer import import_release
from apps.content.models import (
    ContentDay,
    ContentDayVersion,
    ContentRelease,
    ReleaseStatus,
    SiteState,
)

from . import helpers

PRIVATE_ROOT = Path(tempfile.mkdtemp(prefix="accept-private-"))
PUBLIC_ROOT = Path(tempfile.mkdtemp(prefix="accept-public-"))


def _make_tree(base: Path, day_count: int, title_prefix: str, *,
               no_code_day: int | None = None) -> Path:
    root = base / "source"
    root.mkdir(parents=True, exist_ok=True)
    for day in range(1, day_count + 1):
        helpers.write_day(
            root, day,
            readme=helpers.day_readme(day, f"{title_prefix}{day}"),
            with_code=(day != no_code_day),
            with_runall=(day % 2 == 0),
            with_outputs=(day % 3 == 0),
        )
    helpers.write_plan(root)
    helpers.write_overrides(root, {})
    return root


SAMPLE_QUERIES_OK = [("MLIR", ["day-001"]), ("常量折叠", [])]


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    PUBLIC_ASSET_ROOT=PUBLIC_ROOT,
    PRIVATE_ASSET_ROOT=PRIVATE_ROOT,
)
class ImportAcceptanceTests(TestCase):
    """导入/发布/回滚演练（真实导入器 + 生成树）。"""

    def _import(self, base: Path, commit: str, days: int, title_prefix="测试日课",
                no_code_day=None):
        tree = _make_tree(base, days, title_prefix, no_code_day=no_code_day)
        with mock.patch.object(importer_module, "SAMPLE_QUERIES", SAMPLE_QUERIES_OK):
            return import_release(
                content_commit=commit, source_root=tree,
                expected_days=days, logger=lambda msg: None,
            )

    def test_tc_a05_publish_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_a = self._import(Path(tmp), "a" * 40, 7, title_prefix="A版课程")
            self.assertEqual(release_a.status, ReleaseStatus.ACTIVE)
            self.assertEqual(release_a.day_count, 7)
            # 页面渲染 A 内容。
            response = self.client.get("/tutorials/week-001/day-001/")
            self.assertContains(response, "A版课程1")

            # 发布新版本 B：切换 active，A 转 retired。
            release_b = self._import(Path(tmp), "b" * 40, 7, title_prefix="B版课程")
            release_a.refresh_from_db()
            release_b.refresh_from_db()
            self.assertEqual(release_b.status, ReleaseStatus.ACTIVE)
            self.assertEqual(release_a.status, ReleaseStatus.RETIRED)
            response = self.client.get("/tutorials/week-001/day-001/")
            self.assertContains(response, "B版课程1")

            # 回滚：重新激活 A（上一已知良好版本）。
            from django.db import transaction

            release_a.status = ReleaseStatus.READY
            release_a.save(update_fields=["status"])
            with transaction.atomic():
                release_a.activate()
            release_b.refresh_from_db()
            self.assertEqual(release_b.status, ReleaseStatus.RETIRED)
            response = self.client.get("/tutorials/week-001/day-001/")
            self.assertContains(response, "A版课程1")

    def test_activation_invalidates_page_cache(self):
        """激活新版本后，旧缓存页面不得继续服务（§7.2 失效旧缓存）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._import(Path(tmp), "c" * 40, 7, title_prefix="C版课程")
            # 匿名首页进入缓存。
            self.client.get("/")
            # 发布新版本。
            self._import(Path(tmp), "d" * 40, 7, title_prefix="D版课程")
            response = self.client.get("/")
            self.assertContains(response, "D版课程1")
            self.assertNotContains(response, "C版课程1")

    def test_tc_b02_failed_import_keeps_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = self._import(Path(tmp), "e" * 40, 7, title_prefix="E版课程")
            # 构造坏树：day-002 缺少“前置准备”。
            tree = _make_tree(Path(tmp), 7, "F版课程")
            broken = (
                "# 第 2 天：F版课程2\n\n"
                "> **今日目标**：目标\n"
                "> **预计时间**：学习 30 分钟 + 实践 45 分钟\n"
                "> **今日产出**：产出\n"
            )
            (tree / "tutorials/week-001/day-002/README.md").write_text(
                broken, encoding="utf-8"
            )
            with mock.patch.object(importer_module, "SAMPLE_QUERIES", SAMPLE_QUERIES_OK):
                with self.assertRaises(ImporterError):
                    import_release(
                        content_commit="f" * 40, source_root=tree,
                        expected_days=7, logger=lambda msg: None,
                    )
            # active 版本不变、线上内容不受影响。
            release.refresh_from_db()
            self.assertEqual(release.status, ReleaseStatus.ACTIVE)
            failed = ContentRelease.objects.get(commit="f" * 40)
            self.assertEqual(failed.status, ReleaseStatus.FAILED)
            self.assertIn("code", failed.error_report)
            self.assertEqual(failed.day_count, 0)
            response = self.client.get("/tutorials/week-001/day-002/")
            self.assertContains(response, "E版课程2")

    def test_tc_b08_no_code_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._import(
                Path(tmp), "1" * 40, 7, title_prefix="G版课程", no_code_day=3
            )
            meta = (
                ContentDayVersion.objects
                .filter(day_id="day-003").values("metadata_json").first()
            )["metadata_json"]
            self.assertIsNone(meta["code_path"])
            self.assertIsNone(meta["source_zip"])
            self.assertFalse(meta["run_all"])
            # 页面无空资源按钮，且显示说明文案。
            response = self.client.get("/tutorials/week-001/day-003/")
            self.assertContains(response, "无需下载源码")
            self.assertNotContains(response, "下载源码 ZIP")

    def test_tc_b04_image_asset_served(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = self._import(Path(tmp), "2" * 40, 7, title_prefix="H版课程")
            response = self.client.get("/tutorials/week-001/day-001/")
            # 渲染后的正文引用公开资产 URL。
            url_part = f"/assets/public/releases/{release.commit}/tutorials/week-001/day-001/images/diagram.svg"
            self.assertContains(response, url_part)
            asset = self.client.get(url_part)
            self.assertEqual(asset.status_code, 200)
            self.assertEqual(asset.headers["Content-Type"], "image/svg+xml")
            content = b"".join(asset.streaming_content)
            self.assertTrue(content.startswith(b"<svg"))
            # 路径穿越被拒。
            bad = self.client.get(
                f"/assets/public/releases/{release.commit}/../../etc/passwd"
            )
            self.assertEqual(bad.status_code, 404)


def _meta(day: int, sha: str, **extra):
    base = {
        "day_id": f"day-{day:03d}", "day": day, "week": 1, "phase": 1,
        "type": "concept_lab", "key_output": False, "title": f"Day{day}",
        "objective": "目标", "time": {"learning_min": 30, "practice_min": 45},
        "prerequisites": "p", "deliverable": "d",
        "source_path": f"tutorials/week-001/day-{day:03d}/README.md",
        "code_path": None, "url": f"tutorials/week-001/day-{day:03d}/",
        "source_zip": None, "code_url": None, "outputs_url": None,
        "run_all": False, "skills": [], "content_sha": sha,
        "required_tasks": ["reading", "exercise", "experiment", "acceptance"],
    }
    base.update(extra)
    return base


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class FaultIsolationTests(TestCase):
    """TC-F08 / TC-F12：搜索失败与存储不可用的降级行为。"""

    @classmethod
    def setUpTestData(cls):
        from django.core.cache import cache

        cache.clear()
        cls.release = ContentRelease.objects.create(
            commit="3" * 40, config_version=1, status=ReleaseStatus.ACTIVE,
        )
        day, _ = ContentDay.objects.update_or_create(
            day_id="day-001", defaults={"day": 1, "week": 1, "phase": 1},
        )
        version = ContentDayVersion.objects.create(
            release=cls.release, day_ref=day, day_id="day-001",
            metadata_json=_meta(1, "a" * 64), rendered_html="<p>ok</p>",
            content_sha="a" * 64,
        )
        day.current_version = version
        day.save(update_fields=["current_version"])
        state = SiteState.get_solo()
        state.active_release = cls.release
        state.save()

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user("frank", password="pw-12345678")

    def test_tc_f12_cached_public_page_readable_without_db(self):
        """MySQL 不可用：已缓存匿名页面继续可读（§9.4）。"""
        warm = self.client.get("/")
        self.assertEqual(warm.status_code, 200)
        with mock.patch(
            "apps.content.views.get_active_release",
            side_effect=DatabaseError("mysql down"),
        ):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)  # 命中缓存，不查库。

    def test_tc_f12_maintenance_page_when_cache_miss(self):
        """MySQL 不可用且无缓存：返回维护页（503），且维护页不进入缓存。"""
        with mock.patch(
            "apps.content.views.get_active_release",
            side_effect=DatabaseError("mysql down"),
        ):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "服务暂时不可用", status_code=503)
        from django.core.cache import cache

        epoch = cache.get("site:page:epoch")
        self.assertIsNone(cache.get(f"page:home:{epoch}") if epoch else None)

    def test_tc_f12_write_returns_storage_unavailable(self):
        """MySQL 不可用：学习写入明确失败（不冒充成功）。"""
        self.client.login(username="frank", password="pw-12345678")
        with mock.patch(
            "apps.learning.api.update_progress",
            side_effect=DatabaseError("mysql down"),
        ):
            response = self.client.patch(
                "/api/v1/me/progress/day-001/update/",
                data='{"tasks": {"reading": "done"}}',
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "STORAGE_UNAVAILABLE")
        self.assertIn("未保存", response.json()["message"])

    def test_tc_f08_search_failure_explicit(self):
        """搜索服务异常：明示失败可重试，不伪装成无结果。"""
        with mock.patch(
            "apps.search.service.search", side_effect=DatabaseError("db down")
        ):
            page = self.client.get("/search/?q=MLIR")
            api = self.client.get("/api/v1/search/?q=MLIR")
        self.assertEqual(page.status_code, 503)
        self.assertContains(page, "搜索服务暂时不可用", status_code=503)
        self.assertEqual(api.status_code, 503)
        self.assertEqual(api.json()["code"], "SEARCH_UNAVAILABLE")

    def test_healthz_reports_db_unavailable(self):
        with mock.patch(
            "apps.content.views.get_active_release",
            side_effect=DatabaseError("mysql down"),
        ):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"db_unavailable", response.content)

    def test_sitemap_and_robots(self):
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(b"<loc>", sitemap.content)
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b"Sitemap:", robots.content)
        self.assertIn(b"Disallow: /api/", robots.content)

    def test_nav_aria_current(self):
        response = self.client.get("/search/?q=MLIR")
        self.assertContains(response, 'aria-current="page"')
