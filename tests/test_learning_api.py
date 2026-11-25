"""学习 API 测试：权限、If-Match/412、计划、跨用户边界。"""
import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.content.models import (
    ContentDay,
    ContentDayVersion,
    ContentRelease,
    ReleaseStatus,
    SiteState,
)

META_1 = {
    "day_id": "day-001", "day": 1, "week": 1, "phase": 1, "type": "concept_lab",
    "key_output": False, "title": "Day One",
    "objective": "目标", "time": {"learning_min": 30, "practice_min": 45},
    "prerequisites": "准备", "deliverable": "产出",
    "source_path": "tutorials/week-001/day-001/README.md",
    "code_path": None, "url": "tutorials/week-001/day-001/",
    "source_zip": None, "code_url": None, "outputs_url": None,
    "run_all": False, "skills": [], "content_sha": "a" * 64,
    "required_tasks": ["reading", "exercise", "experiment", "acceptance"],
}


def _make_release():
    release = ContentRelease.objects.create(
        commit="b" * 40, config_version=1, status=ReleaseStatus.ACTIVE,
    )
    for meta in (META_1,):
        day, _ = ContentDay.objects.update_or_create(
            day_id=meta["day_id"],
            defaults={"day": meta["day"], "week": meta["week"], "phase": meta["phase"]},
        )
        version = ContentDayVersion.objects.create(
            release=release, day_ref=day, day_id=meta["day_id"],
            metadata_json=meta, rendered_html="<p>ok</p>",
            content_sha=meta["content_sha"],
        )
        day.current_version = version
        day.save(update_fields=["current_version"])
    state = SiteState.get_solo()
    state.active_release = release
    state.save()
    return release


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class ProgressApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw-12345678")
        self.other = User.objects.create_user("bob", password="pw-12345678")
        _make_release()
        self.client.login(username="alice", password="pw-12345678")

    def _patch(self, payload, headers=None):
        return self.client.patch(
            "/api/v1/me/progress/day-001/update/",
            data=json.dumps(payload), content_type="application/json",
            **(headers or {}),
        )

    def test_anonymous_gets_401(self):
        client = self.client_class()
        response = client.get("/api/v1/me/dashboard/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "NOT_AUTHENTICATED")

    def test_progress_patch_creates(self):
        response = self._patch({"tasks": {"reading": "done"}})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["revision"], 2)
        self.assertEqual(data["tasks"]["reading"]["status"], "done")
        self.assertIn("ETag", response)

    def test_progress_patch_412_on_stale(self):
        self._patch({"tasks": {"reading": "done"}})
        response = self._patch(
            {"tasks": {"reading": "in_progress"}}, headers={"HTTP_IF_MATCH": '"1"'}
        )
        self.assertEqual(response.status_code, 412)
        body = response.json()
        self.assertEqual(body["code"], "PRECONDITION_FAILED")
        self.assertIsNotNone(body["current"])

    def test_progress_patch_requires_if_match_when_exists(self):
        self._patch({"tasks": {"reading": "done"}})
        response = self._patch({"tasks": {"reading": "in_progress"}})
        self.assertEqual(response.status_code, 412)

    def test_invalid_status_rejected(self):
        response = self._patch({"tasks": {"reading": "finished"}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "TASK_STATUS_INVALID")

    def test_cross_user_progress_still_own(self):
        # bob 无法读取 alice 的记录：各自独立，bob GET 得到自己的空记录。
        self.client.logout()
        self.client.login(username="bob", password="pw-12345678")
        response = self.client.get("/api/v1/me/progress/day-001/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], 0)

    def test_unknown_day_404(self):
        response = self._patch({"tasks": {"reading": "done"}})
        response = self.client.get("/api/v1/me/progress/day-999/")
        self.assertEqual(response.status_code, 404)

    def test_plan_flow(self):
        response = self.client.put(
            "/api/v1/me/plan/",
            data=json.dumps({"current_day_id": "day-001"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["current_day_id"], "day-001")
        response = self.client.put(
            "/api/v1/me/plan/",
            data=json.dumps({"current_day_id": "day-999"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_dashboard_shape(self):
        self.client.put(
            "/api/v1/me/plan/",
            data=json.dumps({"current_day_id": "day-001"}),
            content_type="application/json",
        )
        response = self.client.get("/api/v1/me/dashboard/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["continue_target"]["day_id"], "day-001")
        self.assertIn("counts", data)

    def test_days_api_public(self):
        response = self.client.get("/api/v1/days/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["days"]), 1)

    def test_days_api_requires_release(self):
        state = SiteState.get_solo()
        state.active_release = None
        state.save()
        response = self.client.get("/api/v1/days/")
        self.assertEqual(response.status_code, 503)
