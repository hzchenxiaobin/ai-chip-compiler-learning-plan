#!/usr/bin/env python3
"""学习产物校验（WP-01/WP-07）。

对应 docs/development/01_构建与内容契约.md §9，在完整构建后执行：
1. days.json 结构与业务规则
2. 站内资源存在性、日课链接与 chunk 锚点
3. ZIP 安全、权限与条目
4. 索引覆盖、提交一致性与样例查询
5. HTML data-day-id / data-content-sha 与 days.json 一致
6. 学习页面与静态资源存在、无硬编码域名

用法：``python3 tools/learning_validate.py [--public public] [--base-path ""]``
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import learning_assets
import learning_metadata
import learning_search

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _walk_tutorials_markdown():
    """返回 {day_number: markdown 正文}（重新读取权威源做锚点复核）。"""
    result = {}
    for readme in sorted((_REPO_ROOT / "tutorials").glob("week-*/day-*/README.md")):
        day_dir = readme.parent
        try:
            day = int(day_dir.name.removeprefix("day-"))
        except ValueError:
            continue
        lines = readme.read_text(encoding="utf-8").strip().splitlines()
        result[day] = "\n".join(lines[1:]).strip()
    return result


def _heading_slugs(markdown):
    """按文档顺序对全部标题运行 slug 复刻，返回可锚点集合。"""
    slugify = learning_search.make_slugger()
    slugs = set()
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if match:
            slug = slugify(match.group(2))
            if slug:
                slugs.add(slug)
    return slugs


def _tokenize(query):
    """查询分词：CJK 二元 + ASCII 完整 token（与前端 search.js 同规则）。"""
    tokens = []
    ascii_runs = re.findall(r"[A-Za-z0-9_.\/\-]+", query)
    tokens.extend(run.lower() for run in ascii_runs if run)
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", query)
    for run in cjk_runs:
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _text_matches(text, tokens):
    text = text.lower()
    return all(token in text for token in tokens)


def validate_public(public_dir, days, content_commit, base_path="", repo_root=None):
    """完整校验 public/ 产物；发现问题打印并以非零码退出。"""
    public_dir = Path(public_dir)
    repo_root = Path(repo_root) if repo_root else _REPO_ROOT
    errors = []

    def fail(message):
        errors.append(message)

    # --- 1. days.json 结构 ------------------------------------------------
    days_path = public_dir / "learning" / "days.json"
    if not days_path.is_file():
        fail(f"缺少产物：{days_path}")
        return _finish(errors, public_dir)
    payload = json.loads(days_path.read_text(encoding="utf-8"))
    if payload.get("content_commit") != content_commit:
        fail("days.json content_commit 与构建提交不一致")
    if payload.get("base_path") != base_path:
        fail(f"days.json base_path={payload.get('base_path')!r} 与期望 {base_path!r} 不一致")
    collection_errors = learning_metadata.validate_day_collection(payload["days"], content_commit, base_path)
    for error in collection_errors:
        fail(str(error))

    # --- 2. 站内资源与链接 ------------------------------------------------
    for record in days:
        page = public_dir / record["url"] / "index.html"
        if not page.is_file():
            fail(f"日课页面缺失：{record['url']}")
        if record["source_zip"] and not (public_dir / record["source_zip"]).is_file():
            fail(f"源码包缺失：{record['source_zip']}")

    for required in (
        public_dir / "learning" / "search" / "lite-index.json",
        *[public_dir / "learning" / "search" / f"phase-{p}.json" for p in range(1, 7)],
        public_dir / "css" / "learning.css",
        public_dir / "js" / "learning" / "app.js",
        public_dir / "search" / "index.html",
        public_dir / "settings" / "index.html",
        public_dir / "phases" / "index.html",
        *[public_dir / "weeks" / f"week-{w:03d}" / "index.html" for w in range(1, 25)],
        *[public_dir / "phases" / f"phase-{p}" / "index.html" for p in range(1, 7)],
    ):
        if not required.is_file():
            fail(f"产物缺失：{required.relative_to(public_dir)}")

    # --- 3. ZIP 校验 -------------------------------------------------------
    for record in days:
        if not record["source_zip"]:
            continue
        day_dir = repo_root / Path(record["source_path"]).parent
        override = {}
        overrides_path = repo_root / "config" / "learning" / "day-overrides.json"
        if overrides_path.is_file():
            overrides_path_data = json.loads(overrides_path.read_text(encoding="utf-8"))
            override = overrides_path_data.get("days", {}).get(record["day_id"], {})
        selected = learning_assets.select_archive_files(day_dir, override)
        try:
            learning_assets.verify_day_zip(public_dir / record["source_zip"], learning_assets.expected_zip_names(selected))
        except learning_metadata.LearningError as exc:
            fail(str(exc))

    # --- 4. 索引与锚点、样例查询 -------------------------------------------
    lite = json.loads((public_dir / "learning" / "search" / "lite-index.json").read_text(encoding="utf-8"))
    markdown_by_day = _walk_tutorials_markdown()
    shard_days = {}
    for phase in range(1, 7):
        shard = json.loads((public_dir / "learning" / "search" / f"phase-{phase}.json").read_text(encoding="utf-8"))
        for day_entry in shard["days"]:
            shard_days[day_entry["day_id"]] = day_entry
            day_num = int(day_entry["day_id"].removeprefix("day-"))
            slugs = _heading_slugs(markdown_by_day.get(day_num, ""))
            for chunk in day_entry["chunks"]:
                if chunk["anchor"] and chunk["anchor"] not in slugs:
                    fail(f"{day_entry['day_id']}：chunk 锚点 {chunk['anchor']!r} 不在日课标题 slug 集合中")

    tokens_mlir = _tokenize("MLIR")
    mlir_hits = [
        d["day_id"]
        for d in lite["days"]
        if _text_matches(" ".join([d["title"], d["objective"], d["deliverable"], " ".join(d["skills"])]), tokens_mlir)
    ]
    if "day-029" not in mlir_hits:
        fail(f"样例查询 MLIR 未命中 day-029（实际命中 {len(mlir_hits)} 天）")
    for sample in ("FileCheck", "JIT"):
        if not any(
            _text_matches(" ".join([d["title"], d["objective"], d["deliverable"], " ".join(d["skills"])]), _tokenize(sample))
            for d in lite["days"]
        ):
            fail(f"样例查询 {sample} 在 lite 索引无命中")

    def fulltext_hit(query):
        tokens = _tokenize(query)
        hits = set()
        for day_id, entry in shard_days.items():
            blob = "\n".join(c["text"] for c in entry["chunks"]) + "\n" + "\n".join(entry["code_paths"])
            if _text_matches(blob, tokens):
                hits.add(day_id)
        return hits

    run_all_days = {d["day_id"] for d in days if d["run_all"]}
    hits = fulltext_hit("run_all.sh")
    if not (hits & run_all_days):
        fail("样例查询 run_all.sh 未命中任何 run_all 日课")
    for sample in ("Roofline", "内存规划"):
        if not fulltext_hit(sample):
            fail(f"样例查询 {sample} 在正文分片无命中")

    # --- 5. 教程 HTML 数据属性一致性 ---------------------------------------
    for record in days:
        page = public_dir / record["url"] / "index.html"
        if not page.is_file():
            continue
        head = page.read_text(encoding="utf-8")[:6000]
        body_match = re.search(r"<body[^>]*>", head)
        if not body_match:
            fail(f"{record['day_id']}：页面缺少 body 标签")
            continue
        body_tag = body_match.group(0)
        day_attr = re.search(r'data-day-id="([^"]+)"', body_tag)
        sha_attr = re.search(r'data-content-sha="([^"]+)"', body_tag)
        if not day_attr or day_attr.group(1) != record["day_id"]:
            fail(f"{record['day_id']}：HTML data-day-id 与 days.json 不一致")
        if not sha_attr or sha_attr.group(1) != record["content_sha"]:
            fail(f"{record['day_id']}：HTML data-content-sha 与 days.json 不一致")

    # --- 6. 硬编码域名检查 ---------------------------------------------------
    banned = ("localhost", "127.0.0.1", "hzchenxiaobin.github.io")
    for checkee in [public_dir / "js" / "learning" / "app.js", public_dir / "css" / "learning.css"]:
        if not checkee.is_file():
            continue
        text = checkee.read_text(encoding="utf-8")
        for marker in banned:
            if marker in text:
                fail(f"{checkee.name} 疑似硬编码域名：{marker}")

    return _finish(errors, public_dir)


def _finish(errors, public_dir):
    if errors:
        for error in errors:
            print(f"[VALIDATE] {error}", file=sys.stderr)
        print(f"[VALIDATE] 校验失败：{len(errors)} 个问题", file=sys.stderr)
        raise SystemExit(1)
    print(f"[VALIDATE] public/ 校验通过：{public_dir}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="校验学习产物")
    parser.add_argument("--public", default=str(_REPO_ROOT / "public"))
    parser.add_argument("--base-path", default="")
    args = parser.parse_args()
    public_dir = Path(args.public)
    days_path = public_dir / "learning" / "days.json"
    if not days_path.is_file():
        raise SystemExit(f"[VALIDATE] 找不到 {days_path}，请先构建")
    payload = json.loads(days_path.read_text(encoding="utf-8"))
    validate_public(public_dir, payload["days"], payload["content_commit"], payload.get("base_path", args.base_path))


if __name__ == "__main__":
    main()
