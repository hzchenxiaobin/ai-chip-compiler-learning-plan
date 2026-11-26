> 第二阶段：MLIR 核心能力（第 29～56 天）

### 第 043 天｜Shape Inference 接口

- **学习**：Shape 推导的输入、输出和失败语义；理解静态维度与动态维度传播。
- **实践**：为 MatMul 设计输出 Shape 推导规则，先写测试样例再写代码。
- **产出**：Shape 推导规则表和测试清单。

### 第 044 天｜实现 MatMul Shape 推导

- **学习**：部分静态 Shape、未知维度和结果类型更新。
- **实践**：实现静态 MatMul 输出 Shape 推导，保留无法确定的动态维度。
- **产出**：Shape Inference 代码和静态／动态测试。

### 第 045 天｜第一个 RewritePattern

- **学习**：Pattern 匹配、Rewriter、替换与擦除 Operation。
- **实践**：实现 `Relu(Relu(x)) → Relu(x)`，确保使用者被正确替换。
- **产出**：Canonicalization Pattern 和 `FileCheck` 测试。

### 第 046 天｜代数化简 Pattern

- **学习**：常量匹配、属性读取和 Pattern 的收益前提。
- **实践**：实现 `Add(x, 0) → x` 或当前类型系统允许的安全代数化简。
- **产出**：Pattern、正例、反例和优化前后 IR。

### 第 047 天｜常量折叠

- **学习**：Folder、Canonicalization 和常量物化之间的关系。
- **实践**：对支持的标量或小型 Tensor 常量执行 Add 折叠；限制过大 Tensor 的编译期展开。
- **产出**：Fold 实现、边界测试和编译期开销说明。

### 第 048 天｜组合运行优化 Pass

- **学习**：Canonicalizer 的迭代执行、Pattern 冲突和不动点。
- **实践**：组合 Shape 推导、Relu 消除、代数化简和 Fold，观察多轮优化后的稳定 IR。
- **产出**：Pass 管道、组合测试和 IR 对照。

### 第 049 天｜第 7 周复盘

- **学习**：总结 Shape Inference、Fold 和 RewritePattern 的不同职责。
- **实践**：构造一个必须连续执行两种 Pattern 才能完全优化的用例。
- **产出**：组合用例及复盘；能回答“为什么一次 Pattern 遍历不一定得到最简 IR”。
