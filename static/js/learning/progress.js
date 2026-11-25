/**
 * progress.js —— 日课任务卡、内容复核、计划切换与列表页状态。
 * 静态层由服务端渲染；本模块只在启用 JavaScript 时接管交互。
 */
(function (global) {
    'use strict';

    var STATE_LABELS = {
        not_started: '未开始', in_progress: '进行中', ready_for_review: '待验收',
        completed: '已完成', blocked: '有卡点'
    };

    function $(selector, root) { return (root || document).querySelector(selector); }
    function $all(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }

    /* ---------------- 日课任务卡 ---------------- */

    function initDayTaskCard() {
        var card = $('[data-learning="day-task"]');
        if (!card || !global.LearningAPI) return;
        var dayId = document.body.getAttribute('data-day-id');
        if (!dayId) return;

        var saveStatus = $('[data-learning="save-status"]', card);
        var overallEl = $('[data-learning="overall-status"]', card);
        var revision = null;

        function say(message, isError) {
            if (!saveStatus) return;
            saveStatus.textContent = message;
            saveStatus.classList.toggle('learning-save-error', Boolean(isError));
        }

        function refreshOverall(data) {
            revision = data.revision;
            if (overallEl && data.overall) {
                overallEl.textContent = STATE_LABELS[data.overall] || data.overall;
                overallEl.className = 'learning-state learning-state-' + data.overall;
            }
            var plannedToggle = $('[data-learning="planned-toggle"]', card);
            if (plannedToggle && typeof data.planned === 'boolean') {
                plannedToggle.disabled = false;
                plannedToggle.checked = data.planned;
            }
        }

        $all('input[type="radio"][data-task]', card).forEach(function (radio) {
            radio.addEventListener('change', function () {
                var task = radio.getAttribute('data-task');
                var status = radio.value;
                var fieldset = radio.closest('fieldset');
                if (fieldset) fieldset.setAttribute('aria-busy', 'true');
                say('保存中…');
                global.LearningAPI.apiFetch(global.LearningAPI.progressUrl(dayId), {
                    method: 'PATCH',
                    body: (function () { var payload = { tasks: {} }; payload.tasks[task] = status; return payload; })(),
                    ifMatch: revision,
                    create: revision === null
                }).then(function (result) {
                    if (result.ok) {
                        refreshOverall(result.data);
                        say('已保存');
                    } else {
                        // 失败：恢复该组之前的选中值。
                        var previous = fieldset && fieldset.getAttribute('data-previous');
                        if (previous) {
                            var prevRadio = fieldset.querySelector('input[value="' + previous + '"]');
                            if (prevRadio) prevRadio.checked = true;
                        }
                        if (result.status === 412 && result.data && result.data.current) {
                            refreshOverall(result.data.current);
                            say('版本冲突：页面已刷新为最新状态，请重试', true);
                        } else {
                            say('本次更改未保存：' + ((result.data && result.data.message) || '请求失败'), true);
                        }
                    }
                }).catch(function () {
                    say('网络错误，本次更改未保存', true);
                }).finally(function () {
                    if (fieldset) {
                        fieldset.removeAttribute('aria-busy');
                        fieldset.setAttribute('data-previous', status);
                    }
                });
            });
            var group = radio.closest('fieldset');
            if (group && radio.checked) group.setAttribute('data-previous', radio.value);
        });

        // 记录初始 revision / planned / overall（来自 data-* 或首次 GET）。
        var banner = $('[data-learning="version-banner"]', card);
        var ackButton = banner && $('[data-learning="acknowledge"]', banner);
        if (ackButton) {
            ackButton.addEventListener('click', function () {
                say('复核中…');
                global.LearningAPI.apiFetch(global.LearningAPI.progressUrl(dayId), {
                    method: 'PATCH',
                    body: { acknowledge_content: true },
                    ifMatch: revision,
                    create: revision === null
                }).then(function (result) {
                    if (result.ok) {
                        refreshOverall(result.data);
                        banner.hidden = true;
                        say('已复核新版内容');
                    } else {
                        say('复核失败，请重试', true);
                    }
                });
            });
        }

        var plannedToggle = $('[data-learning="planned-toggle"]', card);
        if (plannedToggle) {
            plannedToggle.addEventListener('change', function () {
                var target = plannedToggle.checked ? dayId : null;
                global.LearningAPI.apiFetch(global.LearningAPI.planUrl(), {
                    method: 'PUT',
                    body: { current_day_id: target }
                }).then(function (result) {
                    if (result.ok) {
                        say(plannedToggle.checked ? '已设为当前学习计划' : '已取消当前计划');
                    } else {
                        plannedToggle.checked = !plannedToggle.checked;
                        say('设置失败，请重试', true);
                    }
                });
            });
        }

        // 首次拉取 revision（用于 If-Match）。
        global.LearningAPI.apiFetch('/api/v1/me/progress/' + dayId + '/').then(function (result) {
            if (result.ok) refreshOverall(result.data);
        });
    }

    /* ---------------- 周/阶段/仪表盘状态刷新 ---------------- */

    function initDayStatusBadges() {
        var spans = $all('[data-day-status]:empty');
        if (!spans.length || !global.LearningAPI) return;
        global.LearningAPI.apiFetch(global.LearningAPI.dashboardUrl()).then(function (result) {
            if (!result.ok || !result.data || !result.data.summary) return;
            var states = result.data.summary.days || {};
            spans.forEach(function (span) {
                var dayId = span.getAttribute('data-day-status');
                var entry = states[dayId];
                if (entry && entry.overall) {
                    span.textContent = STATE_LABELS[entry.overall] || entry.overall;
                    span.className = 'learning-state learning-state-' + entry.overall;
                }
            });
        });
    }

    global.LearningProgress = {
        initDayTaskCard: initDayTaskCard,
        initDayStatusBadges: initDayStatusBadges,
        STATE_LABELS: STATE_LABELS
    };
})(window);
