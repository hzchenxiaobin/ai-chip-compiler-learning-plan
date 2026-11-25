"""导出/导入/替换/删除测试。"""
import json
import tempfile
from pathlib import Path

from django.conf import settings as dj_settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.content.models import (
    ContentDay,
    ContentDayVersion,
    ContentRelease,
    ReleaseStatus,
    SiteState,
)
from apps.learning import transfer
from apps.learning.models import DayProgress, LearningDataJob, LearningPlan, TaskProgress
from apps.learning.services import update_progress

PRIVATE_ROOT = Path(tempfile.mkdtemp(prefix="transfer-test-"))


def _now_iso():
    return timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")


META = {
    "day_id": "day-001", "day": 1, "week": 1, "phase": 1, "type": "concept_lab",
    "key_output": False, "title": "Day One", "objective": "o",
    "time": {"learning_min": 30, "practice_min": 45},
    "prerequisites": "p", "deliverable": "d",
    "source_path": "tutorials/week-001/day-001/README.md",
    "code_path": None, "url": "tutorials/week-001/day-001/",
    "source_zip": None, "code_url": None, "outputs_url": None,
    "run_all": False, "skills": [], "content_sha": "a" * 64,
    "required_tasks": ["reading", "exercise", "experiment", "acceptance"],
}
META_2 = {**META, "day_id": "day-002", "day": 2, "url": "tutorials/week-001/day-002/"}


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    PRIVATE_ASSET_ROOT=PRIVATE_ROOT,
)
class TransferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.release = ContentRelease.objects.create(
            commit="c" * 40, config_version=1, status=ReleaseStatus.ACTIVE,
        )
        for meta in (META, META_2):
            day, _ = ContentDay.objects.update_or_create(
                day_id=meta["day_id"],
                defaults={"day": meta["day"], "week": 1, "phase": 1},
            )
            version = ContentDayVersion.objects.create(
                release=cls.release, day_ref=day, day_id=meta["day_id"],
                metadata_json=meta, rendered_html="<p>x</p>",
                content_sha=meta["content_sha"],
            )
            day.current_version = version
            day.save(update_fields=["current_version"])
        state = SiteState.get_solo()
        state.active_release = cls.release
        state.save()

    def setUp(self):
        self.user = User.objects.create_user("carol", password="pw-12345678")

    # ------------------------------------------------------------- 导出

    def test_export_payload_shape(self):
        update_progress(self.user, self.release, META,
                        tasks={"reading": "done"}, acknowledge=False,
                        if_match=None, if_none_match="*")
        payload = transfer.build_export_payload(self.user, self.release)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["kind"], transfer.EXPORT_KIND)
        self.assertEqual(payload["content_commit"], self.release.commit)
        self.assertEqual(len(payload["days"]), 1)
        day = payload["days"][0]
        self.assertEqual(day["day_id"], "day-001")
        self.assertEqual(day["tasks"]["reading"]["status"], "done")
        self.assertIn("revision", day)

    def test_export_job_creates_private_file(self):
        job = transfer.create_export_job(self.user, self.release)
        path = Path(dj_settings.PRIVATE_ASSET_ROOT) / job.private_file
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["kind"], transfer.EXPORT_KIND)

    # ------------------------------------------------------------- 预检

    def _payload(self, days, **extra):
        base = {
            "schema_version": 1, "kind": transfer.EXPORT_KIND,
            "exported_at": _now_iso(), "content_commit": self.release.commit,
            "plan": {"current_day_id": None, "revision": 0},
            "days": days,
        }
        base.update(extra)
        return base

    def _day(self, day_id="day-002", tasks=None, revision=1, **extra):
        record = {
            "day_id": day_id, "content_sha": "a" * 64, "revision": revision,
            "tasks": {
                "reading": {"status": "not_started", "updated_at": None},
                "exercise": {"status": "not_started", "updated_at": None},
                "experiment": {"status": "not_started", "updated_at": None},
                "acceptance": {"status": "not_started", "updated_at": None},
            },
            "last_visited_at": None, "needs_review": False,
        }
        for task_id, status in (tasks or {}).items():
            record["tasks"][task_id] = {"status": status, "updated_at": None}
        record.update(extra)
        return record

    def test_precheck_classifies(self):
        update_progress(self.user, self.release, META,
                        tasks={"reading": "done"}, acknowledge=False,
                        if_match=None, if_none_match="*")
        # 同内容 → 未变化。
        report, _, _ = transfer.precheck(
            self.user, self.release,
            self._payload([self._day("day-001", tasks={"reading": "done"})]),
        )
        self.assertEqual(report["counts"]["unchanged"], 1)

        # 内容不同 → 冲突（无论 revision）。
        report, _, _ = transfer.precheck(
            self.user, self.release,
            self._payload([self._day("day-001", tasks={"reading": "blocked"}, revision=99)]),
        )
        self.assertEqual(report["counts"]["conflict"], 1)

        # 本机无记录 → 新增。
        report, _, _ = transfer.precheck(
            self.user, self.release, self._payload([self._day("day-002")])
        )
        self.assertEqual(report["counts"]["add"], 1)

    def test_precheck_unknown_day_skipped(self):
        report, _, _ = transfer.precheck(
            self.user, self.release, self._payload([self._day("day-500")])
        )
        self.assertEqual(report["counts"]["skip"], 1)
        self.assertIn("day-500", report["skipped_unknown"])

    def test_precheck_duplicate_day_rejected(self):
        with self.assertRaises(transfer.TransferError) as ctx:
            transfer.precheck(
                self.user, self.release,
                self._payload([self._day("day-001"), self._day("day-001")]),
            )
        self.assertEqual(ctx.exception.code, "DAY_DUPLICATE")

    def test_precheck_unknown_field_rejected(self):
        record = self._day("day-001", hack="x")
        with self.assertRaises(transfer.TransferError) as ctx:
            transfer.precheck(self.user, self.release, self._payload([record]))
        self.assertEqual(ctx.exception.code, "FIELD_UNKNOWN")

    def test_precheck_future_version_rejected(self):
        payload = self._payload([self._day("day-001")], schema_version=2)
        with self.assertRaises(transfer.TransferError) as ctx:
            transfer.precheck(self.user, self.release, payload)
        self.assertEqual(ctx.exception.code, "VERSION_UNSUPPORTED")

    def test_parse_bytes_rejects_duplicate_keys(self):
        with self.assertRaises(transfer.TransferError):
            transfer.parse_import_bytes(b'{"a": 1, "a": 2}')

    def test_parse_bytes_rejects_bom_and_bad_utf8(self):
        with self.assertRaises(transfer.TransferError):
            transfer.parse_import_bytes(b"\xef\xbb\xbf{}")
        with self.assertRaises(transfer.TransferError):
            transfer.parse_import_bytes(b"\xff\xfe{}")

    def test_parse_bytes_rejects_oversize(self):
        with override_settings(IMPORT_MAX_FILE_BYTES=10):
            with self.assertRaises(transfer.TransferError):
                transfer.parse_import_bytes(b"x" * 100)

    # ------------------------------------------------------------- 应用

    def _import_job(self, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return transfer.create_import_job(self.user, self.release, raw)

    def test_apply_merge_adds(self):
        job = self._import_job(
            self._payload([self._day("day-002", tasks={"reading": "done"})])
        )
        self.assertEqual(job.status, "precheck_ok")
        result = transfer.apply_import(
            self.user, self.release, job, mode="merge", resolutions={}
        )
        self.assertEqual(result["added"], 1)
        self.assertTrue(TaskProgress.objects.filter(
            user=self.user, day_id="day-002", task_id="reading", status="done"
        ).exists())

    def test_apply_merge_conflict_requires_resolution(self):
        update_progress(self.user, self.release, META,
                        tasks={"reading": "done"}, acknowledge=False,
                        if_match=None, if_none_match="*")
        job = self._import_job(
            self._payload([self._day("day-001", tasks={"reading": "blocked"})])
        )
        with self.assertRaises(transfer.TransferError) as ctx:
            transfer.apply_import(
                self.user, self.release, job, mode="merge", resolutions={}
            )
        self.assertEqual(ctx.exception.code, "CONFLICTS_UNRESOLVED")

        result = transfer.apply_import(
            self.user, self.release, job, mode="merge",
            resolutions={"day-001": "incoming"},
        )
        self.assertEqual(result["conflict_incoming"], 1)
        self.assertTrue(TaskProgress.objects.filter(
            user=self.user, day_id="day-001", task_id="reading", status="blocked"
        ).exists())

    def test_apply_replace_snapshots_and_replaces(self):
        update_progress(self.user, self.release, META,
                        tasks={"reading": "done"}, acknowledge=False,
                        if_match=None, if_none_match="*")
        LearningPlan.objects.create(user=self.user, current_day_id="day-001", revision=1)
        job = self._import_job(
            self._payload([self._day("day-002", tasks={"reading": "done"})])
        )
        result = transfer.apply_import(
            self.user, self.release, job, mode="replace", resolutions={}
        )
        self.assertEqual(result["added"], 1)
        # day-001 被替换删除。
        self.assertFalse(DayProgress.objects.filter(
            user=self.user, day_id="day-001"
        ).exists())
        self.assertTrue(DayProgress.objects.filter(
            user=self.user, day_id="day-002"
        ).exists())
        # 快照可恢复：包含替换前的 day-001。
        snapshot_id = job.report_json.get("snapshot_job_id")
        self.assertIsNotNone(snapshot_id)
        snapshot_job = LearningDataJob.objects.get(pk=snapshot_id)
        snapshot_path = Path(dj_settings.PRIVATE_ASSET_ROOT) / snapshot_job.private_file
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertIn("day-001", [d["day_id"] for d in data["days"]])
        # 计划被替换为导入的（无 plan → null）。
        plan = LearningPlan.objects.filter(user=self.user).first()
        self.assertIsNone(plan.current_day_id)

    def test_delete_learning_data(self):
        update_progress(self.user, self.release, META,
                        tasks={"reading": "done"}, acknowledge=False,
                        if_match=None, if_none_match="*")
        LearningPlan.objects.create(user=self.user, current_day_id="day-001")
        deleted = transfer.delete_learning_data(self.user)
        self.assertEqual(deleted, 1)
        self.assertFalse(DayProgress.objects.filter(user=self.user).exists())
        self.assertFalse(LearningPlan.objects.filter(user=self.user).exists())

    def test_download_token_flow(self):
        job = transfer.create_export_job(self.user, self.release)
        token = transfer.make_download_token(job.pk, ttl=60)
        self.assertTrue(transfer.verify_download_token(job.pk, token))
        self.assertFalse(transfer.verify_download_token(job.pk, "123:deadbeef"))
        expired = transfer.make_download_token(job.pk, ttl=-10)
        self.assertFalse(transfer.verify_download_token(job.pk, expired))
