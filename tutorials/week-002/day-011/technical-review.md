# 第 11 天技术校对报告

> 审阅范围：`tutorials/week-002/day-011/README.md`、`examples/mini-graph-v4/` 全部源码与测试、`experiments/what-breaks.log` 冻结输出、`images/` 下 3 张 SVG。
> 核验环境（与正文声明一致）：Linux aarch64 · Ubuntu 20.04 · g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0。所有可运行内容均在临时目录复跑，未改动仓库冻结产物。
> 总体结论：代码可三构建全绿（Debug/ASan/UBSan，71＋44 条断言逐条复现），v3→v4“输出一字不差”经实际 diff 证实，两个 bugs 反面教材与 what-breaks 实验（13 条警告、13 个编译错误）均可完整复现且与冻结日志一致；未发现虚构数据。以下为逐条校对意见。

## 【错误】

#### 1. 3.4 节结论把本项目的设计说反了：不是“每种算子一个类”
- **原文**：“当前项目每种算子一个类、运行期才拿到节点、访问者会越来越多”
- **依据**：本工程恰恰是“一个 Node 类 ＋ OpKind 枚举、不为每种算子派生子类”：`src/OpKind.h` 注释明写“枚举是「一个类 + kind + 属性」路线的一部分：不为每种算子派生子类”；README 3.1 节自己也写“我们的 `Node` 是「一个类 ＋ kind 枚举」（第 9 天的决策），没有 `accept` 可用”；第 9 节总结再次写“「一个类 + kind」的我们用不上它（CRTP）”。若“每种算子一个类”为真，经典双分派 Visitor（数据方提供虚函数 `accept`）就可用，3.1 节“没有 accept 可用、于是用 switch 完成第一重分派”的整段论证将不成立。此句应改为“当前项目不为每种算子派生类（一个 Node 类＋kind 枚举）”之类的表述。
- **置信度**：高（与同文三处表述及全部源码直接矛盾，源码已逐文件核对）。

## 【存疑】

#### 1. “MLIR walk／LLVM InstVisitor 遍历只读”的类比过于绝对
- **原文**：“对照 MLIR 的 `Operation::walk` 和 LLVM 的 `InstVisitor`，"遍历只读、修改走 Rewriter"是同一个分工。”
- **依据**：查 llvm-project 官方源码（main 分支 `mlir/include/mlir/IR/Operation.h`）：`Operation` 确为 `final` 且无虚函数（正文 3.1/3.3 这点正确），但 `Operation::walk` 是非 const 成员，回调签名形如 `void(Operation*)`（可变指针），且头文件注释明确允许“A callback on a block or operation is allowed to erase that block or operation”（post-order 或擦除后跳过时）；`llvm/include/llvm/IR/InstVisitor.h` 的各 `visitXXX` 方法同样接收非 const 的 `Instruction&`。即两者都不是“只读遍历”，准确的说法是：MLIR 在模式重写场景要求结构性修改走 `PatternRewriter`（这是一条真实存在的分工，但与“walk 只读”不同）。本教程自己的 `const Node&` 接口比 MLIR 更严格，类比方向合理，但“遍历只读”三个字对外部框架 API 而言失实，建议弱化为“结构性修改应走 Rewriter”。
- **置信度**：高（外部 API 事实已对照官方源码核实；不确定点仅在于作者本意是讲“重写纪律”还是“walk 的 API 约束，故列存疑而非错误）。

## 【建议】

#### 1. “一次虚调用贵 1～2 ns”未限定构建类型，与同段 Debug 数据对不上
- **原文**：“按绝对值说，一次虚调用贵 1～2 ns；一次 Pass 遍历几百到几万个节点，总代价在微秒级——对编译器完全无感。”
- **依据**：同段刚给出的 Debug 差值是 36.17−28.65 = 7.52 ns/次，只有 Release 差值（8.05−6.95 = 1.10 ns）落在“1～2 ns”。本机同环境复测（取 3 轮最优）：Debug 差约 6.7 ns、Release 差约 1.05 ns，与正文两组数值一致，即规律真实、但“1～2 ns”只对 Release 成立。图 3 图注（“一次虚调用差 1～2 ns”）与第 9 节总结（“每次贵 1～2 ns”）同样未限定。建议补一句“（Release 下；未优化的 Debug 差距约 7 ns）”，避免读者拿 Debug 数字验算时困惑。
- **置信度**：高。

#### 2. “4 个漏改的类”按类名计数，被点名的类定义实为 5 处；7(b) 的提示也偏少
- **原文**：“这次构建**失败**：**13 个编译错误**逐个点名 4 个漏改的类——`NodeLinePrinter`（Graph.cpp）、`OpCardPrinter`、`CounterVisitor`、`RecordingVisitor`（test_visitor.cpp）”
- **依据**：复跑 `experiments/what-breaks-when-adding-mul.sh`（与仓库冻结日志逐条一致）：13 个 `error: cannot declare variable ... to be of abstract type` 分别指向 main.cpp 的 `OpCardPrinter`、`CounterVisitor`，test_visitor.cpp 的 `RecordingVisitor`、`OpCardPrinter`、`CounterVisitor`，以及 Graph.cpp 的 `NodeLinePrinter`。其中 `CounterVisitor` 在 main.cpp 与 test_visitor.cpp 各定义一次（两个匿名命名空间中的同名类，都被点名），按类定义计是 5 处、按类名去重才是 4 个；类名列表也未标注 `OpCardPrinter`／`CounterVisitor` 在 tests 里同样被点名。第 7 节练习 (b) 的提示“不止 `src/` 里两个，`tests/` 里也有”同样偏少——src/ 下被点名的有 3 处（Graph.cpp 的 NodeLinePrinter、main.cpp 的 OpCardPrinter 与 CounterVisitor）。做“预测 vs 实际点名”清单的学生会数出与提示不一致的结果。建议改为“按类名 4 个、按定义 5 处（CounterVisitor 在 main.cpp 与 test 各一份）”。
- **置信度**：高（对冻结日志逐条核对并复跑验证）。

#### 3. “Graph 原样”与改动二自相矛盾
- **原文**：“由第 10 天的 v3 复制而来（`Value`／`Node`／`Graph`／`Interpreter` 原样），机制上的改动是下文的三处”
- **依据**：与 day-010 的 v3 逐文件 diff：`Value.h`、`Node.h`、`Interpreter.h/.cpp`、`OpKind.h`、`Attrs.h`、`TensorType.h`、`Dtype.h`、`tests/test_use_def.cpp` 逐字节相同（“原样”对它们成立），但 `Graph.cpp` 新增了 `NodeVisitor.h` 包含和 `NodeLinePrinter` 类并重写了 `to_string()`，`Graph.h` 头部注释也有改动——Graph 正是“改动二”的落点，5.1 文件树也把 Graph.h/Graph.cpp 标为 ★。把 Graph 列进“原样”清单与后文自相矛盾，建议从括号中去掉 Graph，或改写成“对外行为原样（机制改动仅三处）”。
- **置信度**：高（diff 验证）。

#### 4. 图 2 图注“全工程唯一的分发 switch”口径过宽，与 5.4 实验自身矛盾
- **原文**：“中卡是 `apply_visitor`，全工程唯一的分发 `switch`，**故意不写 `default`**”
- **依据**：`Interpreter::run`（src/Interpreter.cpp:37）和 `bench_switch`（src/bench.cpp:18）同样是“按 kind 选动作”的 switch；5.4 步骤 1 的 13 条 `-Wswitch` 警告里，`Interpreter::run`、`bench_switch` 各占 1 条，正说明工程里按 kind 分发的 switch 不止 `apply_visitor` 一处。准确口径是正文第 4 节第 1 点的表述：“`kind → visit_xxx` 的对应关系只写在 `apply_visitor` 一处”。另外 `src/NodeVisitor.h` 的注释也写了“整个工程只有这一个 switch 负责「按算子类型选动作」的分发”（README 5.2 引用该文件时恰好删去了这句），图注宜采用同样的收窄表述。
- **置信度**：高。

#### 5. 第 1 节把“节点消失、输出全 0”的演示错挂在 5.4 节名下
- **原文**：“今天 5.4 节的实验会真实演示漏改的后果：节点从 IR 里悄悄消失，解释器静默输出全 0”
- **依据**：5.4 节的两个实验都不产生可运行程序里的“节点消失／全 0”：实验一（what-breaks-when-adding-mul.sh）演示的是编译期 13 条警告与 13 个编译错误（步骤 1/2 均未链接出带漏改的二进制），实验二是计时。能真实复现“节点行消失、`?%n0`、静默全 0”的是 `bugs/err_unhandled_kind.cpp`，属第 6 节内容，图 3 左卡也把它标注为“bugs/ 可复现”。建议把括号里的指引改为“今天第 6 节的 bugs 反面教材（图 3 左卡）会真实演示”。
- **置信度**：中（现象本身真实且已复现，仅归属章节指引不准；若作者把 5.4 连同其图 3 的引用算作“5.4 节”，则可勉强自洽）。

#### 6. 接口里的虚析构函数出现但全文未解释，漏了 Visitor 模式的一个经典坑
- **原文**：“virtual ~NodeVisitor() = default;”
- **依据**：这是接口中唯一的非纯虚成员，作用是保证“经由 `NodeVisitor*` 删除派生类对象”时调用正确的析构函数——漏写它正是 Visitor 模式的经典 UB 坑。本工程所有访问者都是栈对象，未触发该坑；但初学者照这个接口自写 visitor、改用 `new`/`unique_ptr<NodeVisitor>` 管理生命周期时就会踩到，且正文 3.1、5.2 对这一行为只字未提。鉴于本报告任务要求检查“是否遗漏初学者必知的关键坑”，建议在 5.2 补一句说明它为什么存在。
- **置信度**：中（坑的真实性为高；是否列为“当天必知”属教学取舍）。

#### 7. 5.2 改动二的代码摘录按字面敲入得不到正确输出
- **原文**：“std::string text = "graph \"" + name_ + "\" (" /* 头部与输入表，同 v3 */;”
- **依据**：真实实现（src/Graph.cpp:289-306）里这一行还要拼接 inputs/outputs 计数，其后还有一个遍历 `inputs_` 的 for 循环；摘录用行内注释把这两段一并省略，且省略标记嵌在字符串字面量语句中间，逐字照抄的初学者会得到 `graph "matmul-bias-relu" (` 这样的残缺输出且不易察觉差异来源。5.1 已给出完整工程路径，影响有限；建议完整给出这个仅约 17 行的函数，或把省略说明独立成一行注释。
- **置信度**：中（属可改进的表达问题，不影响机制讲解的正确性）。
