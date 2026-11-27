# 第 10 天技术校对报告

校对环境与已核事实：在与教程声明一致的机器（Linux aarch64 · Ubuntu 20.04 · g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0）上于临时目录重新构建并运行了 mini-graph-v3 的 Debug／ASan／UBSan 三构建、`mini-graph-v3` 主程序三幕、71 条断言测试与三个 bugs 反面教材：主程序三幕输出、测试结果（71 条、13 组、三构建全绿、ASan 约 3.3 秒）、bugs 异常消息均与 README 逐字一致；第一／二／三幕全部数值手算核对无误（C=[[58,64],[139,154]]、D=Y=[[116,128],[278,308]]、第三幕 Y=[[68,84],[169,194]] 等）；v2→v3 的文件差异与“第 9 天原样复制＋三处改动＋一处计划外 bug 修复”的声明相符（Dtype／TensorType／OpKind／Attrs／Interpreter 逐字节相同，Node 仅注释变化，v2 的 `topological_order` 确为按 id 下标的 `vector<char>`）；MLIR／LLVM 对照已查官方 Doxygen（`mlir::Value`、`mlir::RewriterBase`、`llvm::Value`）。三张 SVG 均为有效 XML，图中账本、数值与真实输出一致。以下为发现的问题。

## 【错误】

#### 1. `replace_all_uses_of`“先拷贝再遍历”给出的迭代失效理由不成立
- **原文**：“边遍历边改 from->uses_ 就是「迭代中修改容器」，会漏记录。”
- **依据**：循环体只做两件事：写 `u.user->inputs_[u.operand]`（Node 的成员，不触碰 `from->uses_`）和 `mutable_value(to)->uses_.push_back(u)`（至多重分配 `to->uses_` 自己的缓冲）。函数开头 `require(from != to)`（Graph.cpp:136）已排除两个指针指向同一 Value，因此 `to->uses_` 与 `from->uses_` 是两个不同对象的成员 vector，push_back 不可能使 `from->uses_` 的迭代器失效；`from->uses_` 在整个循环中从未被修改（只在循环结束后才 `clear()`），所述“迭代中修改容器、会漏记录”的机制不存在。实测验证：删掉 `moved` 拷贝、直接遍历 `from->uses_` 的版本在 Debug／ASan／UBSan 三构建下 71 条断言全部通过；对注释描述的“to 的生产者节点就是 from 的使用者”等三个场景，与原版输出逐位一致且 `use_def_consistent()` 保持。真正会踩“迭代中修改容器”的写法是边遍历边从 `from->uses_` 中删除记录、或允许 `to == from`，两者在本代码中都不出现。先拷贝本身是无害的防御性写法，问题在于把它归因于一个不存在的失效机制——该理由还进入第 8 节验收清单（“`replace_all_uses_of` 为什么先拷贝账本再遍历”）成为学习点，会让初学者记错 C++ 规则（误以为“往另一个 vector push_back 会使本 vector 的迭代器失效”）。
- **置信度**：高（源码路径分析＋三构建全套测试＋针对性对照实验互相印证；拷贝与不拷贝两版行为无差异）。

#### 2. “ASan 也未必抓得住”与对该 bug 的实测结果矛盾
- **原文**：“ASan 也未必抓得住这种"读到了垃圾值"的越界”
- **依据**：把 v2 的 `std::vector<char> visited`（按节点 id 做下标）回植到 v3 并以 `-DENABLE_ASAN=ON` 构建运行，第二幕 `erase_node(mm2)` 之后解释器重算处稳定触发 `AddressSanitizer: heap-buffer-overflow ... READ of size 1 ... 0 bytes to the right of 3-byte region`，连续 4 次运行 4 次命中，栈顶正是 `topological_order` 中的 `visited[n->id()]`，调用点为 main.cpp:113 的解释器 run。该越界是紧贴 3 字节堆分配末尾的 1 字节读，恰好落在 ASan 红区，属于 ASan 最可靠捕捉的 bug 类别；“读到垃圾值而不报错”只发生在没有 ASan 的普通构建（malloc 粒度余量）里。按原文指引排查，初学者会在最该开 ASan 的场景跳过 ASan，属于方向性误导。若作者本意是“越界读落在分配粒度内读到了旧值抓不住”，那描述的是非 ASan 构建的行为，与本例（越界 1 字节即入红区）不符。
- **置信度**：高（本机可稳定复现并给出精确报告；不排除作者当时以其它构建方式运行形成误判，但“未必抓得住”作为一般性论断不成立）。

#### 3. 越界读的下标与数组长度跟所述故障现场对不上
- **原文**：“`visited[4]` 在长度 4 的数组上**越界读**”
- **依据**：第二幕的故障现场：`erase_node(mm2)` 后剩余节点 id 为 0、2、3，`num_nodes()` 为 3，v2 代码 `visited(num_nodes())` 的长度是 3；relu 的 id 是 3，越界发生在 `visited[3]`（上一条实测的 ASan 报告亦显示“3 字节区域右侧 1 字节读”）。第二幕不存在 id 为 4 的节点；且若数组真是长度 4，`visited[3]` 反而在界内且为零初始化，relu 不可能被“误判为已访问”，与原文随后描述的失败模式自相矛盾。“下标 4／长度 4”这组数字恰好吻合第三幕（erase bias3 后剩 id 1、2、3、4，`num_nodes()`=4，bias_new 的 `visited[4]` 越界），疑似两幕的数字互串。建议按第二幕改为“`visited[3]` 在长度 3 的数组上越界读”。
- **置信度**：高（第二幕结论有源码推演＋ASan 实测双重支持；第三幕推演未单独运行，但其节点与 id 计数可由源码直接得出）。

#### 4. “经典图初始账本（16 条）”分组计数错误
- **原文**：“经典图初始账本（16 条）”
- **依据**：`tests/test_use_def.cpp` 第 1 组（注释“---- 1. 初始账本：经典图的每条 use 都登记在册”）实际包含 20 条 CHECK：num_values、num_nodes、%A／%B／%bias／%C／%D／%Y 六个值各 num_uses 与 user／operand 逐条核对（共 14 条）、`!relu->result()->has_uses()`、`e.a->has_uses()`、`use_def_consistent(e.graph)` 等，脚本分组计数与人工逐条核对均为 20。总数 71 与“13 组”的表述属实（程序自打印 “all 71 assertions passed”），仅此处分组计数不符。
- **置信度**：高（分组脚本计数＋人工核对＋程序自打印总数三方一致）。

#### 5. `uses_to_string()` 并没有“又写一遍 switch (kind)”
- **原文**：“今天 `uses_to_string()` 里又写了一遍 `switch (kind)`”
- **依据**：v3 全部源码中带 switch 的位置只有三处文件：`OpKind.h` 的 `op_name()`（第 9 天已有）、`Interpreter.cpp::run()`（`switch (n->kind())`）和 `Dtype.h`（两个 dtype switch）；`Graph.cpp`（含 `uses_to_string()`）一行 switch 都没有，它调用的是 `op_name(u.user->kind())`。因此“每新增一种算子所有 switch 都要跟着改”对 `uses_to_string()` 不成立——新增算子时它无需任何修改。第 11 天教程自己也把这件事准确表述为“又把『kind 转成名字』的逻辑借了一遍 `op_name()`”，与本句直接矛盾；本句疑为把“新增了一个 kind 分发的调用点”误写成“又写了一遍 switch”。
- **置信度**：高（grep 全源码＋与已发布的第 11 天教程原文交叉对照）。

## 【存疑】

#### 1. MLIR Rewriter 的方法名 `replaceUses` 并不存在
- **原文**：“MLIR 的 Rewriter 也是这两步（`replaceUses ＋ eraseOp`）”
- **依据**：查 MLIR 官方 Doxygen（mlir::RewriterBase，24.x）：不存在名为 `replaceUses` 的成员函数；实际相关接口是 `replaceAllUsesWith(Value, Value)`、`replaceUsesWithIf(Value, Value, function_ref<bool(OpOperand&)>)`、`replaceAllOpUsesWith(...)` 与 `eraseOp(...)`。另注意 `replaceOp(op, newValues)` 会自动擦除原操作（文档注明 “The replaced op is erased.”），真正“替换与删除两步分开”的惯用法是 Value 级的 `replaceAllUsesWith` ＋ `eraseOp`（src/Graph.h 注释里的“先 replaceUses 再 eraseOp”同此问题）。句子想表达的两步分解与“分开是有意的”在概念上成立，但以代码格式引用了一个不存在的名字，读者按名检索官方文档会找不到，建议改为真实方法名。
- **置信度**：高（已查 MLIR 24 官方 Doxygen 逐条核对；归入存疑仅因概念正确、属引用名称不准确而非机制错误）。

## 【建议】

#### 1. 选做挑战应提醒“边遍历边删除”的迭代器失效坑
- **原文**：“用今天的 API 写一个约 20 行的 mini-DCE：循环删除"无使用者且非图输出"的节点，直到一轮下来一个都删不动（不动点）”
- **依据**：`erase_node` 会从 `nodes_`（`std::vector<std::unique_ptr<Node>>`）中 erase 元素；学员若在最自然的写法 `for (const std::unique_ptr<Node>& n : g.nodes())` 循环体内直接调 `g.erase_node(n.get())`，就是“迭代中修改容器”，属于未定义行为。正文 5.2 节末尾只提了“删除后指针失效”，未提遍历中的迭代器失效，而 mini-DCE 恰恰是当天最容易触发这条坑的练习。建议在挑战题里补一句“先把节点列表拷贝一份再循环删除（或用索引小心前进）”，可以替学员挡掉一次真实崩溃。
- **置信度**：高（C++ 容器语义明确；属提示缺失而非既有内容错误）。

#### 2. `replace_all_uses_of` 缺少“值属于本图”的守门检查
- **原文**：“replace 三个廉价检查”
- **依据**：`erase_node` 有“节点不属于本图”的守门（测试第 12 组专门验证），而 `replace_all_uses_of` 只做空指针、`from == to`、类型一致三个检查，从不验证 `from`／`to` 是否属于本图；且该函数实现完全不经由 `this` 的成员，传入外图的 Value 时会直接改写外图节点的槽位并把记录写进外图 Value 的账本，两张图的账本同时静默损坏、不抛任何异常。不影响当天示例的正确性（示例均在单图内使用），但与“唯一登记员／唯一写者”的叙事有落差，建议补一条归属检查，或在正文说明这是“三个廉价检查”之外的已知边界（与“取消输出接口不预支”同类的取舍）。
- **置信度**：中（行为可直接由源码读出；是否必须补检查属教学取舍，非正确性问题）。
