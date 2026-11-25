#!/usr/bin/env python3
"""tools/learning_metadata.py 单元测试（WP-01）。

覆盖：引用块解析、时间解析、类型推断、覆盖配置校验、内容哈希
确定性与隔离性、集合校验。使用临时目录构造最小日课树。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from learning_metadata import (  # noqa: E402
    LearningError,
    build_day_record,
    canonical_override_json,
    clean_quote_text,
    compute_content_sha,
    extract_labeled_quote,
    infer_day_type,
    load_day_overrides,
    parse_estimated_minutes,
    validate_day_collection,
)

SAMPLE_MARKDOWN = """# 第 001 天：示例日课

> **今日目标**：理解一个概念，完成一个实验。
> 第二行补充说明，保留换行。
> **预计时间**：学习 25 分钟 ＋ 实践 45 分钟
> **前置准备**：`python3` 与基本命令行；建议回忆 Day 1。
> **今日产出**：一份 `code/` 目录和真实运行记录。

## 1. 正文标题

内容……
"""


def make_day_dir(root, day=1, week=1, markdown=SAMPLE_MARKDOWN, with_code=True):
    day_dir = Path(root) / f"week-{week:03d}" / f"day-{day:03d}"
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "README.md").write_text(markdown, encoding="utf-8")
    if with_code:
        code = day_dir / "code"
        code.mkdir(exist_ok=True)
        (code / "run_all.sh").write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
        (code / "run_all.sh").chmod(0o755)
        (code / "main.py").write_text("print('hi')\n", encoding="utf-8")
        outputs = code / "outputs" / "result.txt"
        outputs.parent.mkdir(parents=True, exist_ok=True)
        outputs.write_text("frozen output\n", encoding="utf-8")
    images = day_dir / "images"
    images.mkdir(exist_ok=True)
    (images / "01.svg").write_text("<svg></svg>", encoding="utf-8")
    return day_dir


def make_tutorial(day_dir, day=1, week=1, title="第 001 天：示例日课"):
    text = (day_dir / "README.md").read_text(encoding="utf-8")
    return {
        "number": day,
        "week": week,
        "slug": day_dir.name,
        "title": title,
        "markdown": "\n".join(text.strip().splitlines()[1:]).strip(),
        "source": day_dir,
    }


class QuoteExtractionTest(unittest.TestCase):
    def test_normal_multiline(self):
        text, line = extract_labeled_quote(SAMPLE_MARKDOWN, "今日目标")
        self.assertEqual(line, 3)
        self.assertIn("第二行补充说明", text)

    def test_missing_label(self):
        with self.assertRaises(LearningError) as ctx:
            extract_labeled_quote("没有引用块的正文", "今日目标")
        self.assertIn("LEARNING_E101", str(ctx.exception))

    def test_duplicate_label(self):
        markdown = SAMPLE_MARKDOWN + "\n> **今日目标**：再来一次\n"
        with self.assertRaises(LearningError) as ctx:
            extract_labeled_quote(markdown, "今日目标")
        self.assertIn("LEARNING_E102", str(ctx.exception))

    def test_stops_at_next_label(self):
        text, _ = extract_labeled_quote(SAMPLE_MARKDOWN, "今日目标")
        self.assertNotIn("预计时间", text)
        time_text, _ = extract_labeled_quote(SAMPLE_MARKDOWN, "预计时间")
        self.assertIn("学习 25 分钟", time_text)

    def test_time_variants(self):
        for raw in (
            "学习 25 分钟＋实践 45 分钟",
            "学习 25 分钟 ＋ 实践 45 分钟",
            "学习 25 分钟 + 实践 45 分钟",
            "学习 25 分钟＋实践 45 分钟（选做另加 10 分钟）",
            "学习 30 分钟＋实践 30 分钟（首次构建约 10～20 分钟）。",
        ):
            parsed = parse_estimated_minutes(raw)
            self.assertIsNotNone(parsed, raw)
            self.assertGreater(parsed["learning_min"], 0)
            self.assertGreater(parsed["practice_min"], 0)
        self.assertIsNone(parse_estimated_minutes("学习二十五分钟"))
        self.assertIsNone(parse_estimated_minutes("学习 25 分钟；无实践"))


class TypeInferenceTest(unittest.TestCase):
    def test_ladder(self):
        self.assertEqual(infer_day_type(168, 6), "final_assessment")
        self.assertEqual(infer_day_type(7, 1), "review")
        self.assertEqual(infer_day_type(6, 1), "integration")
        self.assertEqual(infer_day_type(155, 6), "documentation")
        self.assertEqual(infer_day_type(29, 2), "concept_lab")


class CleanTextTest(unittest.TestCase):
    def test_cleanup(self):
        raw = "**粗体** 与 `code_cmd` 和 [链接](https://example.com)\n- 列表项"
        cleaned = clean_quote_text(raw)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertNotIn("[", cleaned)
        self.assertNotIn("- 列表", cleaned)
        self.assertIn("code_cmd", cleaned)
        self.assertIn("列表项", cleaned)


class OverridesTest(unittest.TestCase):
    def _write(self, data):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "day-overrides.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid(self):
        path = self._write({"schema_version": 1, "days": {"day-029": {"type": "environment_lab", "skills": ["MLIR"]}}})
        data = load_day_overrides(path, valid_day_ids={"day-029"})
        self.assertEqual(data["days"]["day-029"]["type"], "environment_lab")

    def test_unknown_field(self):
        path = self._write({"schema_version": 1, "days": {"day-029": {"bad": 1}}})
        with self.assertRaises(LearningError) as ctx:
            load_day_overrides(path, valid_day_ids={"day-029"})
        self.assertIn("LEARNING_E119", str(ctx.exception))

    def test_duplicate_json_key(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "o.json"
        path.write_text('{"schema_version": 1, "schema_version": 1, "days": {}}', encoding="utf-8")
        with self.assertRaises(LearningError) as ctx:
            load_day_overrides(path)
        self.assertIn("LEARNING_E110", str(ctx.exception))

    def test_unknown_day(self):
        path = self._write({"schema_version": 1, "days": {"day-999": {"type": "review"}}})
        with self.assertRaises(LearningError):
            load_day_overrides(path, valid_day_ids={"day-001"})

    def test_bad_skills(self):
        path = self._write({"schema_version": 1, "days": {"day-001": {"skills": ["a"] * 13}}})
        with self.assertRaises(LearningError):
            load_day_overrides(path, valid_day_ids={"day-001"})


class ContentShaTest(unittest.TestCase):
    def _tree(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name), make_day_dir(tmp.name)

    def test_deterministic(self):
        root, day_dir = self._tree()
        sha1 = compute_content_sha(day_dir, {})
        sha2 = compute_content_sha(day_dir, {})
        self.assertEqual(sha1, sha2)
        self.assertEqual(len(sha1), 64)

    def test_sensitivity(self):
        root, day_dir = self._tree()
        base = compute_content_sha(day_dir, {})
        (day_dir / "README.md").write_text(SAMPLE_MARKDOWN + "\n新增一行\n", encoding="utf-8")
        self.assertNotEqual(base, compute_content_sha(day_dir, {}))
        (day_dir / "code" / "main.py").write_text("print('changed')\n", encoding="utf-8")
        self.assertNotEqual(base, compute_content_sha(day_dir, {}))
        # 覆盖变化 → SHA 变化
        self.assertNotEqual(base, compute_content_sha(day_dir, {"type": "review"}))
        # 冻结输出变化 → SHA 变化
        (day_dir / "code" / "outputs" / "result.txt").write_text("changed\n", encoding="utf-8")
        self.assertNotEqual(base, compute_content_sha(day_dir, {}))

    def test_isolation(self):
        root, day_dir = self._tree()
        base = compute_content_sha(day_dir, {})
        other = make_day_dir(root, day=2, week=1)
        (other / "README.md").write_text("完全不同的内容", encoding="utf-8")
        self.assertEqual(base, compute_content_sha(day_dir, {}))
        # 噪音文件不参与哈希
        (day_dir / ".DS_Store").write_bytes(b"junk")
        self.assertEqual(base, compute_content_sha(day_dir, {}))

    def test_empty_vs_missing_override(self):
        root, day_dir = self._tree()
        self.assertEqual(compute_content_sha(day_dir, {}), compute_content_sha(day_dir, None))


class DayRecordTest(unittest.TestCase):
    def test_build_record(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        day_dir = make_day_dir(root)
        tutorial = make_tutorial(day_dir)
        record = build_day_record(
            tutorial,
            root,
            {},
            github_repo_url="https://github.com/x/y",
            content_commit="a" * 40,
            source_zip="downloads/day-001-source.zip",
        )
        self.assertEqual(record["day_id"], "day-001")
        self.assertEqual(record["type"], "concept_lab")
        self.assertFalse(record["key_output"])
        self.assertEqual(record["time"], {"learning_min": 25, "practice_min": 45})
        self.assertTrue(record["run_all"])
        self.assertEqual(record["required_tasks"], ["reading", "exercise", "experiment", "acceptance"])
        self.assertIn("tree/" + "a" * 40, record["code_url"])
        self.assertIsNotNone(record["outputs_url"])
        self.assertNotIn("第 001 天", record["title"])


class CollectionValidationTest(unittest.TestCase):
    def _days(self, count=3):
        days = []
        for i in range(1, count + 1):
            days.append(
                {
                    "day_id": f"day-{i:03d}",
                    "day": i,
                    "week": (i - 1) // 7 + 1,
                    "phase": (i - 1) // 28 + 1,
                    "type": "concept_lab",
                    "key_output": False,
                    "title": "t",
                    "objective": "o",
                    "time": {"learning_min": 1, "practice_min": 1},
                    "prerequisites": "p",
                    "deliverable": "d",
                    "source_path": f"tutorials/week-001/day-{i:03d}/README.md",
                    "code_path": None,
                    "url": f"tutorials/week-001/day-{i:03d}/",
                    "source_zip": None,
                    "code_url": None,
                    "outputs_url": None,
                    "run_all": False,
                    "skills": [],
                    "required_tasks": ["reading", "exercise", "experiment", "acceptance"],
                    "content_sha": "0" * 64,
                }
            )
        return days

    def test_count_mismatch(self):
        errors = validate_day_collection(self._days(3), "a" * 40)
        self.assertTrue(any("168" in str(e) for e in errors))

    def test_bad_commit(self):
        errors = validate_day_collection(self._days(2), "0" * 39)
        self.assertTrue(any("content_commit" in str(e) for e in errors))

    def test_bad_base_path(self):
        errors = validate_day_collection(self._days(2), "a" * 40, base_path="x/")
        self.assertTrue(any("base_path" in str(e) for e in errors))


if __name__ == "__main__":
    unittest.main()
