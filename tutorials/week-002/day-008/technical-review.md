# 第 8 天技术校对报告

校对环境：与教程声明一致（Linux aarch64 · Ubuntu 20.04 · g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0）。已在本机临时目录完整复跑：Debug／ASan 双构建、`mini-graph`、`test_graph`（44 条断言双绿）、`ctest`（0.00 s／3.27 s）、三个 bugs 反面教材（含 `err_copy_graph` 的编译期报错），输出与 README 记录逐行核对一致；`make_unique`＋private 构造的报错信息已单独复现。对 MLIR／ONNX／V8 的论断查证了官方文档与源码（出处见各条）。

## 【错误】

#### 1. 图 2 给 Node 标注的“不可拷贝原因”错误：Node 没有 unique_ptr 成员

- **原文**：“右上两个蓝盒子——`Node` 与 `Value`，成员里清一色裸指针借用，拷贝全部 ✗”
- **依据**：README 第 101 行（图 2 解读段），对应 images/02-graph-node-value-ownership.svg 中 Node 盒子下方的一行“拷贝 ✗（unique_ptr 成员连带删除）”。`Node` 的成员是 `int64_t id_`、`string kind_`、`vector<const Value*> inputs_`、`const Value* result_`，没有任何 `unique_ptr` 成员；它的拷贝被禁止是源码里显式写的 `Node(const Node&) = delete;`（src/Node.h:13，Value 同理见 src/Value.h:13）。“unique_ptr 成员连带删除”这个理由只对 `Graph` 成立（src/Graph.h:19 显式删除，且 `values_`／`nodes_` 的 `unique_ptr` 成员本来也会连带删除）。图 2 把 Graph 的理由安到了 Node 头上，读者按图推理“Node 里有 unique_ptr”会得到与源码相反的结论；另外 README 说两个蓝盒子都标了“拷贝 ✗”，但 SVG 里只有 Node 一处（Value 盒子没有该标注）。本条是图内文字错误，修复只需改 SVG 标注（如“拷贝 ✗（显式 = delete）”）。
- **置信度**：高（源码与 SVG 文字逐字核对）。

#### 2. 第 6 节错误一／错误三的示意代码按字面运行不会触发所描述的 ASan 报告

- **原文**：“first->id;                             // 悬空”
- **依据**：README 第 6 节错误一代码块（第 343 行）；错误三代码块的“leaked->kind();              // 悬空”（第 382 行）是同一问题。这两行都是丢弃值表达式（discarded-value expression）。按 C++ 语义，非 volatile 泛左值被丢弃时不发生左值到右值转换，编译器不会为 `first->id;` 生成内存读取；`leaked->kind();` 调用的 `kind()` 只返回 `const string&`，同样不读对象内容。本机实测（g++ 9.4.0，`-fsanitize=address -static-libasan`，默认无优化，与教程命令一致）：按字面复现的两个最小程序均正常退出、ASan 零报告；而仓库真实 bugs 文件能报 `heap-use-after-free`，是因为 `printf("%lld", first->id)`／`printf("%s", leaked->kind().c_str())` 真正发生了读取（两处均已复现并与 README 输出一致）。悬空指针的使用确实是未定义行为，但“是 UB”不等于“ASan 必报”——初学者照敲示意代码会看到“什么都没发生”，与本节“ASan 报 heap-use-after-free／当场被抓”的现象描述相矛盾。建议把示意行改成真正发生读取的形式（如 `std::printf("%lld\n", first->id);`）。
- **置信度**：高（语言规则＋本机实测；不确定点：不同编译器／优化级别可能生成不同代码，但在教程自己给出的命令与 g++ 9.4 默认设置下实测不报）。

## 【存疑】

#### 1. “MLIR 的 operand 就是对 Value 的引用，没有独立 Edge 实体”表述过于绝对

- **原文**：“MLIR 里 Operation 的 operand（操作数）就是对 Value 的引用，没有独立 Edge 实体”
- **依据**：README 第 82 行。两侧都查证过。支持教程的方面：MLIR LangRef 原文写明 “MLIR is fundamentally based on a graph-like data structure of nodes, called Operations, and edges, called Values”（https://mlir.llvm.org/docs/LangRef/）——官方文档自己把 Value 称作边，“值即边”的设计与 MLIR 的概念模型一致。需要保留的方面：MLIR 的 C++ 实现里，每个操作数槽位是一个 `OpOperand` 对象（mlir/include/mlir/IR/Value.h，`class OpOperand : public IROperand<OpOperand, Value>`，注释 “This class represents an operand of an operation. Instances of this class contain a reference to a specific Value”），Value 借助它维护 use-list——“用”侧的边是有实体的，而这恰是第 10 天 Use-Def 要引入的机制。同段对 TurboFan 的论断也核对了 V8 源码：src/compiler/node.h 确有 `class Edge final`（“An encapsulation for information associated with a single use of a node as an input from another node”），NodeProperties 提供 `IsValueEdge`／`IsEffectEdge`／`IsControlEdge`——“边有控制／数据／效果之分”属实；但 `Edge` 是包着 `Use` 记录的轻量包装，边的种类按输入位置（value→context→frame state→effect→control 的布局）和 Operator 的输入计数推导，并不是每条边上存的“类型标签”，“边是一等对象”的说法偏强。建议把“没有独立 Edge 实体”改成“没有可独立持有的 Edge IR 对象（‘用’的一侧到第 10 天才实体化）”，避免读者日后读 MLIR 源码时困惑。
- **置信度**：中（“过于绝对”的定性判断；MLIR 与 V8 两处源码／文档均已核对）。

## 【建议】

#### 1. 实验二“加一行”实际是两行

- **原文**：“在 `main.cpp` 里加一行（我临时改了一份做实验）”
- **依据**：README 第 295 行。紧随其后的代码块是两行（`add_node` 与 `mark_output`），且展示的输出 “(2 inputs, 2 outputs)” 与 “output %w” 依赖第二行。本机实测：只加 `add_node` 不加 `mark_output` 时，输出是 “(2 inputs, 1 outputs)” 且没有 “output %w” 行，与 README 记录不符；两行都加则逐行一致。建议改为“加两行”。
- **置信度**：高（复现验证）。

#### 2. “加起来不到 40 行”按文件行数口径不成立

- **原文**：“两个函数的完整实现都在仓库 `Graph.cpp` 里，加起来不到 40 行”
- **依据**：README 第 205 行。`topological_order` 占 src/Graph.cpp 第 51–72 行、`to_string` 占第 74–95 行，合计 44 行（含空行、注释与大括号）；只数有效语句约 35 行。按读者最容易去核对的“文件行数”口径，“不到 40 行”不成立。建议改成“40 行出头”或“不到 50 行”。
- **置信度**：高（行数客观可数；严重度低）。

#### 3. Graph.h 公开接口清单遗漏 `nodes()` 与移动赋值

- **原文**：“`Graph.h` 的公开接口按学习目标分三件事——构造（`add_input`／`add_node`／`mark_output`）、观察（`name`／`num_values`／`num_nodes`／`inputs`／`outputs`）、遍历（`topological_order`／`to_string`）：”
- **依据**：README 第 142 行。实际 Graph.h 的公开成员还有 `const std::vector<std::unique_ptr<Node>>& nodes() const noexcept`（src/Graph.h:39，观察类）和 `Graph& operator=(Graph&&) noexcept = default`（src/Graph.h:22，移动赋值）；教程代码块以“公开接口”的名义呈现却未注明是节选。建议注明节选，或把这两项补进清单，避免读者对照源码时以为看漏了。
- **置信度**：高（源码核对；不影响正确性）。

#### 4. images/03-experiment-results.svg 的 `unique_ptr` 名单漏画指向 `%b` 的所有权箭头

- **原文**：“Graph 手里的 `unique_ptr` 名单扩容时只搬名单”
- **依据**：README 5.4 节图 3 的图注（第 326 行），文件 images/03-experiment-results.svg。SVG 左板画了 `%a`／`%b`／`%t`／`%y` 四个值盒，但“unique_ptr 名单”盒子只引出 3 条箭头（按坐标核对分别落在 `%a`、`%t`、`%y` 三个盒子的范围内），`%b` 没有所有权箭头；说明文字写“每个值／节点”，而节点（n0、n1）在左板也没有画出。这与 5.3 节真实输出“Graph 拥有 4 个 Value、2 个 Node”不一致。建议补第 4 条箭头（或注明“只画部分”）。
- **置信度**：高（SVG 坐标逐条核对）。

#### 5. “add_node 的三步”与代码注释的步数编号不一致

- **原文**：“`Graph.cpp` 里最核心的是 `add_node` 的三步——顺序就是设计：”
- **依据**：README 第 175 行。紧随其后的代码注释只编号了两步（“1) 先造结果值，再造节点……”“2) 节点借用结果、结果回指生产者……”），入库（`push_back`）与返回没有编号。文字说“三步”、代码标两步，初学者数不出第三步。建议把注释补成 1)／2)／3)（第三步＝入库登记），或把文字改为“两步”。
- **置信度**：高（客观不一致；严重度低）。
