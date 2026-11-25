/**
 * app.js —— 学习模块启动入口：按 data-page-type 分发。
 */
(function (global) {
    'use strict';

    function boot() {
        var pageType = document.body.getAttribute('data-page-type') || '';
        if (pageType === 'tutorial') {
            if (global.LearningProgress) global.LearningProgress.initDayTaskCard();
        } else if (pageType === 'week' || pageType === 'phase' || pageType === 'dashboard') {
            if (global.LearningProgress) global.LearningProgress.initDayStatusBadges();
        } else if (pageType === 'search') {
            if (global.LearningSearch) global.LearningSearch.initSearchEnhancement();
        } else if (pageType === 'settings') {
            if (global.LearningTransfer) global.LearningTransfer.initSettings();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})(window);
