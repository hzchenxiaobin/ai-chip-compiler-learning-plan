# 第 30 天技术校对报告

校对环境与已核事实：在与教程声明一致的机器（Ubuntu 20.04 · aarch64 · LLVM 18.1.8，`mlir-opt-18`／`mlir-cpu-runner-18`）上于 `/tmp` 临时目录重放了当天全部实验：实验①round-trip 换名、②diff 为空、③generic form、④多结果 `%0:2`、⑤JIT 打印 `5`、⑥类型巡游（含 `offset: 0` 被省略）、5.4 qonly 打印 `3`，输出与 README 逐字一致；四个错误探针的报错文本、note 与 exit 码（均为 1）全部复现；命名作用域探针（两个函数重名相安无事）复现通过。练习与选做预测已代跑验证：`%seventeen` 改名 `%magic` 后输出不变、`17` 改 `23` 后 JIT 打印 `7`、`offset: 2` 确会被打印、`%0:3` 与子标 `%0#2` 写法合法；直接把未 lower 的文件喂给 runner 报 `Dialect 'func' not found for custom op 'func.func'`，与“runner 不认 func 方言”的说法相符。Day 4／9／10／11／12／17／25／29／31／32／33／45 等跨日引用与总计划核对一致。涉及机制处已查 MLIR 18.1.8 官方源码（`mlir/lib/AsmParser/Parser.cpp`、`mlir/include/mlir/Dialect/Func/IR/FuncOps.td`）与官方文档（LangRef、Builtin dialect、FuncOps.td）。三张 SVG 均为有效 XML，图中数值、报错文本与真实输出一致。以下为发现的问题。

## 【错误】

#### 1. “名字作用域是块级的”——SSA 名字作用域实际是 region（隔离作用域）级，同函数跨块重名即报错
- **原文**：“- **一个常见误解**："两个函数里都叫 %a 会撞名。"不会——名字作用域是块级的。`probe.sh` 里的命名作用域探针实测：两个函数各自用 `%x` 和 `%a`，相安无事。”
- **依据**：本机实测（mlir-opt-18）三个反例：同一函数两个相邻块各定义一次 `%v`（`cf.br` 分隔）报 `error: redefinition of SSA value '%v'`（note 指向第一个块里的定义）；嵌套 region 内重用外层同名值同样报 redefinition；块参数与 op 结果同名（函数参数 `%x` 后再 `%x = arith.constant`）也报 redefinition。MLIR 18.1.8 LangRef 明确写 “Value identifiers are only in scope for the (nested) region in which they are defined”；解析器源码 `Parser.cpp` 的名字作用域按 region 压栈（`parseRegionBody` → `pushSSANameScope`，`parseBlock` 不压栈）。两个函数互不冲突的真正原因是 `FuncOp` 带 `IsolatedFromAbove` trait（FuncOps.td），每个函数体是一个独立名字作用域。初学者若按“块级”理解在多块函数里重用名字，会撞上教程未解释的 redefinition 报错。
- **置信度**：高（三条对照实验＋LangRef 原文＋解析器源码互相印证；“两个函数不冲突”这一结论本身正确，错的是给出的机制解释）。

#### 2. “方言名在无歧义时可以省略”不是 MLIR 的通用规则
- **原文**：“三个阅读要点：**(a)** 注释在 round-trip 后会消失——注释是文本层的，不属于 IR，所以这份标注要靠文件本身保存；**(b)** `arith.maxsi` 是"取两者较大值"（signed max），标量 ReLU 恰好是 `max(x, 0)`；**(c)** `return` 是 `func.return` 的简写（方言名在无歧义时可以省略），读 IR 时两种写法都会遇到。”
- **依据**：本机实测（mlir-opt-18）：函数体内写裸 `addi` 报 `error: custom op 'addi' is unknown (tried 'func.addi' as well)`，裸 `br` 同样报错（只尝试了 `func.` 前缀，`cf.br` 根本不被尝试）——即使 `arith.addi` 在已注册方言中无歧义也不解析。真实机制见 18.1.8 源码：`FuncOp` 显式实现 `OpAsmOpInterface::getDefaultDialect()` 返回 `"func"`（FuncOps.td 注释 “Allow the dialect prefix to be omitted”），解析器（Parser.cpp `parseCustomOperationName`）只把无前缀 op 名补上“当前默认方言”再查找。省写只对 func 方言的 op 在 `func.func` 体内这少数场合成立，与“无歧义”无关。初学者按此规则写 `addi`/`br` 会得到教程未解释的报错。
- **置信度**：高（两个反例实测＋FuncOps.td／Parser.cpp 源码逐行核对；`return`／`call` 可省写本身属实，错在机制描述）。

#### 3. "`arith.addi` …属性和 Region 为空"与教程自己的实验③真实输出矛盾
- **原文**：“- **一个最小例子**：`%sum = arith.addi %x, %b : i32`——名字 `arith.addi`，操作数 `%x`、`%b`，结果 `%sum`，属性和 Region 为空。”
- **依据**：教程 5.3 实验③贴出的本机真实 generic form 第三行就是 `%1 = "arith.addi"(%arg0, %arg1) <{overflowFlags = #arith.overflow<none>}> : (i32, i32) -> i32`（本次重放逐字一致）：`arith.addi` 携带固有属性 `overflowFlags`（默认值 `none`）。按教程自己给“属性”下的口径（`arith.constant` 的 `value`、`func.func` 的 `sym_name`／`function_type` 都算属性），addi 的属性并不为空，只有 Region 为空；本例里属性、Region 双空的其实是 `arith.maxsi`（`"arith.maxsi"(%1, %0) : (i32, i32) -> i32`）。该句与本篇自己的真实输出直接矛盾，会让读者对“五件套”的属性一栏产生错误预期。
- **置信度**：高（教程内真实输出直接可证，无需外部资料；`overflowFlags` 属固有属性、经 properties 槽位打印，详见存疑 1）。

## 【存疑】

#### 1. generic form 的 `<{...}>` 槽位在 MLIR 18 里正式名称是 properties，与“属性”混称需留意版本差异
- **原文**：“这就是图 2 的文字版，五件套版式对每条 op 都成立：**圆括号里是操作数，尖括号 `{}` 里是属性，冒号后是类型签名，`(...)` 大括号包着的是 Region**。四个一眼可见的事实：`"builtin.module"` 和 `"func.func"` 都是 Operation（嵌套关系打出来了）；`arith.constant` 的 0 在属性 `value = 0 : i32` 里、圆括号是空的（无操作数）；`func.return` 的签名是 `(i32) -> ()`（只读不写）；`^bb0(%arg0: i32, %arg1: i32):` 是块头——`%x`、`%b` 的真正定义者，Day 31 的主角提前露脸。”
- **依据**：LangRef（18.1.8）的 generic-operation 文法为 `string-literal `(` value-use-list? `)` successor-list? dictionary-properties? region-list? dictionary-attribute? `:` function-type`，其中 `dictionary-properties ::= `<` dictionary-attribute `>`——教程示例里的 `<{value = 0 : i32}>`、`<{overflowFlags = …}>`、`<{function_type = …, sym_name = …}>` 打的都是 properties（固有属性）槽位；可丢弃属性则以裸 `{...}` 打印且条目名必须带方言前缀。把这些一律称为“属性”在读本篇示例时不产生错误结论（它们确实是固有属性），但读者后续查文档会遇到 Properties 这个独立概念；另外“尖括号 `{}`”把尖括号与花括号两种记号写在一起，初读者不易对应到实际打印的 `<{...}>`。建议 Day 32 展开 Type/Attribute 时点名 properties 与可丢弃属性字典的区分，并把该句的记号写准（`(...)`＝操作数、`<{...}>`＝属性、`:` 后＝类型签名、`({...})`＝Region 列表）。
- **置信度**：高（LangRef 文法＋本机输出核对；归入存疑是因为“属性”作统称在本篇不产生错误结论，属术语粒度与版本演进问题）。

#### 2. “index …循环下标专用”过于绝对
- **原文**：“- **沿用一个例子看类型家族**（`probe.sh` 实验⑥真实解析）：`i32`（整数）、`f32`（浮点）、`index`（宽度与目标相关的整数，循环下标专用）、`tensor<2x3xf32>`（逻辑形状＋元素类型）、`memref<2x3xf32, strided<[3, 1]>>`（还带物理布局）。**Day 4 的 TensorDesc（Shape/Dtype/Stride 三件套）在这里对上号**：tensor 描述逻辑形状，memref 连物理 stride 一起管。深挖留给 Day 32。”
- **依据**：官方 Builtin dialect 文档对 index 类型的定义是 “The index type is a signless integer whose size is equal to the natural machine word of the target … and is used by the affine constructs in MLIR”，rationale 是 “integers of platform-specific bit widths are practical to express sizes, dimensionalities and subscripts”——即尺寸、维度、下标都可用，并非只能用于循环下标（memref 维度、张量尺寸、affine 下标同样常为 index）。“宽度与目标相关”这一半准确；“专用”宜改为“常用于”，另可顺带说明 index 是 signless（不带符号性标记）。
- **置信度**：高（官方文档原文核对；属过度限定而非机制错误）。

## 【建议】

#### 1. “先定义后使用”实际有两种报错形态，建议补上支配检查那条
- **原文**：“原因：使用先于定义（或根本没有定义）；MLIR 的普通块内不允许前向引用。”
- **依据**：本机实测（mlir-opt-18）：`%a` 先用后定义（`%r = arith.addi %a, %x` 在前、`%a = arith.constant 1 : i32` 在后）并不报 “use of undeclared SSA value name”，而是解析通过、在验证层报 `error: operand #0 does not dominate this use`（附 `note: operand defined here (op in the same block)`）。即“名字从未定义”才走解析层的 undeclared 报错；“名字晚定义”走的是 SSA 支配检查，发生在验证层。初学者顺手一试前向引用看到的正是这条教程未覆盖的报错，建议第 6 节补一句“定义出现在使用之后 → operand does not dominate this use”，把四条铁律与真实报错对得更齐。
- **置信度**：高（实测复现；“普通块内不允许前向引用”作为结果性陈述不算错，属报错形态覆盖不全）。

#### 2. “Day 10 手写的 addUse/removeUse”与第 10 天教程的实际内容对不上
- **原文**：“- **一个类比**：快递单——"取件货架"和"放回货架"。**对应到技术上是**：Operand 在数据结构上是对某个 SSA 值的一次**使用**（use），登记在被用值的 **use-list** 里——你 Day 10 手写的 `addUse`/`removeUse` 的工业版；Result 不是"值"这个名字，而是值的一种具体形态（**OpResult**），挂在这一端成为**定义**。Day 45 的"把使用者替换到新值"，做的就是把 use-list 里那些登记项成批改指到新结果上。**类比的边界**：快递单引用货架，但操作数引用的是"值本身"——替换操作改的是引用的指向，不会把值复制一份过来。”
- **依据**：第 10 天的 `mini-graph-v3` 全部源码与 README 里没有任何 `addUse`／`removeUse`（全仓库 tutorials 内这两个词只出现在本天 README 与 `code/concept-map.md`）：第 10 天的实际做法是 `Value::uses_` 账本＋登记发生在 `make_node` 内部，改写接口叫 `replace_all_uses_of` 与 `erase_node`。按“手写的 addUse/removeUse”回看第 10 天会找不到对应物；建议改为“你 Day 10 在 `Value::uses_` 账本里做过的登记与迁移”的工业版（`code/concept-map.md` 对照表里 “addUse / removeUse（Day 10）”一行同此问题）。
- **置信度**：高（day-010 目录全文检索；属跨日引用名称不准确，不影响本天 MLIR 技术内容的正确性）。
