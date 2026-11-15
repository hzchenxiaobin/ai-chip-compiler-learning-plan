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

## 文档

完整日程见：[AI芯片编译器学习计划.md](./AI芯片编译器学习计划.md)

每天都包含：

- **学习**：当天需要理解的概念或源码；
- **实践**：当天需要完成的编码或实验；
- **产出**：代码、测试、IR、性能数据或复盘笔记。

## 项目结构

```text
├── AI芯片编译器学习计划.md   # 168 天完整计划（权威来源）
├── tutorials/                # 每日教程（168 个目录）
│   └── day-NNN/
│       ├── README.md         # 当天完整教程
│       ├── images/           # 手绘 SVG 技术图（≥3 张/天）
│       └── code/             # 可运行代码 + outputs/ 冻结产物
├── skills/                   # 教程生成 Skill（模板 + 质量清单 + 工具）
├── tools/                    # 构建与生成脚本
│   ├── build.py              # GitHub Pages 静态站构建
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

- **minic 统一编译入口**：一条命令从图 IR 到可执行（`tutorials/day-120` 起）；
- **Runtime 三件套**：特化分发 / 通用回退 / 缓冲池（`tutorials/day-127~133`）；
- **质量体系**：测试金字塔 / Pass 二分定位 / 性能回归（`tutorials/day-134~140`）；
- **五份项目文档**：架构 / Pass / Lowering / 测试 / 性能（`tutorials/day-155~159`）。

## 使用方式

1. 按第 001 天至第 168 天依次执行；
2. 每周第 6 天集中集成，第 7 天复盘验收；
3. 每个优化都回答"为什么语义不变、为什么可能更快、如何验证"；
4. 时间不足时优先保留代码、测试和复盘，不用删除正确性验证追赶进度。

## 开发环境

- **Python** ≥ 3.9（numpy 用于数值验证）
- **LLVM/MLIR 工具链**（mlir-opt / mlir-translate / llc / clang）——第 117 天起需要
- 各天的 `code/run_all.sh` 可一键复现当日全部实验
