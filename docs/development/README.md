# AI 芯片编译器学习网站：详细开发文档

> 文档版本：`DEV-2026-11-25-v3`（动态网站架构）  
> 适用仓库：`hzchenxiaobin/ai-chip-compiler-learning-plan`  
> 内容分析提交：`53b62f1c84223bb6ca466bb8177921ccd5d8ef72`  
> 上游基线：最新版建设指南与《AI芯片编译器学习网站设计文档》V2.0

## 1. 文档包用途

本套文档把 `FR-001`—`FR-015` 和 28 个基础验收用例拆解为工程任务：P0 对应 `WP-01`—`WP-07`，P1/P2 对应 `WP-08`—`WP-16`。动态化调整保留需求和工作包编号，但替换旧的静态站与本地存储实现契约。

- 网站是 **Django 动态应用＋MySQL**，不使用 GitHub Pages 托管。
- Markdown/Git 是教程唯一内容权威源；MySQL 内容表是可重建读模型，不提供第二套正文编辑器。
- 公开教程免登录阅读；保存进度、导入数据和管理私密材料必须登录。
- MySQL 是账号与学习记录权威源；Redis 只用于缓存、限流和 Celery 任务。
- localStorage 只保存轻量 UI 偏好；P0 不使用 IndexedDB 保存业务数据。
- 日课 URL 保持 `/tutorials/week-NNN/day-NNN/`，生产采用独立域名根路径。
- 首版不执行学习者代码；L2、AI 和 L3 后续分别评审、分权部署。

## 2. 阅读顺序与职责分工

| 文档 | 主要读者 | 动态架构内容 | 工作包 |
|---|---|---|---|
| [01_构建与内容契约.md](01_构建与内容契约.md) | 内容、后端 | 168 天解析、MySQL 内容版本、原子激活、源码 ZIP、搜索读模型 | WP-01、02、05 |
| [02_前端学习模块.md](02_前端学习模块.md) | 前端、后端 | API 客户端、会话/CSRF、状态机、revision、搜索与服务端导入导出 | WP-03、04、05、06 |
| [03_页面集成与交互.md](03_页面集成与交互.md) | 前端、设计、后端 | Django 模板、动态路由、匿名/登录状态、并发与异常交互 | WP-03—06 |
| [04_数据证据与后续迭代.md](04_数据证据与后续迭代.md) | 后端、CI、安全 | MySQL Schema、迁移、证据、L2、项目档案和可选离线边界 | P1/P2 |
| [05_测试发布与运维.md](05_测试发布与运维.md) | 测试、SRE、安全 | MySQL/Redis 集成测试、E2E、Nginx、迁移、备份、监控和回滚 | WP-07 |
| [06_工作包拆解与追踪.md](06_工作包拆解与追踪.md) | 项目负责人 | P0 49 项任务、依赖和 28 用例追踪 | WP-01—07 |
| [07_P1自测复习与卡点开发.md](07_P1自测复习与卡点开发.md) | 内容、前后端 | 题包导入、MySQL 扩展、自测、复习和卡点 | WP-08、09 |
| [08_P1证据导入与本地脚本开发.md](08_P1证据导入与本地脚本开发.md) | 后端、工具链 | 证据上传、私有暂存、哈希、性能和本地脚本 | WP-10 |
| [09_P1_L2CI复验开发.md](09_P1_L2CI复验开发.md) | CI、后端、安全 | 受信工作流、artifact、服务端 attestation | WP-11 |
| [10_P1项目档案与可选同步开发.md](10_P1项目档案与可选同步开发.md) | 前后端、隐私 | 项目档案、可选离线 outbox 与冲突恢复；文件名仅为兼容保留 | WP-12、13 |
| [11_P2社区教师反馈与学习小组开发.md](11_P2社区教师反馈与学习小组开发.md) | 后端、治理 | 公开讨论、私密反馈、cohort 字段级共享 | WP-14 |
| [12_P2_AI助教开发.md](12_P2_AI助教开发.md) | AI、后端、安全 | RAG、真实引用、隐私、预算与熔断 | WP-15 |
| [13_P2_隔离远程实验开发.md](13_P2_隔离远程实验开发.md) | 平台、安全 | microVM、私有测试、L3、配额与销毁 | WP-16 |
| [14_P1P2工作包与验收追踪.md](14_P1P2工作包与验收追踪.md) | 项目负责人 | P1/P2 72 项任务、迁移顺序和发布门禁 | WP-08—16 |

P0 顺序为 WP-01→WP-02/WP-03→WP-04/WP-05→WP-06→WP-07。P1 先完成 WP-08，再并行 WP-09/WP-10，之后 WP-11/WP-12；WP-13 仅在真实离线需求下启动。P2 不捆绑上线。

## 3. 范围基线

### 3.1 P0 必须交付

1. Django、MySQL、Redis、Nginx 和对象存储开发/测试/生产配置。
2. 指定 commit 的 168 天内容导入、完整校验、active_release 原子切换和回滚。
3. 注册、登录、退出、会话撤销、CSRF、行级权限和受控管理后台。
4. 动态首页、日课、周/阶段、搜索、我的学习和设置页。
5. MySQL 四任务状态、当前计划、继续学习、内容复核和跨设备恢复。
6. 版本化源码 ZIP、公开/私有对象存储分离和 GitHub 深链。
7. 服务端中文与技术 token 搜索、筛选、分页和真实锚点。
8. 导出、完整预检、合并/替换、替换前快照、删除学习数据与账号。
9. 响应式、无障碍、CI、迁移、备份恢复、监控、冒烟和回滚。

### 3.2 P0 明确不交付

- 公开社区、排行榜、远程编译、结构化自测、复习、证据上传和项目档案。
- 离线编辑与浏览器业务副本；原生 App、支付和强制锁课。
- 为未启用能力提前创建无调用方的微服务；L3 不与 Web 共用执行权限。

### 3.3 P1/P2 入口

P1 复用主站账号和 MySQL，不再新增“可选账号同步”。WP-13 只负责可选离线编辑、outbox 与冲突恢复。L2 必须有独立验证记录；L3 必须有平台强隔离和私有测试。P2 的社区、教师、AI、Lab 分别设置 feature flag。

## 4. 目标工程目录

```text
ai-chip-compiler-learning-plan/
├── config/                     # Django settings、根 URL、ASGI/WSGI
├── apps/
│   ├── content/                # release/day/version/chunk、导入、发布
│   ├── accounts/               # 用户、会话策略、账号生命周期
│   ├── learning/               # plan/progress/task、导出导入
│   ├── search/                 # token/posting、查询服务
│   ├── evidence/               # P1 证据与证明引用
│   ├── review/                 # P1 自测、复习、卡点
│   └── portfolio/              # P1 项目档案
├── templates/                  # base、首页、日课、周/阶段、设置等
├── static/
│   ├── js/vp-solution.js       # 现有正文交互，继续复用
│   └── js/learning/            # api/progress/search/transfer 等
├── tools/
│   ├── build.py                # 可选薄兼容入口，不再发布 Pages
│   └── learning_evidence.py    # P1 本地证据脚本
├── services/
│   ├── verification/           # P1 L2 worker，可独立部署
│   ├── ai-gateway/             # P2 独立
│   └── lab/                    # P2 独立强隔离
├── schemas/                    # 导入导出、题包、证据等版本化 Schema
├── tests/                      # content/unit/api/e2e/security/deployment
├── deploy/                     # Nginx、Compose/系统服务、迁移与冒烟
└── tutorials/                  # Markdown、图片、代码和 outputs 权威源
```

生产仍不需要 Node.js；Node 只用于前端单元测试和 Playwright。应用依赖、前端测试依赖和部署配置均锁定版本。

## 5. 全局接口与命名约定

### 5.1 标识、时间和字符集

- 日课 `day-001`—`day-168`，周 `week-001`—`week-024`，阶段 `phase-1`—`phase-6`。
- 数据库主键使用 BIGINT/UUID 之一并全局一致；对外学习标识使用稳定业务 ID，不暴露顺序主键遍历接口。
- 时间戳统一 RFC 3339 UTC；MySQL 连接和 Django 时区使用 UTC。
- MySQL 使用 InnoDB、utf8mb4、严格模式；`content_sha/evidence_hash` 为 64 位小写 SHA-256。

### 5.2 URL、认证和并发

所有站内 URL 用 Django `{% url %}` 或 `reverse()` 生成，不设置 Pages `base_path`。公开资源由 Nginx/对象存储提供；私有文件必须经授权和短时签名 URL。

同源浏览器写请求使用 Session Cookie＋CSRF＋Origin 检查。进度、计划和后续可变实体采用整记录 revision＋`If-Match`；版本不匹配返回 412 和当前服务端记录，业务冲突返回 409。禁止字段级时间戳拼接。

### 5.3 错误分类

| 错误码 | 含义 | 用户行为 |
|---|---|---|
| `AUTH_REQUIRED` | 需要登录 | 保留当前操作意图，登录后返回 |
| `SESSION_EXPIRED` | 会话过期 | 保留未提交表单，重新认证 |
| `PERMISSION_DENIED` | 非资源所有者或角色不足 | 不泄露资源是否存在 |
| `STORAGE_UNAVAILABLE` | MySQL 等权威存储不可用 | 明示未保存，公开缓存可读 |
| `REVISION_CONFLICT` | If-Match 版本过旧 | 返回当前记录，等待重试或选择 |
| `DATA_SCHEMA_INVALID` | 导入字段不合法 | 整批拒绝并定位字段 |
| `DATA_VERSION_UNSUPPORTED` | 主版本不支持 | 不猜测迁移 |
| `SEARCH_UNAVAILABLE` | 搜索查询失败 | 可重试，不伪装无结果 |
| `CONTENT_RELEASE_NOT_READY` | 内容版本未通过校验 | 禁止激活 |

## 6. 变更控制

可直接修改不改变外部契约的函数内部实现、CSS 命名和测试 fixture。以下变更必须评审：日课 URL、任务状态、revision 语义、MySQL 表/迁移、导出与证据 Schema、内容哈希输入、权限模型、生产依赖和远程执行边界。

建议提交顺序：`dynamic-skeleton`、`content-import`、`auth-pages`、`server-progress`、`server-search`、`data-transfer`、`deployment-hardening`。每个提交可独立测试，不提交数据库文件、私有导出或生成的大型对象存储内容。

## 7. 分阶段完成定义

### 7.1 P0 完成

- WP-01—WP-07 全部关闭，FR-001—FR-009 与 26 个 P0 用例有证据。
- 干净环境可启动真实 MySQL/Redis 依赖并完成 168 天导入。
- 注册、登录、退出、跨设备恢复、越权拒绝和 revision 冲突通过。
- 所有动态深链经 Nginx 可刷新，无 Pages 或 base path 依赖。
- 导入失败不切换 active_release；迁移/测试/冒烟失败不切换生产流量。
- MySQL 备份恢复和 Redis 清空演练通过；失败写入不冒充成功。

### 7.2 P1 核心完成

- WP-08—WP-12 准出，FR-010—FR-013 和 TC-F13/F14 有测试映射。
- MySQL expand→migrate→contract 使用旧版备份/fixture，升级不丢数据。
- 复习 `[1,7,28]`、先答后看、卡点历史与日课验收边界正确。
- 证据声明/有效级别分离；L2 需要匹配的有效 attestation。
- 项目档案默认服务端私密，不公开个人代码和笔记。

### 7.3 可选离线与 P2 完成

- WP-13 开启时才验收 outbox、412 冲突、删除 tombstone 和恢复幂等；未开启不阻塞 P1。
- WP-14 的公开讨论、私密反馈和 cohort 权限分别准出。
- WP-15 提交 golden、引用、拒答、防注入、隐私和成本证据。
- WP-16 提交强隔离、私有测试、销毁、独立 L3 签名和灰度证据。
- 任一外部能力关闭，公开教程和已保存的在线学习数据仍可读取。
