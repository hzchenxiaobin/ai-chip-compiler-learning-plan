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
