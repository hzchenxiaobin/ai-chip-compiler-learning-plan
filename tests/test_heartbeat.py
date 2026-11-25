"""阅读心跳（自动进度）测试。"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.content.models import (
    ContentDay,
    ContentDayVersion,
    ContentRelease,
    ReleaseStatus,
    SiteState,
)
from apps.learning.models import DayProgress, TaskProgress, TaskStatus
from apps.learning.services import record_reading_heartbeat

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


def _setup_release():
    release = ContentRelease.objects.create(
        commit="h" * 40, config_version=1, status=ReleaseStatus.ACTIVE,
    )
    day, _ = ContentDay.objects.update_or_create(
        day_id="day-001", defaults={"day": 1, "week": 1, "phase": 1},
    )
    version = ContentDayVersion.objects.create(
        release=release, day_ref=day, day_id="day-001",
        metadata_json=META, rendered_html="<p>x</p>", content_sha=META["content_sha"],
    )
    day.current_version = version
    day.save(update_fields=["current_version"])
    state = SiteState.get_solo()
    state.active_release = release
    state.save()
    return release


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class HeartbeatServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _setup_release()

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user("irene", password="pw-12345678")

    def test_creates_progress_and_auto_in_progress(self):
        result = record_reading_heartbeat(
            self.user, META, scroll_ratio=0.3, elapsed_seconds=15
        )
        self.assertEqual(result["reading_status"], "in_progress")
        self.assertFalse(result["auto_completed"])
        self.assertEqual(result["reading_seconds"], 15)
        self.assertTrue(TaskProgress.objects.filter(
            user=self.user, day_id="day-001", task_id="reading",
            status="in_progress"
        ).exists())
        # 状态变化 → revision +1。
        self.assertEqual(result["revision"], 1)

    def test_position_update_does_not_bump_revision(self):
        record_reading_heartbeat(self.user, META, scroll_ratio=0.3, elapsed_seconds=15)
        result = record_reading_heartbeat(
            self.user, META, scroll_ratio=0.5, elapsed_seconds=15
        )
        # 纯位置/时长更新：revision 不变。
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["reading_seconds"], 30)
        self.assertEqual(result["reading_position"], 0.5)

    def test_elapsed_capped_at_60(self):
        record_reading_heartbeat(
            self.user, META, scroll_ratio=0.1, elapsed_seconds=9999
        )
        progress = DayProgress.objects.get(user=self.user, day_id="day-001")
        self.assertEqual(progress.reading_seconds, 60)

    def test_auto_done_when_threshold_and_bottom(self):
        with override_settings(
            AUTO_COMPLETE_READING=True,
            READING_DONE_MIN_SECONDS=180,
            READING_DONE_SCROLL_RATIO=0.95,
        ):
            for _ in range(6):  # 6 × 30s = 180s。
                result = record_reading_heartbeat(
                    self.user, META, scroll_ratio=0.4, elapsed_seconds=30
                )
            self.assertFalse(result["auto_completed"])  # 未到页底。
            result = record_reading_heartbeat(
                self.user, META, scroll_ratio=0.97, elapsed_seconds=30
            )
            self.assertTrue(result["auto_completed"])
            self.assertEqual(result["reading_status"], "done")
        self.assertTrue(TaskProgress.objects.filter(
            user=self.user, day_id="day-001", task_id="reading", status="done"
        ).exists())

    def test_auto_done_disabled_by_setting(self):
        with override_settings(
            AUTO_COMPLETE_READING=False,
            READING_DONE_MIN_SECONDS=30,
        ):
            record_reading_heartbeat(self.user, META, scroll_ratio=0.2, elapsed_seconds=30)
            result = record_reading_heartbeat(
                self.user, META, scroll_ratio=1.0, elapsed_seconds=30
            )
            self.assertFalse(result["auto_completed"])
            self.assertEqual(result["reading_status"], "in_progress")

    def test_heartbeat_never_overrides_manual_states(self):
        # 人工标记 blocked 后，心跳不得推进。
        TaskProgress.objects.create(
            user=self.user, day_id="day-001", task_id="reading", status="blocked"
        )
        DayProgress.objects.create(user=self.user, day_id="day-001", revision=5)
        with override_settings(READING_DONE_MIN_SECONDS=30):
            result = record_reading_heartbeat(
                self.user, META, scroll_ratio=1.0, elapsed_seconds=30
            )
        self.assertFalse(result["auto_completed"])
        self.assertEqual(result["reading_status"], "blocked")
        task = TaskProgress.objects.get(
            user=self.user, day_id="day-001", task_id="reading"
        )
        self.assertEqual(task.status, "blocked")
        # revision 未被心跳改动。
        self.assertEqual(result["revision"], 5)

    def test_representation_includes_reading_fields(self):
        record_reading_heartbeat(
            self.user, META, scroll_ratio=0.66, elapsed_seconds=42
        )
        from apps.learning.services import day_representation

        release = SiteState.get_active_release()
        data = day_representation(self.user, release, META)
        self.assertEqual(data["reading_seconds"], 42)
        self.assertAlmostEqual(data["reading_position"], 0.66, places=2)


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class HeartbeatApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _setup_release()

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user("john", password="pw-12345678")
        self.client.login(username="john", password="pw-12345678")

    def _beat(self, scroll, elapsed, form=False):
        if form:
            return self.client.post(
                "/api/v1/me/progress/day-001/heartbeat/",
                data={"scroll_ratio": str(scroll), "elapsed_seconds": str(elapsed)},
            )
        import json

        return self.client.post(
            "/api/v1/me/progress/day-001/heartbeat/",
            data=json.dumps({"scroll_ratio": scroll, "elapsed_seconds": elapsed}),
            content_type="application/json",
        )

    def test_json_heartbeat_flow(self):
        response = self._beat(0.4, 30)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reading_status"], "in_progress")
        self.assertEqual(data["reading_seconds"], 30)

    def test_form_encoded_beacon_flow(self):
        # sendBeacon 走 form-encoded（含 csrfmiddlewaretoken 时由中间件校验，
        # 测试客户端已带会话 CSRF）。
        response = self._beat(0.4, 30, form=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reading_seconds"], 30)

    def test_invalid_body(self):
        response = self.client.post(
            "/api/v1/me/progress/day-001/heartbeat/",
            data='{"scroll_ratio": "abc"}', content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "BODY_INVALID")

    def test_unknown_day_404(self):
        response = self.client.post(
            "/api/v1/me/progress/day-999/heartbeat/",
            data='{"scroll_ratio": 0.5, "elapsed_seconds": 10}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_anonymous_401(self):
        client = self.client_class()
        response = client.post(
            "/api/v1/me/progress/day-001/heartbeat/",
            data='{"scroll_ratio": 0.5, "elapsed_seconds": 10}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
