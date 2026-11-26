第 7 周让上周的 mini 方言从“能验证”进化到“会优化”。第 43～44 天先解决结果类型要人手写的问题：为 matmul 设计 Shape 推导规则并翻译成 C++，新的 -mini-infer-shape 只把结果类型里的 ? 细化成数字，补信息、不动图，也绝不发明或改写已有数字；第 45～47 天让 IR 第一次变小：Relu(Relu(x)) 塌缩、Add(x, -0.0) 与 Mul(x, 1.0) 代数化简、常量碰常量直接折出结果，这些规则不另写 Pass，而是挂在算子身上，交给现成的 -canonicalize 驱动反复迭代；第 48 天把四种能力组合成一条管道，用对照实验看清执行顺序与不动点如何决定优化存亡；第 49 天复盘收口：Shape 推导补信息、Fold 只算值、RewritePattern 改结构，三种机制互相制造机会、缺一不可。一周下来，mini-opt 学会自己补类型、自己瘦身，也为下周的算子融合备好重写机制。

![第 7 周总览：顶部 mini-opt 流水线在解析与验证之后新增两格——-mini-infer-shape 补信息和 -canonicalize 缩 IR；中部三张机制卡分别是独立 Pass 的 Shape 推导（只补 ? 不动图）、挂在算子上的 RewritePattern（认形状改结构）与 Fold（只算值不碰图）；下方三步接力链展示 fold 折出常量 1.0 解锁乘一塌缩、再解锁双 Relu 消除；底部五段七天推进从规则表、C++ Pass、三条化简规则、组合管道到复盘，衔接第 6 周的方言定义与第 8 周的算子融合](images/week-overview.svg)

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
