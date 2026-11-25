"""公开页面与账号流程测试。"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.content.models import (
    ContentDay,
    ContentDayVersion,
    ContentRelease,
    ReleaseStatus,
    SiteState,
)

META = {
    "day_id": "day-001", "day": 1, "week": 1, "phase": 1, "type": "concept_lab",
    "key_output": False, "title": "第一天测试课程",
    "objective": "理解编译与链接", "time": {"learning_min": 30, "practice_min": 45},
    "prerequisites": "Linux 环境", "deliverable": "空工程",
    "source_path": "tutorials/week-001/day-001/README.md",
    "code_path": None, "url": "tutorials/week-001/day-001/",
    "source_zip": None, "code_url": None, "outputs_url": None,
    "run_all": False, "skills": [], "content_sha": "e" * 64,
    "required_tasks": ["reading", "exercise", "experiment", "acceptance"],
}


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class ContentPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.release = ContentRelease.objects.create(
            commit="f" * 40, config_version=1, status=ReleaseStatus.ACTIVE,
            plan_markdown="# 计划\n\n## 第 1 周：第一周主题\n",
        )
        day, _ = ContentDay.objects.update_or_create(
            day_id="day-001", defaults={"day": 1, "week": 1, "phase": 1},
        )
        version = ContentDayVersion.objects.create(
            release=cls.release, day_ref=day, day_id="day-001",
            metadata_json=META, rendered_html="<h2 id=\"sect\">章节</h2><p>正文</p>",
            content_sha=META["content_sha"],
        )
        day.current_version = version
        day.save(update_fields=["current_version"])
        state = SiteState.get_solo()
        state.active_release = cls.release
        state.save()

    def test_home_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "第一天测试课程")

    def test_day_page_anonymous(self):
        response = self.client.get("/tutorials/week-001/day-001/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "理解编译与链接")
        self.assertContains(response, "可保存状态并跨设备继续")

    def test_day_page_logged_in_task_card(self):
        User.objects.create_user("dave", password="pw-12345678")
        self.client.login(username="dave", password="pw-12345678")
        response = self.client.get("/tutorials/week-001/day-001/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-learning=\"day-task\"")
        self.assertContains(response, "学习任务")
        self.assertEqual(response.headers.get("Cache-Control"), "private, no-store")

    def test_day_page_404(self):
        response = self.client.get("/tutorials/week-001/day-999/")
        self.assertEqual(response.status_code, 404)

    def test_week_page(self):
        response = self.client.get("/weeks/week-1/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Day 1：第一天测试课程")

    def test_phase_page(self):
        response = self.client.get("/phases/phase-1/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C++ 与编译器基础")

    def test_phase_page_invalid(self):
        response = self.client.get("/phases/phase-9/")
        self.assertEqual(response.status_code, 404)

    def test_plan_page(self):
        response = self.client.get("/plan/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "第一周主题")

    def test_anonymous_home_cached(self):
        from django.core.cache import cache

        self.client.get("/")
        epoch = cache.get("site:page:epoch")
        hit = cache.get(f"page:home:{epoch}") if epoch else None
        self.assertIsNotNone(hit)
        # 命中缓存：第二次请求不触发数据库（移除连接不可行，验证键存在即可）。
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_healthz(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ok", response.content)


class NoContentTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    @override_settings(CACHES={"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_503_when_no_release(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 503)


class AccountFlowTests(TestCase):
    def test_register_login_logout(self):
        response = self.client.post("/register/", {
            "username": "erin", "email": "erin@example.com",
            "password1": "pw-123456789", "password2": "pw-123456789",
        })
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="erin").exists())

        self.client.logout()
        response = self.client.post("/login/", {
            "username": "erin", "password": "pw-123456789", "next": "/",
        })
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_login_page_renders(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "登录")
