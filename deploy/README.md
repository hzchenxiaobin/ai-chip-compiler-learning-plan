# 部署与运维手册（P0 动态学习站）

对应设计文档 §8.1、§9、§10.5。本手册面向部署与运维人员。

## 1. 架构与边界

```text
浏览器 ↔ Nginx(HTTPS) ↔ Gunicorn(Django WSGI)
                       ├── MySQL：内容读模型 + 学习数据（唯一权威源）
                       ├── Redis：缓存/限流（非权威，清空不丢数据）
                       └── 文件系统：公开资产(源码 ZIP/图片) + 私有文件(导出/快照)
```

- Git 是教程正文唯一权威源；MySQL 中的内容读模型可由同一 commit 完整重建。
- 个人学习数据只在 MySQL；备份策略必须覆盖 MySQL（见 §6）。
- 私有文件（导出、替换快照）不放入公开静态目录，通过短时签名 URL 下载。

## 2. 环境要求

- Ubuntu 24.04（或等价 Linux）
- Python 3.12（含 venv）、MySQL 8.x、Redis 7.x、Nginx
- 仓库检出路径示例：`/home/chenb/code/github/ai-chip-compiler-learning-plan`

## 3. 安装步骤

```bash
cd /home/chenb/code/github/ai-chip-compiler-learning-plan

# 1) 依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2) 数据库（root 执行）
mysql -e "CREATE DATABASE learning CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER 'learning'@'localhost' IDENTIFIED BY '<强密码>';"
mysql -e "GRANT ALL PRIVILEGES ON learning.* TO 'learning'@'localhost';"
mysql -e "GRANT ALL PRIVILEGES ON test_learning.* TO 'learning'@'localhost';"  # CI/测试用
mysql -e "FLUSH PRIVILEGES;"

# 3) 环境变量（写入 /etc/default/learning 或 systemd Environment=）
export DJANGO_SETTINGS_MODULE=config.settings.prod
export DJANGO_SECRET_KEY=<随机长字符串>
export DJANGO_ALLOWED_HOSTS=learn.example.com
export DB_NAME=learning
export DB_USER=learning
export DB_PASSWORD=<数据库密码>
export PRIVATE_SIGNING_KEY=<随机长字符串>
export REDIS_URL=redis://127.0.0.1:6379/0

# 4) 初始化
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput

# 5) 导入内容版本（原子发布）
.venv/bin/python manage.py import_tutorial --commit HEAD
# 导入 168 天 + 校验样例查询全部通过后自动激活；失败不会影响线上旧版本。

# 6) 启动
.venv/bin/gunicorn config.wsgi -c deploy/gunicorn.conf.py
sudo cp deploy/nginx.conf /etc/nginx/sites-available/learning.conf
sudo ln -s /etc/nginx/sites-available/learning.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 4. 内容发布与回滚

- 发布 = `import_tutorial --commit <新提交>`：构建 validating → ready →
  在单事务中切换 `SiteState.active_release`；旧 release 转 retired 并保留。
- 失败语义：任何解析/校验失败 → release 标记 failed、只保留诊断、
  不切换 active_release，线上版本不变。
- 回滚 = 重新激活旧 release（管理后台或 shell）：

```bash
.venv/bin/python manage.py shell -c "
from apps.content.models import ContentRelease, SiteState
r = ContentRelease.objects.get(commit='<旧提交>', config_version=1)
r.status = 'ready'; r.save()
from django.db import transaction
with transaction.atomic(): r.activate()
"
```

## 5. 冒烟检查（每次发布后）

- `GET /healthz` 返回 200 且 active_release 指向新提交
- `GET /`、`/tutorials/week-001/day-001/`、`/tutorials/week-005/day-029/`、
  `/weeks/week-1/`、`/phases/phase-1/`、`/plan/`、`/search/?q=MLIR` 全部 200
- `GET /api/v1/days/` 返回 168 天
- 登录后在 day-029 勾选任务 → 刷新状态保留；导出 JSON 可再次导入（unchanged）
- 下载一个源码 ZIP（如 `/assets/public/releases/<commit>/downloads/day-029-source.zip`）
- `GET /sitemap.xml`、`/robots.txt`、`/privacy/` 返回 200
- 停止 MySQL 后匿名已缓存页面仍可读（写入提示「未保存」）——故障降级演练
- 发布/回滚：`/admin/content/contentrelease/`（导入表单 + 每行激活/回滚按钮）
- 学习指标：`/admin/learning/auditevent/metrics/`

### 浏览器 E2E（发布前）

```bash
# 需要 Node 20 与 Chromium：
node node_modules/playwright/cli.js test -c playwright.config.js
# 含键盘可达、320px 无溢出、双主题、axe-core critical/serious 扫描
```

## 6. 备份与恢复

- MySQL 每日全量（`mysqldump --single-transaction learning`）+ binlog 保留，
  备份文件加密并异地存放。
- 定期恢复演练：在临时库恢复 → 起测试服务器 → 校验 /api/v1/days/ 与登录进度。
- 公开内容可随时从 Git 重建（`import_tutorial`）；私有导出/快照文件随目录备份。
- Redis 可随时清空，不影响数据正确性。

## 7. 故障处置

| 现象 | 优先检查 |
|---|---|
| 全站 503 “内容尚未发布” | active_release 是否存在；`import_tutorial` 是否成功 |
| 登录后写进度 500 | MySQL 连接/权限；日志中的异常 |
| 搜索无结果 | release 是否激活；posting 是否导入（导入日志有 postings 数量） |
| 图片/ZIP 404 | Nginx `location /assets/public/` 的 alias 路径；collectstatic |
| CSRF 失败页 | Cookie 域/Secure 配置；系统时间漂移 |

## 8. 安全清单

- [ ] 生产使用 `config.settings.prod`，全部秘密来自环境变量，不进 Git
- [ ] MySQL/Redis 不暴露公网；Gunicorn 只监听 127.0.0.1
- [ ] HTTPS 启用后开启 `SESSION_COOKIE_SECURE`/`SECURE_SSL_REDIRECT`
- [ ] 登录限流（Redis）生效；admin 路径限制来源
- [ ] 备份加密；日志不含 Cookie/令牌/完整笔记
