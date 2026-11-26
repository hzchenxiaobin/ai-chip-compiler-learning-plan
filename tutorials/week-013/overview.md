第 13 周进入第四阶段，mini 编译器第一次跨方言：把图优化交付的干净 tensor 图（mini.matmul）翻译成硬件认识的循环与访存 IR，这一步叫 Lowering。它重要，因为图再干净也只是「做什么」的声明，硬件只认 load、store 与循环这份「怎么做」的操作卡。七天沿一条主线推进：第 85 天先不写代码，画施工图，列出类型、索引、输出初始化三张任务清单；第 86 天立骨架，用事务式 Rewriter 提交结构正确、计算留白的空 Pass；第 87～89 天逐块填肉：先给输出显式零起点，再钉死三重循环边界四要素，最后把 Load、Mul、Add、Store 填进循环体；第 90 天用形状矩阵与猎杀矩阵考验非方形与边界形状；第 91 天把六天的局部检查拼成语义保持的整体论证。最终产物是能跑、能验的 MatMul Lowering Pass，连同前后 IR 对照与正确性报告；第 14 周的 Tiling 将直接作用在这份循环 IR 上。

![第 13 周总览：从图 IR Lowering 到循环 IR。顶部三张卡点明问题与主线——图优化交付的干净 tensor 图硬件不认识、全周沿画施工图→立骨架→填三块肉→验牙齿→复盘推进、全周命题是语义保持拆成 S1～S6 六条款逐条验收；中部是核心翻译关系——左边图 IR（tensor 值语义的 mini.matmul 声明）经 DialectConversion 四角色（ConversionTarget 管合法性、TypeConverter 做 tensor 到 memref 的类型兑换、ConversionPattern 读源写目标、驱动器收敛或整体失败）下降为右边循环 IR（alloc＋三重循环＋load/mulf/addf/store 的命令式程序），下方标注填肉顺序与「形状是数据、IR 结构恒为 18 op」；底部七天推进条从 Day 85 画施工图走到 Day 91 复盘论证，收尾两卡列出全周产出（完整 MatMul Lowering Pass、前后 IR 对照与正确性报告、一页复盘）并衔接第 12 周图优化的交棒与第 14 周 Tiling 的循环 IR 输入](images/week-overview.svg)

> 第四阶段：Lowering、Tiling 与性能（第 85～112 天）

### 第 085 天｜设计 Lowering 路线

- **学习**：DialectConversion、TypeConverter、目标与源 Operation 的职责。
- **实践**：画出 `mini.matmul` 到循环表示的转换步骤，列出类型、索引和输出初始化任务。
- **产出**：Lowering 设计文档和测试计划。

### 第 086 天｜建立循环 Lowering 骨架

- **学习**：ConversionPattern、Rewriter 和转换失败处理。
- **实践**：创建 MatMul Lowering Pass，先完成匹配和骨架，不急于生成完整计算。
- **产出**：可运行的空 Lowering Pass 和诊断测试。

### 第 087 天｜生成输出初始化

- **学习**：累加器初始化、输出分配和内存语义。
- **实践**：为 MatMul 输出分配空间并初始化为零，处理动态维度的保守路径。
- **产出**：输出初始化 IR 和检查测试。

### 第 088 天｜生成三重循环

- **学习**：循环上界、下界、步长和 induction variable。
- **实践**：生成 `i/j/k` 三重循环，先支持静态 Shape。
- **产出**：循环 IR 和边界测试。

### 第 089 天｜生成 Load、Mul、Add、Store

- **学习**：多维索引到线性地址的映射、累加值读取与写回。
- **实践**：完成 MatMul 循环体，确保初始化、加载和存储位置正确。
- **产出**：完整 MatMul Lowering IR。

### 第 090 天｜支持非方形与边界 Shape

- **学习**：M、N、K 独立取值和小尺寸、维度为 1 等边界情况。
- **实践**：测试 `1×N`、`M×1`、小 K、非方形矩阵，修复索引和边界问题。
- **产出**：至少 8 组 Shape 测试和参考结果对照。

### 第 091 天｜第 13 周复盘

- **学习**：回顾图算子到循环实现的语义保持。
- **实践**：手画一个 `2×3` 乘 `3×2` 的循环与索引示例，对照生成 IR。
- **产出**：Lowering 前后 IR、正确性报告和一页复盘。
