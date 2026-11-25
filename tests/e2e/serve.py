#!/usr/bin/env python3
"""仅测试用的静态服务器：把 public/ 同时暴露在根路径与项目子路径。

用法：python3 tests/e2e/serve.py [public_dir] [port]

- 支持 /ai-chip-compiler-learning-plan/ 子路径（去掉前缀后落到同一目录）
- 继承 SimpleHTTPRequestHandler 的路径规范化，防目录穿越
- 加 no-store 头，避免测试期间缓存干扰
"""

import http.server
import os
import sys
import urllib.parse

PUBLIC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "public")
BASE_PREFIX = "/ai-chip-compiler-learning-plan"


class DualPrefixHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        path = urllib.parse.unquote(path)
        if path == BASE_PREFIX:
            path = "/"
        elif path.startswith(BASE_PREFIX + "/"):
            path = path[len(BASE_PREFIX) :] or "/"
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    os.chdir(PUBLIC)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), DualPrefixHandler)
    print(f"serving {PUBLIC} at http://127.0.0.1:{port}/ and http://127.0.0.1:{port}{BASE_PREFIX}/")
    server.serve_forever()
