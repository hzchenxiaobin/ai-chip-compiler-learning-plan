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

## 在线阅读（GitHub Pages）

网站由 `tools/build.py` 从 `tutorials/` 静态构建，推送到 `main` 分支后由
GitHub Actions 自动发布到 GitHub Pages：

**https://hzchenxiaobin.github.io/ai-chip-compiler-learning-plan/**

本地预览：

```bash
python3 tools/build.py                                  # 生成 public/ 静态站
python3 -m http.server 8000 --directory public          # http://127.0.0.1:8000
```

## 文档

完整日程见：[AI芯片编译器学习计划.md](./AI芯片编译器学习计划.md)

每天都包含：

- **学习**：当天需要理解的概念或源码；
- **实践**：当天必须动手完成的编码或实验；
- **产出**：代码、测试、IR、性能数据或复盘笔记。

## 项目结构

```text
├── AI芯片编译器学习计划.md   # 168 天完整计划（权威来源）
├── tutorials/                # 每周概览与每日教程（week-001～week-024，共 168 天）
│   ├── overview.md           # 完整周计划（可含周首总结与总览图引用）
│   ├── images/               # 周总览 SVG
│   └── day-NNN/
│       ├── README.md         # 当天完整教程
│       ├── images/           # 手绘 SVG 技术图（≥3 张/天）
│       └── code/             # 可运行代码 + outputs/ 冻结产物
├── skills/                   # 教程生成 Skill（模板 + 质量清单 + 工具）
├── tools/                    # 构建与生成脚本
│   ├── build.py              # GitHub Pages 静态站构建
│   ├── cannbot_daily_tutorial.sh  # 每日教程自动生成
│   └── cannbot_weekly_overview.sh # 每周概览自动生成
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

## 每周概览生成

周计划页的完整正文直接保存在 `tutorials/week-NNN/overview.md`，包括阶段说明和七天的
学习、实践、产出；构建脚本只读取该文件，不再从总计划动态拼接正文。文件开头还可包含
一段总结和一张技术总览图，图片位于 `tutorials/week-NNN/images/week-overview.svg`。
生成工具只补充总结和总览图，并保留已有周计划正文。

使用 cannbot 串行补全所有周，或只处理指定周：

```bash
tools/cannbot_weekly_overview.sh       # 第 1～24 周，已完成且通过校验的周会跳过
tools/cannbot_weekly_overview.sh 1     # 只处理第 1 周
```

脚本每周独立校验并运行整站构建，失败时默认重试 3 次，日志写入
`build/cannbot_weekly_overview/`。可通过 `MAX_ATTEMPTS` 调整重试次数；可信环境中可设置
`CANNBOT_AUTO_APPROVE=1` 自动批准 cannbot 工具权限。

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
