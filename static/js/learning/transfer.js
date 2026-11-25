/**
 * transfer.js —— 设置页渐进增强：危险操作二次确认与导入进度提示。
 * 所有操作均有服务端表单基础路径；本模块只增强体验。
 */
(function (global) {
    'use strict';

    function initSettings() {
        document.querySelectorAll('form[data-confirm]').forEach(function (form) {
            form.addEventListener('submit', function (event) {
                if (!window.confirm(form.getAttribute('data-confirm'))) {
                    event.preventDefault();
                }
            });
        });

        var fileInput = document.getElementById('import-file');
        if (fileInput) {
            fileInput.addEventListener('change', function () {
                var file = fileInput.files && fileInput.files[0];
                if (!file) return;
                if (file.size > 5 * 1024 * 1024) {
                    window.alert('文件超过 5 MiB 上限，请选择更小的备份文件。');
                    fileInput.value = '';
                } else if (file.name && !/\.json$/i.test(file.name)) {
                    window.alert('请选择 .json 备份文件。');
                    fileInput.value = '';
                }
            });
        }
    }

    global.LearningTransfer = { initSettings: initSettings };
})(window);
