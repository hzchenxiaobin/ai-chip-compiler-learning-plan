# 第 30 天概念对照表：自制编译器 ↔ MLIR

> 学习计划第一阶段（Day 1～28）自己造的零件，在 MLIR 里的工业版叫什么。
> 每一行都能用 `tutorials/day-030/code/` 里的文件或 `--mlir-print-op-generic` 亲眼验证。

| 第一阶段（自制） | MLIR 里的名字 | 关键差异 |
|---|---|---|
| Node / 算子节点（Day 8～9） | **Operation** | MLIR 里一切都是 Operation：`arith.addi` 是，`module`、`func.func` 也是（generic form 可证） |
| Value（Day 8） | **SSA Value** | 值的统称，只有两种具体形态：OpResult（操作产出）和 BlockArgument（块的参数） |
| Node 的输入指针（Day 8） | **Operand** | 一次「使用」（use）：指向某个 SSA 值，登记进它的 use-list |
| addUse / removeUse（Day 10） | use-list（`Value` 的使用者链表） | 替换使用者时 MLIR 用 `replaceAllUsesWith` 一类接口成批迁移 |
| 节点输出端口（Day 9） | **OpResult** | 一条 op 可有 0 / 1 / N 个结果（`%q, %r = func.call ...`） |
| 函数入参 | **BlockArgument** | 不是任何 op 的结果，由所在块直接定义（Day 31 展开） |
| Dtype / Shape / Stride（Day 4 TensorDesc） | **Type**（`i32`、`tensor<2x3xf32>`、`memref<2x3xf32, strided<[3, 1]>>`…） | 每个 SSA 值恰好一个类型；tensor 描述逻辑形状，memref 还带物理布局 |
| 算子属性（Day 9） | **Attribute**（如 `value = 0 : i32`） | 编译期常量，不是 SSA 值，不能当操作数读 |
| Verifier（Day 12） | **Parser + Verifier** 双闸 | 解析层拦 `use of undeclared SSA value name`；验证层拦 `func.return op has 2 operands ...` |
| 打印器 + Visitor（Day 11） | **Printer 双形态**：pretty / generic | generic 形态剥掉全部语法糖，五件套（名字/操作数/属性/Region/结果）一目了然 |

## 用主例 bias_relu 验证对照

`bias_relu.mlir` 全函数：**5 个定义**（%x、%b、%c0、%sum、%r）、**5 次使用**、**每个值恰好一个类型**（全部 i32）：

| 值 | 定义方式 | 定义者 | 使用者 | 类型 |
|---|---|---|---|---|
| %x | BlockArgument | 函数入口块 | arith.addi | i32 |
| %b | BlockArgument | 函数入口块 | arith.addi | i32 |
| %c0 | OpResult | arith.constant | arith.maxsi | i32 |
| %sum | OpResult | arith.addi | arith.maxsi | i32 |
| %r | OpResult | arith.maxsi | func.return | i32 |

## 副例 divmod 验证「N 个结果」

`divmod.mlir` 的 main 里，一条 `func.call` 同时定义两个值；打印时合用一组编号（`%0:2`），用子标区分（`%0#0`、`%0#1`）：

| 值 | 定义方式 | 定义者 | 使用者 |
|---|---|---|---|
| %q（调用后为 %0#0） | OpResult 之一 | func.call（一次产 2 个） | arith.addi / func.return |
| %r（调用后为 %0#1） | OpResult 之二 | func.call（同一条 op） | arith.addi（qonly 版里无人使用——合法） |
