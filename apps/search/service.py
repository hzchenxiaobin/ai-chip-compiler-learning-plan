"""搜索服务（设计文档 §7.5）：构建 posting 与查询。

排序：字段权重（标题 12、技能 8、目标/产出 5、章节 4、代码路径 3、正文 1）
＋技术 token 精确匹配额外 10；同日最多 3 个 chunk；顺序稳定
（总分降序、日号升序、chunk_id 升序）。
"""
import base64
import json

from apps.content.importer.tokenizer import tokenize_unique, is_technical_token
from apps.content.models import ContentChunk, ContentDayVersion
from .models import FIELD_WEIGHTS, EXACT_BONUS, SearchField, SearchPosting, SearchToken

MAX_CHUNKS_PER_DAY = 3
PAGE_SIZE = 20
CANDIDATE_CAP = 1600


# ---------------------------------------------------------------------------
# 构建期
# ---------------------------------------------------------------------------

def day_field_texts(meta: dict) -> dict[str, str]:
    """日级字段的文本（title/skill/objective/deliverable/code_path）。"""
    return {
        SearchField.TITLE: meta.get("title", ""),
        SearchField.SKILL: " ".join(meta.get("skills", [])),
        SearchField.OBJECTIVE: meta.get("objective", ""),
        SearchField.DELIVERABLE: meta.get("deliverable", ""),
        SearchField.CODE_PATH: " ".join(meta.get("code_paths", []))
        + " "
        + " ".join(meta.get("error_tokens", [])),
    }


def collect_day_tokens(meta: dict, chunks: list[dict]) -> set[str]:
    """该日全部待索引 token（供全局 token 表批量创建）。"""
    tokens: set[str] = set()
    for text in day_field_texts(meta).values():
        if text:
            tokens.update(tokenize_unique(text))
    for chunk in chunks:
        for text in (chunk.get("heading", ""), chunk.get("text", "")):
            if text:
                tokens.update(tokenize_unique(text))
    return tokens


def bulk_create_tokens(all_tokens: set[str]) -> dict[str, int]:
    """批量创建 token 并返回 {token: id} 映射。"""
    existing = {row["token"]: row["pk"] for row in SearchToken.objects.values("pk", "token")}
    missing = [SearchToken(token=t) for t in sorted(all_tokens) if t not in existing]
    if missing:
        SearchToken.objects.bulk_create(missing, batch_size=2000, ignore_conflicts=True)
        for token in SearchToken.objects.filter(token__in=[t.token for t in missing]).values("pk", "token"):
            existing[token["token"]] = token["pk"]
    return existing


def build_postings(version: ContentDayVersion, meta: dict, chunks: list[dict], token_map: dict):
    """为单个日课版本写入搜索 posting。chunks 为 {chunk_id, heading, text} 字典列表。

    日级字段挂在 {day_id}:meta 伪 chunk 上，保证标题/技能命中也能返回结果。
    """
    meta_chunk_id = f"{version.day_id}:meta"
    sources: list[tuple[str, str, str]] = []  # (chunk_id, field, text)
    for field, text in day_field_texts(meta).items():
        if text:
            sources.append((meta_chunk_id, field, text))
    for chunk in chunks:
        if chunk.get("heading"):
            sources.append((chunk["chunk_id"], SearchField.HEADING, chunk["heading"]))
        if chunk.get("text"):
            sources.append((chunk["chunk_id"], SearchField.BODY, chunk["text"]))

    postings = []
    for chunk_id, field, text in sources:
        weight = FIELD_WEIGHTS[field]
        for position, token in enumerate(tokenize_unique(text)):
            token_id = token_map.get(token)
            if token_id is None:
                continue
            postings.append(
                SearchPosting(
                    version=version,
                    day_id=version.day_id,
                    chunk_id=chunk_id,
                    field=field,
                    token_id=token_id,
                    weight=weight,
                    position=position,
                )
            )
    SearchPosting.objects.bulk_create(postings, batch_size=2000, ignore_conflicts=True)
    return len(postings)


# ---------------------------------------------------------------------------
# 查询期
# ---------------------------------------------------------------------------

def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor + "==" * (-len(cursor) % 4)))
        offset = data.get("offset", 0)
        return offset if isinstance(offset, int) and 0 <= offset < 100000 else 0
    except Exception:
        return 0


def encode_cursor(offset: int) -> str:
    payload = json.dumps({"offset": offset}).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def search(release, query: str, *, phase=None, week=None, day_type=None,
           page_size=PAGE_SIZE, offset=0):
    """在指定 release 上执行查询。返回 (items, total_days, next_cursor)。"""
    terms = tokenize_unique(query)
    if not terms:
        return [], 0, None

    term_set = set(terms)
    token_rows = list(SearchToken.objects.filter(token__in=terms).values("pk", "token"))
    if not token_rows:
        return [], 0, None
    token_ids = [row["pk"] for row in token_rows]
    token_map = {row["pk"]: row["token"] for row in token_rows}

    postings = (
        SearchPosting.objects.filter(token__in=token_ids, version__release_id=release.pk)
        .values("day_id", "chunk_id", "field", "weight", "token")
    )
    scores: dict[tuple[str, str], dict] = {}
    for posting in postings.iterator(chunk_size=5000):
        key = (posting["day_id"], posting["chunk_id"])
        entry = scores.get(key)
        if entry is None:
            entry = scores[key] = {"score": 0, "fields": set()}
        token = token_map.get(posting["token"], "")
        bonus = EXACT_BONUS if token and is_technical_token(token) else 0
        entry["score"] += posting["weight"] + bonus
        entry["fields"].add(posting["field"])

    if not scores:
        return [], 0, None

    day_ids = {day_id for day_id, _ in scores}
    version_rows = ContentDayVersion.objects.filter(
        release_id=release.pk, day_id__in=day_ids
    ).values("day_id", "metadata_json")
    meta_by_day = {row["day_id"]: row["metadata_json"] for row in version_rows}

    def passes_filters(meta) -> bool:
        if phase is not None and str(meta.get("phase")) != str(phase):
            return False
        if week is not None and str(meta.get("week")) != str(week):
            return False
        if day_type and meta.get("type") != day_type:
            return False
        return True

    day_chunks: dict[str, list] = {}
    for (day_id, chunk_id), entry in scores.items():
        meta = meta_by_day.get(day_id)
        if meta is None or not passes_filters(meta):
            continue
        day_chunks.setdefault(day_id, []).append((chunk_id, entry))

    day_ranked = []
    for day_id, chunk_list in day_chunks.items():
        chunk_list.sort(key=lambda ce: (-ce[1]["score"], ce[0]))
        top = chunk_list[:MAX_CHUNKS_PER_DAY]
        day_score = sum(ce[1]["score"] for ce in top)
        day_ranked.append((day_id, day_score, top))
    day_ranked.sort(key=lambda item: (-item[1], int(item[0].removeprefix("day-"))))

    total_days = len(day_ranked)
    page = day_ranked[offset : offset + page_size]
    next_cursor = encode_cursor(offset + page_size) if offset + page_size < total_days else None

    if not page:
        return [], total_days, next_cursor

    # 一次性取本页 chunk 的 heading/anchor/text。
    needed_chunk_ids = {chunk_id for _, _, top in page for chunk_id, _ in top}
    chunk_rows = {
        row["chunk_id"]: row
        for row in ContentChunk.objects.filter(
            version__release_id=release.pk, chunk_id__in=needed_chunk_ids
        ).values("chunk_id", "heading", "anchor", "text")
    }

    items = []
    for day_id, day_score, top in page:
        meta = meta_by_day[day_id]
        best_chunk_id, best_entry = top[0]
        row = chunk_rows.get(best_chunk_id, {})
        snippet = _snippet(row.get("text", ""), term_set)
        items.append({
            "day_id": day_id,
            "day": meta["day"],
            "week": meta["week"],
            "phase": meta["phase"],
            "type": meta["type"],
            "title": meta["title"],
            "url": meta["url"],
            "heading": row.get("heading", ""),
            "anchor": row.get("anchor", ""),
            "snippet": snippet,
            "score": day_score,
            "matched_fields": sorted(best_entry["fields"]),
        })
    return items, total_days, next_cursor


def _snippet(text: str, terms: set[str]) -> str:
    if not text:
        return ""
    lowered = text.lower()
    position = -1
    hit_len = 0
    for term in terms:
        found = lowered.find(term.lower())
        if found >= 0:
            position, hit_len = found, len(term)
            break
    if position < 0:
        return text[:140]
    start = max(0, position - 60)
    end = min(len(text), position + hit_len + 60)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix
