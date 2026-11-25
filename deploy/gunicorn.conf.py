# Gunicorn 配置（设计文档 §9.1：仅监听内网，由 Nginx 转发）。
#
# 启动：
#   .venv/bin/gunicorn config.wsgi -c deploy/gunicorn.conf.py

bind = "127.0.0.1:8000"
workers = 3
threads = 2
timeout = 60
graceful_timeout = 30
keepalive = 5
max_requests = 2000
max_requests_jitter = 200
accesslog = "-"
errorlog = "-"
loglevel = "info"
forwarded_allow_ips = "127.0.0.1"
