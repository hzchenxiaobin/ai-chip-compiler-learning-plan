# 第 16 天技术校对报告

## 【错误】
#### 1. 「其余文件一行未改」与工程实际改动不符（main.cpp 被整篇重写）
- **原文**：“完整工程在本仓库 `tutorials/week-003/day-016/examples/mini-graph-v8/`，由第 14 天的 v7 复制而来——除 `Graph` 的两处改动（`topological_order` 委托 TopoSort、新增 `rewire_input`）和 `Verifier.h` 里把「欠条」注释改为「已兑现」的两行说明外，其余文件一行未改；v7 的五个测试文件原样保留继续跑。”
- **依据**：对本仓库 v7（week-002/day-014）与 v8 做 `diff -r --brief` 与 `diff -u` 核实：`src/main.cpp` 是整篇重写（新增 TopoSort.h／OpKind.h 头、删去 Frontend.h／Model.h／NodeVisitor.h／OpCardPrinter.h，主程序改为「第一幕双通道＋第二幕两个事故现场」的两幕结构，与 v7 的 Mul 演示完全不同）；此外根目录 `CMakeLists.txt`（工程改名 v7→v8）、`src/CMakeLists.txt`（库改名＋加入 TopoSort.cpp＋可执行文件改名）、`tests/CMakeLists.txt`（新增 test_toposort）均有改动。这些都不在该句点名的例外清单里（「v7 的五个测试文件原样保留」这一点属实：五个 test_*.cpp 与 v7 逐字节一致）。
- **置信度**：高（diff 可客观复现，非主观判断）。

#### 2. 目录树里「其余九个文件」的计数与 src/ 实际文件数不符
- **原文**：“│   └── （其余九个文件从 v7 原样复制）”
- **依据**：`src/` 实有 20 个 .h/.cpp 文件（另有 CMakeLists.txt）。其中新增 2 个（TopoSort.h/.cpp）、改动 4 个（Graph.h、Graph.cpp、main.cpp、Verifier.h），与 v7 逐字节一致的只有 14 个（Attrs.h、Dtype.h、Frontend.h/.cpp、Interpreter.h/.cpp、Model.h、Node.h、NodeVisitor.h、OpCardPrinter.h、OpKind.h、TensorType.h、Value.h、Verifier.cpp）。「九」与任何口径（14／15／16）都对不上；按树的字面语义（src 里除 TopoSort×2 与 Graph×2 外的其余文件），还应包含 main.cpp 与 Verifier.h——前者绝非「原样复制」（见上一条）。最接近「九」的数法是 9 个纯结构头文件，但那样 Frontend／Interpreter／Verifier／main 等 7 个文件就整棵树消失了，误导读者对工程规模的认知。
- **置信度**：高（文件计数客观；作者意图的数法无法确证，但字面陈述错误无疑）。

#### 3. 错误三 ASan 输出的两处「笔者标注」行号指向错误位置
- **原文**：“    #0 ... in Node::kind() const ../src/Node.h:24        ← 读已释放的节点（bug 第 55 行）”
- **依据**：按 `bugs/err_stale_topo_cache.cpp` 头部注释的命令在本机重跑（g++ 9.4.0 + ASan）：ASan 报告为 `#1 in main .../err_stale_topo_cache.cpp:57`——对已释放内存的「读」发生在第 57 行（printf 参数里的 `n->kind()`），而第 55 行只是把悬垂指针拷进局部变量 `const Node* n = schedule[i];`（拷指针不解引用，ASan 不会在该行报警）。紧邻一行「← 释放点（bug 第 46 行调用）」同样偏差两行：真正的 erase 调用 `g.erase_node(dead);` 在第 48 行，第 46 行只是注释。帧号与地址确实随构建变化（正文也如此声明），但同一份源文件的行号不随构建变化，标注应指向 57／48。
- **置信度**：高（重跑复现 ASan 输出并逐行核对源文件；上一次独立运行亦得到相同的 57／48）。

## 【存疑】
- 无。

## 【建议】
#### 1. 正文「位置前移」与冻结日志「位置后移」方向词互相矛盾
- **原文**：“只改一个参数：把 5 节点 relu 链上「被改的节点」从 `c2` 前移到 `c1` 再到 `c0`（环长恒为 3）。一键复现：”
- **依据**：同一实验的冻结输出 `experiments/cycle-position.log` 第 1 行（由 `cycle_position.cpp` 的 printf 打印）写的是「环长固定 3，位置后移一格——已剥的前缀变短、卡住的名单变长」。「前移／后移」指的是同一次锚点移动（c2→c1→c0，向链头靠拢，已剥 2→1→0），两个方向词必有一处用反。正文自身前后一致（表格、三组读数、图注都用「前移」语义），数字与环路径也全部核对一致，因此不影响技术正确性；但读者照 5.4 节跑脚本时会在终端看到与正文相反的方向词。冻结产物不宜改动，建议下次修订内容时统一两处措辞。
- **置信度**：高（两处原文均可直接查证；哪一处是作者本意无法判定，二者互斥这一点是确定的）。

#### 2. 「用 rewire_input 亲手造出 1 环」缺少对应的示例支撑
- **原文**：“用 `rewire_input` 亲手造出 1 环、2 环、3 环、5 环，验证「已剥前缀 / 卡住 / 环上」三组读数各自的含义”
- **依据**：全工程检索，1 环（自环）的三个现场全部由 `replace_all_uses_of` 造出（main.cpp 现场一、`bugs/err_replace_self_loop.cpp`、`tests/test_toposort.cpp` 用例 8）；`rewire_input` 只被用于造 2 环／3 环／5 环（用例 9/10/12、cycle_position 实验、err_silent_bogus_order）。把某节点槽位 rewire 到它自己的结果确实能合法造出自环（三重守卫不拦），但工程里没有任何 rewire 自环用例；第 8 节验收清单同样写「我能用 `rewire_input` 亲手造出 1 环」。建议措辞改为「用 replace／rewire 造出 1～5 环」，或补一个 rewire 自环的最小用例。
- **置信度**：高（工程内无 rewire 自环用例是可 grep 复核的事实）；影响轻微，属目标描述与示例覆盖度的错位。
