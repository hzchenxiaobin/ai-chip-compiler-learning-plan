/**
 * search.js — 本地搜索查询运行时（WP-05）。
 *
 * 对应 docs/development/02_前端学习模块.md §8：
 * - 轻量索引 + 六阶段正文分片按需加载，提交一致性检查
 * - CJK 二元词 + ASCII 完整 token；AND 查询；字段加权评分
 * - AbortController 取消旧查询 + 递增查询序号，旧响应不能覆盖新结果
 * - 阶段筛选只加载目标分片；全部阶段最多 2 个并发请求
 */

import { joinBasePath } from './progress.js';

const RESULT_PAGE_SIZE = 50;
const MAX_CONCURRENT_FETCH = 2;
const SNIPPET_CONTEXT = 60;

const ASCII_TOKEN_RE = /[A-Za-z0-9_.\/\-]+/g;
const CJK_RUN_RE = /[\u4e00-\u9fff]+/g;

export class SearchError extends Error {
  constructor(code, message) {
    super(`[${code}] ${message}`);
    this.code = code;
  }
}

/** 查询分词：CJK 连续段生成二元词（单字保留），ASCII 保留完整 token 并小写。 */
export function tokenizeQuery(query) {
  const tokens = [];
  const asciiRuns = String(query || '').match(ASCII_TOKEN_RE) || [];
  for (const run of asciiRuns) tokens.push(run.toLowerCase());
  const cjkRuns = String(query || '').match(CJK_RUN_RE) || [];
  for (const run of cjkRuns) {
    if (run.length === 1) tokens.push(run);
    else for (let i = 0; i < run.length - 1; i += 1) tokens.push(run.slice(i, i + 2));
  }
  return tokens;
}

function matchesAll(haystackLower, tokens) {
  return tokens.every((token) => haystackLower.includes(token));
}

function containsExact(haystackLower, exact) {
  return exact.length > 1 && haystackLower.includes(exact);
}

function buildSnippet(text, tokens) {
  const lower = text.toLowerCase();
  let hitIndex = -1;
  for (const token of tokens) {
    const index = lower.indexOf(token);
    if (index !== -1 && (hitIndex === -1 || index < hitIndex)) hitIndex = index;
  }
  if (hitIndex === -1) return text.slice(0, SNIPPET_CONTEXT * 2).trim();
  const start = Math.max(0, hitIndex - SNIPPET_CONTEXT);
  const end = Math.min(text.length, hitIndex + SNIPPET_CONTEXT * 2);
  const prefix = start > 0 ? '…' : '';
  const suffix = end < text.length ? '…' : '';
  return (prefix + text.slice(start, end) + suffix).replace(/\s+/g, ' ').trim();
}

function searchDirBase(daysUrl) {
  const index = daysUrl.lastIndexOf('/');
  return index === -1 ? '' : daysUrl.slice(0, index + 1);
}

/**
 * 创建搜索控制器。
 * options: { daysUrl, basePath, fetchImpl }；daysUrl 指向 learning/days.json。
 */
export function createSearchController(options) {
  const daysUrl = options.daysUrl;
  const basePath = options.basePath || '';
  const fetchImpl = options.fetchImpl || ((url, init) => fetch(url, init));
  const baseDir = searchDirBase(daysUrl);

  let litePromise = null;
  let liteIndex = null;
  let daysCommit = null;
  let querySeq = 0;
  let activeAbort = null;
  const phaseCache = new Map();

  async function fetchJson(url, init) {
    const response = await fetchImpl(url, init);
    if (!response.ok) {
      throw new SearchError('INDEX_UNAVAILABLE', `请求失败 ${response.status}：${url}`);
    }
    return response.json();
  }

  async function loadDays() {
    if (daysCommit) return daysCommit;
    const data = await fetchJson(daysUrl, { cache: 'no-cache' });
    if (!data || !Array.isArray(data.days)) {
      throw new SearchError('INDEX_UNAVAILABLE', 'days.json 结构非法');
    }
    daysCommit = data.content_commit;
    return daysCommit;
  }

  async function loadLite() {
    if (liteIndex) return liteIndex;
    if (!litePromise) {
      litePromise = (async () => {
        const commit = await loadDays();
        const lite = await fetchJson(`${baseDir}search/lite-index.json`, { cache: 'no-cache' });
        if (!lite || !Array.isArray(lite.days)) {
          throw new SearchError('INDEX_UNAVAILABLE', '轻量索引结构非法');
        }
        if (lite.content_commit !== commit) {
          throw new SearchError('CONTENT_VERSION_MISMATCH', '轻量索引与 days.json 提交不一致');
        }
        liteIndex = lite;
        return lite;
      })();
      litePromise.catch(() => {
        litePromise = null;
      });
    }
    return litePromise;
  }

  async function loadPhase(phase, signal) {
    if (phaseCache.has(phase)) return phaseCache.get(phase);
    const commit = await loadDays();
    const shard = await fetchJson(`${baseDir}search/phase-${phase}.json?v=${commit}`, { signal });
    if (!shard || shard.content_commit !== commit) {
      throw new SearchError('CONTENT_VERSION_MISMATCH', `阶段 ${phase} 分片与 days.json 提交不一致`);
    }
    phaseCache.set(phase, shard);
    return shard;
  }

  async function loadPhasesWithLimit(phases, signal) {
    const results = new Array(phases.length);
    let cursor = 0;
    async function worker() {
      while (cursor < phases.length) {
        const index = cursor;
        cursor += 1;
        results[index] = await loadPhase(phases[index], signal);
      }
    }
    const workers = [];
    for (let i = 0; i < Math.min(MAX_CONCURRENT_FETCH, phases.length); i += 1) workers.push(worker());
    await Promise.all(workers);
    return results;
  }

  function filterDays(lite, filters) {
    return lite.days.filter((day) => {
      if (filters.phase != null && day.phase !== filters.phase) return false;
      if (filters.week != null && day.week !== filters.week) return false;
      if (filters.type && day.type !== filters.type) return false;
      return true;
    });
  }

  function scoreLiteDay(day, tokens, exact, matchesRef) {
    const titleLower = day.title.toLowerCase();
    const objectiveLower = `${day.objective || ''}\n${day.deliverable || ''}`.toLowerCase();
    const skillsLower = (day.skills || []).join('\n').toLowerCase();
    let score = 0;
    if (matchesAll(titleLower, tokens)) {
      score += 12;
      matchesRef.push('title');
    }
    if (skillsLower && matchesAll(skillsLower, tokens)) {
      score += 8;
      matchesRef.push('skills');
    }
    if (objectiveLower.trim() && matchesAll(objectiveLower, tokens)) {
      score += 5;
      matchesRef.push('objective');
    }
    if (containsExact(`${titleLower}\n${objectiveLower}\n${skillsLower}`, exact)) score += 10;
    return score;
  }

  function scoreFullDay(dayEntry, tokens, exact, matchesRef) {
    let dayScore = 0;
    const codePathsLower = (dayEntry.code_paths || []).join('\n').toLowerCase();
    if (codePathsLower && matchesAll(codePathsLower, tokens)) {
      dayScore += 3;
      matchesRef.push('code');
    }
    const chunks = [];
    for (const chunk of dayEntry.chunks || []) {
      const textLower = chunk.text.toLowerCase();
      const headingLower = (chunk.heading || '').toLowerCase();
      if (!matchesAll(textLower, tokens) && !matchesAll(headingLower, tokens)) continue;
      let chunkScore = 1;
      if (headingLower && matchesAll(headingLower, tokens)) {
        chunkScore += 4;
        matchesRef.push('heading');
      }
      if (containsExact(textLower, exact) || containsExact(headingLower, exact) || containsExact(codePathsLower, exact)) {
        chunkScore += 10;
        matchesRef.push('exact');
      }
      chunks.push({
        chunk,
        score: chunkScore,
        snippet: buildSnippet(chunk.text, tokens),
      });
    }
    chunks.sort((a, b) => b.score - a.score || a.chunk.chunk_id.localeCompare(b.chunk.chunk_id));
    return { dayScore, chunks: chunks.slice(0, 3) };
  }

  function buildResponse(query, scope, filters, results, truncated, loadedPhases) {
    return { query, scope, filters, results, truncated, loadedPhases };
  }

  async function searchLite(query, filters = {}) {
    const lite = await loadLite();
    const tokens = tokenizeQuery(query);
    if (!tokens.length) return buildResponse(query, 'lite', filters, [], false, []);
    const exact = String(query || '').trim().toLowerCase();
    const normalizedFilters = {
      phase: filters.phase ? Number(filters.phase) : null,
      week: filters.week ? Number(filters.week) : null,
      type: filters.type || null,
    };
    const results = [];
    for (const day of filterDays(lite, normalizedFilters)) {
      const matchedFields = [];
      const score = scoreLiteDay(day, tokens, exact, matchedFields);
      if (score <= 0 || !matchedFields.length) continue;
      results.push({
        dayId: day.day_id,
        day: day.day,
        title: day.title,
        url: joinBasePath(basePath, day.url),
        heading: '',
        anchor: '',
        snippet: buildSnippet(`${day.objective || ''}\n${day.deliverable || ''}`, tokens),
        score,
        matchedFields: [...new Set(matchedFields)],
      });
    }
    results.sort((a, b) => b.score - a.score || a.day - b.day || a.title.localeCompare(b.title));
    const truncated = results.length > RESULT_PAGE_SIZE;
    return buildResponse(query, 'lite', normalizedFilters, results.slice(0, RESULT_PAGE_SIZE), truncated, []);
  }

  async function searchFull(query, filters = {}, signal) {
    const seq = ++querySeq;
    if (activeAbort) activeAbort.abort();
    const controller = new AbortController();
    activeAbort = controller;
    if (signal) signal.addEventListener('abort', () => controller.abort(), { once: true });
    try {
      const lite = await loadLite();
      const tokens = tokenizeQuery(query);
      if (!tokens.length) return buildResponse(query, 'full', filters, [], false, []);
      const normalizedFilters = {
        phase: filters.phase ? Number(filters.phase) : null,
        week: filters.week ? Number(filters.week) : null,
        type: filters.type || null,
      };
      const candidateDays = filterDays(lite, normalizedFilters);
      const phasesNeeded = [...new Set(candidateDays.map((day) => day.phase))].sort((a, b) => a - b);
      const shards = await loadPhasesWithLimit(phasesNeeded, controller.signal);
      if (seq !== querySeq) return buildResponse(query, 'full', normalizedFilters, [], false, phasesNeeded);

      const shardByPhase = new Map(shards.map((shard) => [shard.phase, shard]));
      const exact = String(query || '').trim().toLowerCase();
      const results = [];
      for (const day of candidateDays) {
        const shard = shardByPhase.get(day.phase);
        if (!shard) continue;
        const dayEntry = (shard.days || []).find((entry) => entry.day_id === day.day_id);
        if (!dayEntry) continue;
        const matchedFields = [];
        let score = scoreLiteDay(day, tokens, exact, matchedFields);
        const full = scoreFullDay(dayEntry, tokens, exact, matchedFields);
        score += full.dayScore;
        if (!matchedFields.length) continue;
        const best = full.chunks[0];
        results.push({
          dayId: day.day_id,
          day: day.day,
          title: day.title,
          url: joinBasePath(basePath, day.url) + (best && best.chunk.anchor ? `#${encodeURIComponent(best.chunk.anchor)}` : ''),
          heading: best ? best.chunk.heading : '',
          anchor: best ? best.chunk.anchor : '',
          snippet: best ? best.snippet : buildSnippet(`${day.objective || ''}`, tokens),
          score,
          matchedFields: [...new Set(matchedFields)],
          chunks: full.chunks.map((item) => ({ heading: item.chunk.heading, anchor: item.chunk.anchor, snippet: item.snippet, score: item.score })),
        });
      }
      results.sort((a, b) => b.score - a.score || a.day - b.day || a.title.localeCompare(b.title));
      const truncated = results.length > RESULT_PAGE_SIZE;
      return buildResponse(query, 'full', normalizedFilters, results.slice(0, RESULT_PAGE_SIZE), truncated, phasesNeeded);
    } catch (err) {
      if (controller.signal.aborted && seq !== querySeq) {
        return buildResponse(query, 'full', filters, [], false, []);
      }
      throw err;
    }
  }

  function cancel() {
    querySeq += 1;
    if (activeAbort) {
      activeAbort.abort();
      activeAbort = null;
    }
  }

  return { loadLite, searchLite, searchFull, cancel };
}
