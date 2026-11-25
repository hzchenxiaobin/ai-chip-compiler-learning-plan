"""搜索服务测试：中文二元词、技术 token、过滤与稳定排序。"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.content.models import (
    ContentChunk,
    ContentDay,
    ContentDayVersion,
    ContentRelease,
    ReleaseStatus,
    SiteState,
)
from apps.search import service
from apps.search.models import SearchToken

META_A = {
    "day_id": "day-001", "day": 1, "week": 1, "phase": 1, "type": "environment_lab",
    "key_output": False, "title": "搭好 MLIR 工作台",
    "objective": "让 mlir-opt、FileCheck 和 JIT 都听指挥",
    "time": {"learning_min": 25, "practice_min": 45},
    "prerequisites": "p", "deliverable": "d",
    "source_path": "tutorials/week-001/day-001/README.md",
    "code_path": None, "url": "tutorials/week-001/day-001/",
    "source_zip": None, "code_url": None, "outputs_url": None,
    "run_all": True, "skills": ["MLIR", "JIT"], "content_sha": "a" * 64,
    "required_tasks": ["reading", "exercise", "experiment", "acceptance"],
    "code_paths": ["code/run_all.sh"], "error_tokens": [],
}
META_B = {
    **META_A, "day_id": "day-002", "day": 2, "type": "concept_lab",
    "title": "常量折叠与死代码消除",
    "objective": "理解常量折叠的语义与验证方法",
    "skills": ["Pass"],
    "url": "tutorials/week-001/day-002/", "code_paths": [],
}
CHUNKS_A = [
    {"chunk_id": "day-001:0001", "heading": "环境检查",
     "text": "运行 mlir-opt --version 与 FileCheck 校验工具链。"},
]
CHUNKS_B = [
    {"chunk_id": "day-002:0001", "heading": "概念",
     "text": "常量折叠会把 compile-time 已知的运算提前计算。"},
]


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class SearchServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.release = ContentRelease.objects.create(
            commit="d" * 40, config_version=1, status=ReleaseStatus.ACTIVE,
        )
        for meta, chunks in ((META_A, CHUNKS_A), (META_B, CHUNKS_B)):
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
            # 与生产导入器一致：meta 伪 chunk + 正文 chunk。
            meta_text = "\n".join(
                part for part in (
                    meta["title"], meta["objective"], meta["deliverable"],
                    " ".join(meta["skills"]),
                ) if part
            )
            chunk_rows = [ContentChunk(
                version=version, chunk_id=f"{meta['day_id']}:meta",
                day_id=meta["day_id"], heading="", anchor="", text=meta_text,
            )]
            for chunk in chunks:
                chunk_rows.append(ContentChunk(
                    version=version, chunk_id=chunk["chunk_id"],
                    day_id=meta["day_id"], heading=chunk["heading"],
                    anchor="", text=chunk["text"],
                ))
            ContentChunk.objects.bulk_create(chunk_rows)
            all_tokens = service.collect_day_tokens(meta, chunks)
            token_map = service.bulk_create_tokens(all_tokens)
            service.build_postings(version, meta, chunks, token_map)
        state = SiteState.get_solo()
        state.active_release = cls.release
        state.save()

    def test_ascii_token_hits(self):
        items, total, _ = service.search(self.release, "MLIR")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["day_id"], "day-001")

    def test_technical_token_exact(self):
        items, total, _ = service.search(self.release, "mlir-opt")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["day_id"], "day-001")
        # 技术项含精确加分。
        items2, _, _ = service.search(self.release, "run_all.sh")
        self.assertEqual(items2[0]["day_id"], "day-001")

    def test_cjk_bigram(self):
        items, total, _ = service.search(self.release, "常量折叠")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["day_id"], "day-002")
        self.assertIn("常量折叠", items[0]["snippet"])

    def test_filters(self):
        items, total, _ = service.search(self.release, "MLIR", day_type="concept_lab")
        self.assertEqual(total, 0)
        items, total, _ = service.search(
            self.release, "折叠", day_type="environment_lab")
        self.assertEqual(total, 0)
        items, total, _ = service.search(
            self.release, "mlir-opt", day_type="environment_lab")
        self.assertEqual(total, 1)

    def test_no_result(self):
        items, total, _ = service.search(self.release, "不存在的词组xyz")
        self.assertEqual(total, 0)

    def test_empty_query(self):
        items, total, _ = service.search(self.release, "")
        self.assertEqual(total, 0)

    def test_snippet_and_anchor(self):
        items, _, _ = service.search(self.release, "校验")
        self.assertTrue(items[0]["snippet"])
        # 「校验」只出现在正文 chunk（环境检查）。
        self.assertEqual(items[0]["heading"], "环境检查")

    def test_page_search_endpoint(self):
        from django.test import Client

        response = Client().get("/search/?q=MLIR")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "搭好 MLIR 工作台")

    def test_api_search_endpoint(self):
        from django.test import Client

        response = Client().get("/api/v1/search/?q=%E5%B8%B8%E9%87%8F%E6%8A%98%E5%8F%A0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_days"], 1)
        self.assertEqual(data["results"][0]["day_id"], "day-002")

    def test_tokens_created(self):
        self.assertGreaterEqual(SearchToken.objects.count(), 5)
