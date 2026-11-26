第 6 周从“读懂 MLIR”跨到“动手造方言”：不改动 LLVM 一行源码，亲手搭一个叫 mini 的方言，给最终项目 MatMul＋Bias＋ReLU 安家。七天沿一条主线推进：第 36 天建起独立工程，把空方言注册进自制工具 mini-opt；第 37～38 天用 ODS 在 .td 表里定义 matmul、add、relu、constant 四个算子，交给 mlir-tblgen 自动生成解析、打印与约束代码；第 39～40 天接下 ODS 管不了的跨值关系，手写 Verifier 查内维匹配与 shape 一致，让报错学会说人话；第 41 天把算子、验证、Pass 注册首尾相连，端到端 IR 在 mini-opt 里跑通 round-trip；第 42 天复盘，独立新增第五个算子 mini.mul。本周收获五个算子、两层验证的 mini 方言工程和一个自制工具，更是“新增算子只改注册数据、不改工具代码”的扩展能力，也是下周 Shape 推导与图优化的地基。

![第 6 周总览：左侧生产线把 MiniOps.td 经 mlir-tblgen 生成 .inc、加手写 Verifier 编译链接成 mini-opt；右侧 mini-opt 内部一条 .mlir 过解析、两层验证（ODS 约束在前、手写 verify() 在后）、打印与 Pass 三道关卡，靠方言和 Pass 两张注册表认人；目标图 MatMul→Add→Relu 与 constant、mul 五个算子；底部七天从建工程、ODS 填表、手写 Verifier、端到端 IR 到复盘新增 mini.mul，衔接第 5 周读 IR 与第 7 周 Shape 推导](images/week-overview.svg)

> 第二阶段：MLIR 核心能力（第 29～56 天）

### 第 036 天｜创建独立 Dialect 工程

- **学习**：了解 Standalone 工程结构、TableGen 生成代码和构建依赖。
- **实践**：创建 `mini` Dialect，注册最基础的 Dialect 信息。
- **产出**：可构建、可被 `mini-opt` 加载的空 Dialect。

### 第 037 天｜定义 MatMul

- **学习**：ODS 中 Operation 名称、参数、结果、约束和描述的定义方式。
- **实践**：定义 `mini.matmul`，包含两个输入、一个结果和 Tensor 类型。
- **产出**：MatMul Operation 和解析、打印测试。

### 第 038 天｜定义 Add、Relu 和 Constant

- **学习**：逐元素算子、无副作用算子和常量属性的表示。
- **实践**：增加 `mini.add`、`mini.relu`、`mini.constant`，补充必要约束。
- **产出**：三个 Operation 及对应 IR 测试。

### 第 039 天｜实现 MatMul Verifier

- **学习**：Verifier 与 ODS 约束的分工，错误诊断的位置和质量。
- **实践**：检查 MatMul 的秩、内维匹配和输出 Shape；对动态维度采取保守处理。
- **产出**：MatMul Verifier 和至少 6 个合法性测试。

### 第 040 天｜实现 Add 与 Relu Verifier

- **学习**：Elementwise 类型约束、Shape 一致性和后续 Broadcast 扩展边界。
- **实践**：当前先支持完全一致的 Shape，明确拒绝暂不支持的情况。
- **产出**：Verifier、错误诊断和反例测试。

### 第 041 天｜构造第一张 mini IR

- **学习**：Pass 注册和命令行工具如何识别自定义 Dialect。
- **实践**：编写 `MatMul → Add → Relu` 的 MLIR，用自定义工具完成解析、验证和打印。
- **产出**：端到端 IR 示例、`mini-opt` 命令和测试脚本。

### 第 042 天｜第 6 周复盘

- **学习**：回顾 ODS、生成代码、Verifier 和 Pass 工具的关系。
- **实践**：新增一个 `mini.mul`，独立完成定义、构建和合法性测试。
- **产出**：新增算子及复盘；能回答“哪些约束放 ODS，哪些放 Verifier”。
