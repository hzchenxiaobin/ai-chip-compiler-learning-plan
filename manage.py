#!/usr/bin/env python3
"""Django 管理入口。

用法示例：
    python manage.py import_tutorial --commit <40位提交>     # 导入并激活内容版本
    python manage.py runserver                              # 本地开发服务器
"""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "无法导入 Django。请先创建并激活虚拟环境："
            "python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
