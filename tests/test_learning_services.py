"""学习状态机与服务测试（需要数据库）。"""
from django.contrib.auth.models import User
from django.test import TestCase

from apps.content.importer.parsing import TYPE_TASKS
from apps.learning import services
from apps.learning.models import DayProgress, LearningPlan, TaskProgress

META = {
    "day_id": "day-001", "day": 1, "week": 1, "phase": 1,
    "type": "concept_lab", "title": "测试日课",
    "required_tasks": ["reading", "exercise", "experiment", "acceptance"],
    "content_sha": "a" * 64,
}
META_REVIEW = {
    **META, "day_id": "day-007", "day": 7, "type": "review",
    "required_tasks": ["reading", "exercise", "acceptance"],
    "content_sha": "b" * 64,
}


class StateMachineTests(TestCase):
    def test_all_not_started(self):
        tasks = {"reading": "not_started", "exercise": "not_started",
                 "experiment": "not_started", "acceptance": "not_started"}
        self.assertEqual(
            services.derive_day_state(META["required_tasks"], tasks), "not_started"
        )

    def test_blocked_priority(self):
        tasks = {"reading": "done", "exercise": "done",
                 "experiment": "blocked", "acceptance": "done"}
        self.assertEqual(
            services.derive_day_state(META["required_tasks"], tasks), "blocked"
        )

    def test_completed(self):
        tasks = {k: "done" for k in META["required_tasks"]}
        self.assertEqual(
            services.derive_day_state(META["required_tasks"], tasks), "completed"
        )

    def test_ready_for_review(self):
        tasks = {"reading": "done", "exercise": "done",
                 "experiment": "done", "acceptance": "not_started"}
        self.assertEqual(
            services.derive_day_state(META["required_tasks"], tasks), "ready_for_review"
        )

    def test_acceptance_done_but_exercise_not_is_in_progress(self):
        tasks = {"reading": "done", "exercise": "in_progress",
                 "experiment": "done", "acceptance": "done"}
        self.assertEqual(
            services.derive_day_state(META["required_tasks"], tasks), "in_progress"
        )

    def test_review_day_requires_own_tasks(self):
        tasks = {"reading": "done", "exercise": "not_started", "acceptance": "done"}
        self.assertEqual(
            services.derive_day_state(META_REVIEW["required_tasks"], tasks), "in_progress"
        )


class ProgressServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.content.models import (
            ContentDay, ContentDayVersion, ContentRelease, ReleaseStatus,
        )

        cls.release = ContentRelease.objects.create(
            commit="9" * 40, config_version=1, status=ReleaseStatus.ACTIVE,
        )
        for day in range(1, 4):
            day_obj, _ = ContentDay.objects.update_or_create(
                day_id=f"day-{day:03d}",
                defaults={"day": day, "week": 1, "phase": 1},
            )
            ContentDayVersion.objects.create(
                release=cls.release, day_ref=day_obj,
                day_id=f"day-{day:03d}",
                metadata_json={"day_id": f"day-{day:03d}"},
                rendered_html="<p>x</p>", content_sha=f"{day:064d}",
            )

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw-12345678")

    def test_update_creates_and_increments(self):
        result = services.update_progress(
            self.user, None, META,
            tasks={"reading": "done"}, acknowledge=False,
            if_match=None, if_none_match="*",
        )
        self.assertEqual(result["revision"], 2)
        self.assertTrue(TaskProgress.objects.filter(
            user=self.user, day_id="day-001", task_id="reading", status="done"
        ).exists())

    def test_update_with_stale_if_match_fails(self):
        services.update_progress(
            self.user, None, META, tasks={"reading": "done"},
            acknowledge=False, if_match=None, if_none_match="*",
        )
        with self.assertRaises(services.PreconditionFailed) as ctx:
            services.update_progress(
                self.user, None, META, tasks={"reading": "in_progress"},
                acknowledge=False, if_match="1", if_none_match=None,
            )
        self.assertIsNotNone(ctx.exception.current)

    def test_update_existing_without_if_match_fails(self):
        services.update_progress(
            self.user, None, META, tasks={"reading": "done"},
            acknowledge=False, if_match=None, if_none_match="*",
        )
        with self.assertRaises(services.PreconditionFailed):
            services.update_progress(
                self.user, None, META, tasks={"reading": "in_progress"},
                acknowledge=False, if_match=None, if_none_match=None,
            )

    def test_not_applicable_task_rejected(self):
        with self.assertRaises(services.ValidationError):
            services.update_progress(
                self.user, None, META_REVIEW,
                tasks={"experiment": "done"},  # review 日不要求 experiment。
                acknowledge=False, if_match=None, if_none_match="*",
            )

    def test_not_applicable_status_rejected(self):
        with self.assertRaises(services.ValidationError):
            services.update_progress(
                self.user, None, META,
                tasks={"reading": "not_applicable"},
                acknowledge=False, if_match=None, if_none_match="*",
            )

    def test_acknowledge_updates_sha_only(self):
        # 先用旧 SHA 建立记录（模拟内容更新前的学习）。
        DayProgress.objects.create(
            user=self.user, day_id="day-001",
            ack_content_sha="0" * 64, revision=1,
        )
        TaskProgress.objects.create(
            user=self.user, day_id="day-001", task_id="reading", status="done",
        )
        result = services.update_progress(
            self.user, None, META, tasks=None, acknowledge=True,
            if_match="1", if_none_match=None,
        )
        self.assertFalse(result["needs_review"])
        progress = DayProgress.objects.get(user=self.user, day_id="day-001")
        self.assertEqual(progress.ack_content_sha, META["content_sha"])
        # 复核不改变任务状态。
        task = TaskProgress.objects.get(
            user=self.user, day_id="day-001", task_id="reading"
        )
        self.assertEqual(task.status, "done")

    def test_set_plan_explicit(self):
        result = services.set_plan(self.user, self.release, "day-003", None)
        self.assertEqual(result["current_day_id"], "day-003")
        plan = LearningPlan.objects.get(user=self.user)
        self.assertEqual(plan.current_day_id, "day-003")

    def test_set_plan_unknown_day_rejected(self):
        with self.assertRaises(services.ValidationError):
            services.set_plan(self.user, self.release, "day-999", None)

    def test_continue_target_prefers_plan(self):
        metas = [META, {**META, "day_id": "day-002", "day": 2}]
        services.set_plan(self.user, self.release, "day-002", None)
        target = services.get_continue_target(self.user, None, metas)
        self.assertEqual(target["day_id"], "day-002")
        self.assertEqual(target["reason"], "plan")

    def test_continue_target_first_day_when_fresh(self):
        target = services.get_continue_target(self.user, None, [META])
        self.assertEqual(target["day_id"], "day-001")
        self.assertEqual(target["reason"], "first")

    def test_continue_target_recent_activity(self):
        services.update_progress(
            self.user, None, META, tasks={"exercise": "in_progress"},
            acknowledge=False, if_match=None, if_none_match="*",
        )
        metas = [META, {**META, "day_id": "day-002", "day": 2}]
        target = services.get_continue_target(self.user, None, metas)
        self.assertEqual(target["reason"], "recent")

    def test_touch_visit_throttled(self):
        services.touch_visit(self.user, META)
        first = DayProgress.objects.get(user=self.user, day_id="day-001")
        services.touch_visit(self.user, META)
        second = DayProgress.objects.get(user=self.user, day_id="day-001")
        self.assertEqual(first.last_visited_at, second.last_visited_at)

    def _week_metas(self):
        metas = []
        for day in range(1, 8):
            day_type = "review" if day % 7 == 0 else (
                "integration" if day % 7 == 6 else "concept_lab")
            metas.append({
                "day_id": f"day-{day:03d}", "day": day, "week": 1, "phase": 1,
                "type": day_type, "title": f"日 {day}",
                "required_tasks": list(TYPE_TASKS[day_type]),
                "key_output": day_type in ("integration", "review"),
                "content_sha": f"{day:064d}",
            })
        return metas

    def test_week_view_only_reading_not_completed(self):
        metas = self._week_metas()
        # 只完成阅读。
        for meta in metas:
            services.update_progress(
                self.user, None, meta, tasks={"reading": "done"},
                acknowledge=False, if_match=None, if_none_match="*",
            )
        week_view = services.get_week_view_model(self.user, metas)
        self.assertNotEqual(week_view["week_state"], "completed")
        self.assertIn(week_view["week_state"], ("in_progress", "not_started"))

    def test_week_view_completed_when_key_items_done(self):
        metas = self._week_metas()
        for meta in metas:
            tasks = {task_id: "done" for task_id in meta["required_tasks"]}
            services.update_progress(
                self.user, None, meta, tasks=tasks,
                acknowledge=False, if_match=None, if_none_match="*",
            )
        week_view = services.get_week_view_model(self.user, metas)
        self.assertEqual(week_view["week_state"], "completed")

    def test_week_view_blocked(self):
        metas = self._week_metas()
        # 周状态由关键产出（Day 6 集成 / Day 7 复盘）派生：阻塞关键项 → blocked。
        meta = metas[5]  # day-006 integration（key_output）
        services.update_progress(
            self.user, None, meta, tasks={"experiment": "blocked"},
            acknowledge=False, if_match=None, if_none_match="*",
        )
        week_view = services.get_week_view_model(self.user, metas)
        self.assertEqual(week_view["week_state"], "blocked")

    def test_phase_view_states(self):
        metas = []
        for day in range(1, 29):
            day_type = "review" if day % 7 == 0 else (
                "integration" if day % 7 == 6 else "concept_lab")
            metas.append({
                "day_id": f"day-{day:03d}", "day": day,
                "week": (day - 1) // 7 + 1, "phase": 1,
                "type": day_type, "title": f"日 {day}",
                "required_tasks": list(TYPE_TASKS[day_type]),
                "key_output": day_type in ("integration", "review"),
                "content_sha": f"{day:064d}",
            })
        view = services.get_phase_view_model(self.user, metas)
        self.assertEqual(view["phase_state"], "not_started")
        self.assertEqual(len(view["weeks"]), 4)
