#!/usr/bin/env python3
"""tools/learning_assets.py 与 learning_search.py 单元测试（WP-02/WP-05）。"""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import learning_assets  # noqa: E402
import learning_search  # noqa: E402
from learning_metadata import LearningError  # noqa: E402


def make_code_tree(root, day=1, week=1):
    day_dir = Path(root) / f"week-{week:03d}" / f"day-{day:03d}"
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "README.md").write_text("# 第 001 天：示例\n\n> **今日目标**：x\n", encoding="utf-8")
    code = day_dir / "code"
    code.mkdir(exist_ok=True)
    (code / "run_all.sh").write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
    (code / "run_all.sh").chmod(0o755)
    (code / "main.py").write_text("print('hi')\n", encoding="utf-8")
    src = code / "src"
    src.mkdir(exist_ok=True)
    (src / "util.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (code / "build").mkdir(exist_ok=True)
    (code / "build" / "a.o").write_text("object", encoding="utf-8")
    (code / "lib.so").write_bytes(b"\x7fELFfake")
    outputs = code / "outputs"
    outputs.mkdir(exist_ok=True)
    (outputs / "frozen.txt").write_text("frozen\n", encoding="utf-8")
    (code / ".DS_Store").write_bytes(b"junk")
    return day_dir


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.day_dir = make_code_tree(self.root)

    def test_default_exclusions(self):
        selected = learning_assets.select_archive_files(self.day_dir, {})
        names = [rel for rel, _ in selected]
        self.assertIn("run_all.sh", names)
        self.assertIn("main.py", names)
        self.assertNotIn("outputs/frozen.txt", names)
        self.assertNotIn("build/a.o", names)
        self.assertNotIn("lib.so", names)
        self.assertNotIn(".DS_Store", names)

    def test_source_include_exception(self):
        selected = learning_assets.select_archive_files(
            self.day_dir, {"source_include": ["outputs/frozen.txt"]}
        )
        names = [rel for rel, _ in selected]
        self.assertIn("outputs/frozen.txt", names)

    def test_unknown_include_fails(self):
        with self.assertRaises(LearningError):
            learning_assets.select_archive_files(self.day_dir, {"source_include": ["outputs/missing.txt"]})

    def test_secret_rejected(self):
        (self.day_dir / "code" / "token.txt").write_text("AKIAIOSFODNN7EXAMPLE", encoding="utf-8")
        with self.assertRaises(LearningError) as ctx:
            learning_assets.select_archive_files(self.day_dir, {})
        self.assertIn("LEARNING_E203", str(ctx.exception))

    def test_no_code_dir(self):
        empty = self.root / "week-001" / "day-002"
        empty.mkdir(parents=True)
        (empty / "README.md").write_text("# 第 002 天\n", encoding="utf-8")
        self.assertIsNone(learning_assets.select_archive_files(empty, {}))

    def test_symlink_excluded(self):
        link = self.day_dir / "code" / "link.py"
        link.symlink_to(self.day_dir / "code" / "main.py")
        names = [rel for rel, _ in learning_assets.select_archive_files(self.day_dir, {})]
        self.assertNotIn("link.py", names)


class ZipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.day_dir = make_code_tree(self.root)
        self.out = self.root / "public"

    def test_deterministic_and_exec_bit(self):
        path1, _ = learning_assets.build_day_zip(self.day_dir, self.out, "day-001")
        first = path1.read_bytes()
        path2, _ = learning_assets.build_day_zip(self.day_dir, self.out, "day-001")
        self.assertEqual(first, path2.read_bytes())
        with zipfile.ZipFile(path1) as zf:
            info = zf.getinfo("run_all.sh")
            perm = (info.external_attr >> 16) & 0o777
            self.assertTrue(perm & 0o111, "可执行位必须保留")
            self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertIsNone(zf.testzip())
            names = zf.namelist()
            self.assertIn("run_all.sh", names)
            self.assertTrue(any(n.endswith("/") for n in names), "应包含显式目录项")

    def test_expected_names_helper(self):
        selected = learning_assets.select_archive_files(self.day_dir, {})
        names = learning_assets.expected_zip_names(selected)
        self.assertIn("run_all.sh", names)
        with_dir = [n for n in names if n.endswith("/")]
        self.assertTrue(with_dir)


class SlugParityTest(unittest.TestCase):
    """与 static/js/vp-solution.js makeSlugger 的关键行为保持一致。"""

    def test_cjk_passthrough(self):
        slugify = learning_search.make_slugger()
        self.assertEqual(slugify("环境检查"), "环境检查")

    def test_punctuation_and_spaces(self):
        slugify = learning_search.make_slugger()
        self.assertEqual(slugify("3. 核心概念：装的是什么、有哪些工具？"), "_3-核心概念装的是什么有哪些工具")

    def test_day_prefix(self):
        slugify = learning_search.make_slugger()
        self.assertEqual(slugify("Day 29（环境）"), "day-29")

    def test_dedupe(self):
        slugify = learning_search.make_slugger()
        first = slugify("重复标题")
        second = slugify("重复标题")
        self.assertEqual(first, "重复标题")
        self.assertEqual(second, "重复标题-1")


class ChunkTest(unittest.TestCase):
    def test_headings_and_fences(self):
        markdown = """前言段落。

## 第一节：概念

正文 A。

```bash
mlir-opt --canonicalize checkin.mlir
```

### 子节

内容 B。

## 第二节：实验

内容 C。"""
        chunks = learning_search.extract_chunks(markdown)
        headings = [c["heading"] for c in chunks]
        self.assertIn("第一节：概念", headings)
        self.assertIn("子节", headings)
        joined = "\n".join(c["text"] for c in chunks)
        self.assertIn("mlir-opt --canonicalize checkin.mlir", joined)
        self.assertNotIn("```", joined)
        # 前言也是一个 chunk
        self.assertTrue(any(c["heading"] == "" and "前言" in c["text"] for c in chunks))

    def test_long_section_split(self):
        paragraph = "x" * 300 + " "
        markdown = "## 长节\n\n" + "\n\n".join([f"段落{i} " + paragraph for i in range(20)])
        chunks = learning_search.extract_chunks(markdown)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks[1:]:
            self.assertLessEqual(len(chunk["text"]), 4600)

    def test_code_paths_and_errors(self):
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        day_dir = make_code_tree(tmp.name)
        (day_dir / "code" / "fail.log").write_text("test.cpp:12:5: error: use of undeclared identifier 'foo'\n", encoding="utf-8")
        paths = learning_search.collect_code_paths(day_dir)
        self.assertIn("code/run_all.sh", paths)
        self.assertIn("code/outputs/frozen.txt", paths)
        tokens = learning_search.collect_error_tokens(
            day_dir, "报错示例 `LLVM ERROR: bad op` 与 `error: foo` 出现"
        )
        self.assertTrue(any("error: use of undeclared identifier" in t for t in tokens))
        self.assertTrue(any("LLVM ERROR" in t for t in tokens))


if __name__ == "__main__":
    unittest.main()
