/**
 * search.js —— 搜索页渐进增强：防抖即时查询 + 取消旧请求。
 * 基础 GET 表单与翻页由服务端提供，无 JavaScript 仍可用。
 */
(function (global) {
    'use strict';

    function initSearchEnhancement() {
        var form = document.querySelector('[data-learning="search-form"]');
        var results = document.querySelector('[data-learning="search-results"]');
        var status = document.querySelector('[data-learning="search-status"]');
        if (!form || !results || !global.LearningAPI) return;

        var input = form.querySelector('input[name="q"]');
        if (!input) return;
        var controller = null;
        var timer = null;
        var DEBOUNCE_MS = 250;

        function params() {
            var data = new FormData(form);
            var query = {};
            ['q', 'phase', 'week', 'type'].forEach(function (key) {
                query[key] = data.get(key) || '';
            });
            return query;
        }

        function render(items, total, q) {
            results.textContent = '';
            items.forEach(function (item) {
                var section = document.createElement('section');
                section.className = 'learning-search-item';
                var heading = document.createElement('h2');
                var link = document.createElement('a');
                link.href = '/' + item.url + (item.anchor ? '#' + item.anchor : '');
                link.textContent = 'Day ' + item.day + '：' + item.title;
                heading.appendChild(link);
                var meta = document.createElement('p');
                meta.className = 'learning-search-meta';
                meta.textContent = '阶段 ' + item.phase + ' · 第 ' + item.week + ' 周 · 命中字段 ' +
                    (item.matched_fields || []).join('/');
                if (item.heading) meta.textContent += ' · 章节「' + item.heading + '」';
                var snippet = document.createElement('p');
                snippet.className = 'learning-search-snippet';
                snippet.textContent = item.snippet || '';
                section.appendChild(heading);
                section.appendChild(meta);
                if (item.snippet) section.appendChild(snippet);
                results.appendChild(section);
            });
            if (status) {
                status.textContent = total
                    ? '共 ' + total + ' 个日课命中「' + q + '」'
                    : '「' + q + '」无结果';
            }
        }

        function runSearch() {
            if (controller) controller.abort();
            controller = new AbortController();
            var query = params();
            var search = new URLSearchParams(query);
            fetch('/api/v1/search/?' + search.toString(), {
                credentials: 'same-origin',
                signal: controller.signal
            }).then(function (response) { return response.json(); }).then(function (data) {
                if (data && Array.isArray(data.results)) {
                    render(data.results, data.total_days || 0, query.q);
                }
            }).catch(function (err) {
                if (err && err.name === 'AbortError') return;
                if (status) status.textContent = '搜索请求失败，请重试。';
            });
        }

        input.addEventListener('input', function () {
            clearTimeout(timer);
            if (!input.value.trim()) return; // 空查询保留服务端初始内容。
            timer = setTimeout(runSearch, DEBOUNCE_MS);
        });
        form.addEventListener('submit', function (event) {
            clearTimeout(timer);
            // 标准提交仍交给服务端渲染（保留翻页与无 JS 基线路径）。
            if (controller) controller.abort();
        });
    }

    global.LearningSearch = { initSearchEnhancement: initSearchEnhancement };
})(window);
