# AI 芯片编译器开发学习计划

这是一个面向 AI 芯片编译器开发岗位的 **24 周、168 天每日学习计划**。

学习主线：

```text
Modern C++
  → 编译器 IR
  → MLIR
  → AI 计算图优化
  → Lowering 与 Tiling
  → LLVM 与 Runtime
  → 端到端项目与面试复盘
```

## 学习网站（动态 Web 应用）

本仓库包含一个基于 **Django + MySQL + Redis** 的动态学习网站（设计见
[docs/AI芯片编译器学习网站设计文档.md](./docs/AI芯片编译器学习网站设计文档.md)，
P0 实现说明见 [deploy/README.md](./deploy/README.md)）：

- 教程正文仍以 Git 为唯一权威源，通过 `import_tutorial` 命令原子导入为内容版本；
- 注册登录后，阅读/练习/实验/验收四项任务状态保存在 MySQL，支持跨设备恢复、
  revision 乐观锁（`If-Match`/412）、导出与导入（含替换前快照）；
- 服务端全文搜索支持中文二元词、命令与错误码，可按阶段/周/类型筛选；
- 每个有代码的日课提供确定性源码 ZIP（排除冻结输出与疑似密钥，保留执行权限）。

本地快速开始：

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# 准备 MySQL（库名 learning）与 Redis，然后在 config/settings/dev.py 配置连接
.venv/bin/python manage.py migrate
.venv/bin/python manage.py import_tutorial --commit HEAD   # 导入并激活 168 天内容
.venv/bin/python manage.py runserver                        # http://127.0.0.1:8000
```

测试：

```bash
# 单元/集成/验收（真实 MySQL）：106 个用例
.venv/bin/python manage.py test tests --settings=config.settings.test

# 浏览器 E2E + 无障碍（Playwright + Chromium，需 dev server 已启动）
node node_modules/playwright/cli.js test -c playwright.config.js
```

覆盖：内容导入与发布/回滚（TC-B/A05）、状态机、API 权限与并发（If-Match/412）、
导入导出回环、搜索、故障降级（MySQL/Redis/搜索不可用）、键盘可达、320px、
明暗主题与 axe-core critical/serious 违规清零。

## 文档

完整日程见：[AI芯片编译器学习计划.md](./AI芯片编译器学习计划.md)

每天都包含：

- **学习**：当天需要理解的概念或源码；
- **实践**：当天需要完成的编码或实验；
- **产出**：代码、测试、IR、性能数据或复盘笔记。

## 项目结构

```text
├── AI芯片编译器学习计划.md   # 168 天完整计划（权威来源）
├── tutorials/                # 每日教程（week-001～week-024，共 168 天）
│   └── day-NNN/
│       ├── README.md         # 当天完整教程
│       ├── images/           # 手绘 SVG 技术图（≥3 张/天）
│       └── code/             # 可运行代码 + outputs/ 冻结产物
├── skills/                   # 教程生成 Skill（模板 + 质量清单 + 工具）
├── apps/                     # Django 应用（content 导入/learning 进度/search 搜索/accounts 账号）
├── config/                   # Django 设置（base/dev/test/prod）与根路由
├── templates/                # 服务端页面模板
├── tests/                    # 测试套件（94 个用例）
├── deploy/                   # Nginx/Gunicorn 配置与运维手册
├── tools/                    # 工具脚本
│   └── cannbot_daily_tutorial.sh  # 每日教程自动生成
├── static/                   # 网站静态资源
└── public/                   # 构建产物（已 gitignore）
```

## 每日图文教程 Skill

仓库包含 `ai-compiler-daily-tutorial` Skill 源文件，用于把每日学习任务展开为通俗易懂、图文并茂的完整教程：

- [SKILL.md](./skills/ai-compiler-daily-tutorial/SKILL.md)：触发方式、生成流程和质量底线；
- [教程模板](./skills/ai-compiler-daily-tutorial/references/tutorial-template.md)：讲解、实践、图片、练习和验收结构；
- [质量清单](./skills/ai-compiler-daily-tutorial/references/quality-checklist.md)：通俗性、图片、代码和学习闭环检查；
- [计划提取与教程校验工具](./skills/ai-compiler-daily-tutorial/scripts/tutorial_tools.py)：提取指定日期，检查真实图片、占位内容和必要章节。

生成示例：

```text
使用 ai-compiler-daily-tutorial，根据学习计划生成第 45 天教程。
```

## 最终项目

以 `MatMul + Bias + ReLU` 为起点，完成一个端到端编译器：

```text
自定义 MLIR Dialect
  → Shape 推导／常量折叠／算子融合
  → 循环 IR
  → Tiling／循环交换／循环展开
  → LLVM IR
  → 生成并运行程序
  → 正确性验证＋性能分析
```

项目核心产出（第 18 周起）：

- **minic 统一编译入口**：一条命令从图 IR 到可执行（`tutorials/week-018/day-120` 起）；
- **Runtime 三件套**：特化分发 / 通用回退 / 缓冲池（`tutorials/week-019/day-127～day-133`）；
- **质量体系**：测试金字塔 / Pass 二分定位 / 性能回归（`tutorials/week-020/day-134～day-140`）；
- **五份项目文档**：架构 / Pass / Lowering / 测试 / 性能（`tutorials/week-023/day-155～day-159`）。

## 使用方式

1. 按第 001 天至第 168 天依次执行；
2. 每周第 6 天集中集成，第 7 天复盘验收；
3. 每个优化都回答"为什么语义不变、为什么可能更快、如何验证"；
4. 时间不足时优先保留代码、测试和复盘，不用删除正确性验证追赶进度。

## 开发环境

- **Python** ≥ 3.9（numpy 用于数值验证）
- **LLVM/MLIR 工具链**（mlir-opt / mlir-translate / llc / clang）——第 117 天起需要
- 各天的 `code/run_all.sh` 可一键复现当日全部实验
