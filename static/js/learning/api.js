/**
 * api.js —— 学习模块 API 核心（fetch + CSRF + If-Match）。
 * 所有写操作走同源 Session＋CSRF；412 返回服务端当前记录。
 */
(function (global) {
    'use strict';

    function readCookie(name) {
        var parts = document.cookie.split(/;\s*/);
        for (var i = 0; i < parts.length; i++) {
            var pair = parts[i].split('=');
            if (pair[0] === name) return decodeURIComponent(pair[1] || '');
        }
        return null;
    }

    function csrfToken() {
        return readCookie('csrftoken') || '';
    }

    /**
     * 请求 JSON API。
     * 返回 Promise<{ ok, status, data }>；412 时 data.current 为服务端当前版本。
     */
    function apiFetch(path, options) {
        options = options || {};
        var headers = {
            'Accept': 'application/json',
            'X-CSRFToken': csrfToken()
        };
        if (options.body !== undefined) {
            headers['Content-Type'] = 'application/json';
        }
        if (options.ifMatch !== undefined && options.ifMatch !== null) {
            headers['If-Match'] = '"' + options.ifMatch + '"';
        } else if (options.create) {
            headers['If-None-Match'] = '*';
        }
        return fetch(path, {
            method: options.method || 'GET',
            headers: headers,
            credentials: 'same-origin',
            body: options.body !== undefined ? JSON.stringify(options.body) : undefined
        }).then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, status: response.status, data: data };
            }).catch(function () {
                return { ok: response.ok, status: response.status, data: {} };
            });
        });
    }

    global.LearningAPI = {
        apiFetch: apiFetch,
        csrfToken: csrfToken,
        progressUrl: function (dayId) {
            return '/api/v1/me/progress/' + dayId + '/update/';
        },
        planUrl: function () { return '/api/v1/me/plan/'; },
        dashboardUrl: function () { return '/api/v1/me/dashboard/'; },
        searchUrl: function () { return '/api/v1/search/'; }
    };
})(window);
