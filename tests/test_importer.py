"""导入器单元测试：解析、覆盖、哈希、分片、ZIP。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.content.importer import chunking, content_hash, overrides, parsing, zip_builder
from apps.content.importer.errors import ImporterError

from . import helpers


class ParsingTests(SimpleTestCase):
    def _write(self, tmp, text, day=1):
        day_dir = tmp / "tutorials" / "week-001" / f"day-{day:03d}"
        day_dir.mkdir(parents=True)
        path = day_dir / "README.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_parse_normal(self):
        with TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), helpers.day_readme(1, "标题甲"))
            doc = parsing.parse_readme(path)
            self.assertEqual(doc.day, 1)
            self.assertEqual(doc.week, 1)
            self.assertEqual(doc.day_id, "day-001")
            self.assertEqual(doc.title, "标题甲")
            self.assertEqual(doc.objective, "完成第 1 天的核心练习")
            self.assertEqual(doc.time, {"learning_min": 30, "practice_min": 45})

    def test_fullwidth_time_and_colon(self):
        text = (
            "# 第 3 天：标题\n\n"
            "> **今日目标**：目标\n"
            "> **预计时间**：学习 25 分钟；实践 40 分钟\n"
            "> **前置准备**：准备\n"
            "> **今日产出**：产出\n"
        )
        with TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), text, day=3)
            doc = parsing.parse_readme(path)
            self.assertEqual(doc.time, {"learning_min": 25, "practice_min": 40})

    def test_missing_label_reports_line(self):
        text = (
            "# 第 2 天：标题\n\n"
            "> **今日目标**：目标\n"
            "> **预计时间**：学习 25 分钟 + 实践 40 分钟\n"
        )
        with TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), text, day=2)
            with self.assertRaises(ImporterError) as ctx:
                parsing.parse_readme(path)
            self.assertIn("前置准备", str(ctx.exception))

    def test_duplicate_label(self):
        text = (
            "# 第 2 天：标题\n\n"
            "> **今日目标**：目标一\n"
            "> **预计时间**：学习 25 分钟 + 实践 40 分钟\n"
            "> **今日目标**：目标二\n"
            "> **前置准备**：准备\n"
            "> **今日产出**：产出\n"
        )
        with TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), text, day=2)
            with self.assertRaises(ImporterError) as ctx:
                parsing.parse_readme(path)
            self.assertIn("METADATA_LABEL_DUPLICATE", str(ctx.exception))

    def test_day_mismatch(self):
        with TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), helpers.day_readme(5, "标题"))
            with self.assertRaises(ImporterError) as ctx:
                parsing.parse_readme(path)
            self.assertIn("DAY_MISMATCH", str(ctx.exception))

    def test_type_inference(self):
        self.assertEqual(parsing.infer_day_type(168, 6), "final_assessment")
        self.assertEqual(parsing.infer_day_type(7, 1), "review")
        self.assertEqual(parsing.infer_day_type(6, 1), "integration")
        self.assertEqual(parsing.infer_day_type(163, 6), "documentation")
        self.assertEqual(parsing.infer_day_type(3, 1), "concept_lab")

    def test_required_tasks_mapping(self):
        self.assertEqual(
            set(parsing.required_tasks_for_type("review")),
            {"reading", "exercise", "acceptance"},
        )
        self.assertEqual(
            set(parsing.required_tasks_for_type("concept_lab")),
            {"reading", "exercise", "experiment", "acceptance"},
        )


class OverridesTests(SimpleTestCase):
    def test_valid_and_dedup(self):
        with TemporaryDirectory() as tmp:
            helpers.write_overrides(
                Path(tmp), {"day-029": {"skills": ["MLIR", "MLIR", "JIT"]}}
            )
            loaded = overrides.load_day_overrides(Path(tmp))
            self.assertEqual(loaded["day-029"]["skills"], ["MLIR", "JIT"])

    def test_unknown_field_rejected(self):
        with TemporaryDirectory() as tmp:
            config = Path(tmp) / "config" / "learning"
            config.mkdir(parents=True)
            (config / "day-overrides.json").write_text(
                json.dumps({"schema_version": 1, "days": {"day-001": {"day": 2}}}),
                encoding="utf-8",
            )
            with self.assertRaises(ImporterError):
                overrides.load_day_overrides(Path(tmp))

    def test_duplicate_json_key_rejected(self):
        with TemporaryDirectory() as tmp:
            config = Path(tmp) / "config" / "learning"
            config.mkdir(parents=True)
            (config / "day-overrides.json").write_text(
                '{"schema_version": 1, "schema_version": 1, "days": {}}',
                encoding="utf-8",
            )
            with self.assertRaises(ImporterError) as ctx:
                overrides.load_day_overrides(Path(tmp))
            self.assertIn("CONFIG_DUPLICATE_KEY", str(ctx.exception))

    def test_missing_file_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ImporterError):
                overrides.load_day_overrides(Path(tmp))


class ContentHashTests(SimpleTestCase):
    def test_deterministic_and_scoped(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            day = helpers.write_day(root, 1, with_runall=True)
            payload = overrides.canonical_override_payload({})
            sha1 = content_hash.compute_content_sha(day, payload)
            sha2 = content_hash.compute_content_sha(day, payload)
            self.assertEqual(sha1, sha2)
            # 其他日课内容变化不影响本日哈希。
            other = helpers.write_day(root, 2)
            self.assertNotEqual(sha1, content_hash.compute_content_sha(other, payload))
            # 本日内容变化会改变哈希。
            (day / "code" / "main.cpp").write_text("int main(){ return 99; }\n")
            self.assertNotEqual(sha1, content_hash.compute_content_sha(day, payload))
            # 覆盖配置参与哈希。
            payload2 = overrides.canonical_override_payload({"type": "environment_lab"})
            self.assertNotEqual(sha1, content_hash.compute_content_sha(day, payload2))


class ChunkingTests(SimpleTestCase):
    def test_chunks_and_anchors(self):
        markdown = (
            "## 概念\n\nMLIR 基础。\n\n### 环境\n\nmlir-opt 用法。\n\n"
            "## 验收\n\n检查清单。"
        )
        chunks = chunking.build_chunks(markdown, "day-001")
        headings = [c.heading for c in chunks]
        self.assertIn("概念", headings)
        self.assertIn("环境", headings)
        self.assertIn("验收", headings)
        anchors = {c.anchor for c in chunks}
        self.assertIn("概念", anchors)
        self.assertIn("环境", anchors)

    def test_meta_quote_block_skipped(self):
        markdown = (
            "> **今日目标**：目标\n> **预计时间**：学习 30 分钟 + 实践 45 分钟\n\n"
            "## 概念\n\n正文。"
        )
        chunks = chunking.build_chunks(markdown, "day-001")
        joined = "\n".join(c.text for c in chunks)
        self.assertNotIn("今日目标", joined)
        self.assertIn("正文", joined)

    def test_long_section_split(self):
        paragraph = "这是很长的段落内容，用于测试分片边界。" * 120
        markdown = f"## 大节\n\n{paragraph}\n\n{paragraph}\n"
        chunks = chunking.build_chunks(markdown, "day-001")
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.text), 4000 + 200)

    def test_error_tokens(self):
        markdown = "运行后出现 `E104` 与 `LLVM ERROR:` 错误。\n\n正常行。"
        tokens = chunking.collect_error_tokens(markdown)
        self.assertIn("E104", tokens)

    def test_code_paths(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            helpers.write_day(root, 1, with_runall=True, with_outputs=True)
            day_dir = root / "tutorials" / "week-001" / "day-001"
            result = chunking.collect_code_paths(day_dir / "code")
            self.assertIn("code/main.cpp", result.paths)
            self.assertIn("code/run_all.sh", result.paths)
            self.assertNotIn(
                "code/outputs/result.txt", result.paths
            )  # outputs 不进入 code_paths。


class ZipBuilderTests(SimpleTestCase):
    def _day_dir(self, tmp, **kwargs):
        root = Path(tmp)
        return helpers.write_day(root, 1, **kwargs)

    def test_deterministic_zip(self):
        with TemporaryDirectory() as tmp:
            day = self._day_dir(tmp, with_runall=True)
            import hashlib

            path1 = Path(tmp) / "a.zip"
            path2 = Path(tmp) / "b.zip"
            r1 = zip_builder.build_source_zip(path1, day / "code", [])
            r2 = zip_builder.build_source_zip(path2, day / "code", [])
            self.assertEqual(
                hashlib.sha256(path1.read_bytes()).hexdigest(),
                hashlib.sha256(path2.read_bytes()).hexdigest(),
            )
            self.assertIsNotNone(r1)
            import zipfile

            with zipfile.ZipFile(path1) as zf:
                names = zf.namelist()
                self.assertIn("code/run_all.sh", names)
                self.assertIn("code/main.cpp", names)
                info = zf.getinfo("code/run_all.sh")
                self.assertNotEqual((info.external_attr >> 16) & 0o111, 0)

    def test_outputs_excluded_unless_source_include(self):
        with TemporaryDirectory() as tmp:
            day = self._day_dir(tmp, with_runall=True, with_outputs=True)
            import zipfile

            path = Path(tmp) / "base.zip"
            zip_builder.build_source_zip(path, day / "code", [])
            with zipfile.ZipFile(path) as zf:
                self.assertNotIn("code/outputs/result.txt", zf.namelist())
            path2 = Path(tmp) / "include.zip"
            zip_builder.build_source_zip(path2, day / "code", ["result.txt"])
            with zipfile.ZipFile(path2) as zf:
                self.assertIn("code/outputs/result.txt", zf.namelist())

    def test_secret_rejected(self):
        with TemporaryDirectory() as tmp:
            day = self._day_dir(tmp)
            (day / "code" / "run.sh").write_text(
                "#!/bin/bash\nTOKEN=ghp_0123456789abcdefghijklmnopqrstuvwxyz\n",
                encoding="utf-8",
            )
            with self.assertRaises(ImporterError) as ctx:
                zip_builder.build_source_zip(
                    Path(tmp) / "s.zip", day / "code", []
                )
            self.assertIn("ZIP_SECRET_DETECTED", str(ctx.exception))

    def test_placeholder_allowed(self):
        with TemporaryDirectory() as tmp:
            day = self._day_dir(tmp)
            (day / "code" / "run.sh").write_text(
                "#!/bin/bash\nTOKEN=YOUR_TOKEN_HERE\n", encoding="utf-8"
            )
            result = zip_builder.build_source_zip(
                Path(tmp) / "s.zip", day / "code", []
            )
            self.assertIsNotNone(result)

    def test_binary_excluded(self):
        with TemporaryDirectory() as tmp:
            day = self._day_dir(tmp)
            binary = bytes(range(256)) * 64
            (day / "code" / "a.out").write_bytes(binary)
            import zipfile

            path = Path(tmp) / "s.zip"
            zip_builder.build_source_zip(path, day / "code", [])
            with zipfile.ZipFile(path) as zf:
                self.assertNotIn("code/a.out", zf.namelist())

    def test_no_code_returns_none(self):
        with TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            self.assertIsNone(zip_builder.build_source_zip(
                Path(tmp) / "s.zip", empty, []
            ))
