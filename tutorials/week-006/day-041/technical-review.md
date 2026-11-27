# 第 41 天技术校对报告

审阅范围：`tutorials/week-006/day-041/` 的 README.md、`code/` 全部源码与 `.mlir` 输入、`images/` 三张 SVG，以及 `run_all.sh`。审阅环境与教程声明一致（Ubuntu 20.04、LLVM/MLIR 18.1.8 来自 `mlir-18-tools`、CMake 3.20.5、Ninja 1.10.0、g++ 9.4.0）。全部 9 组实验（round-trip、两个负例、CSE、count-ops、statistics、两个对照）均在临时目录重新构建并复跑，输出与教程记录一致；Day 39/40 的 `MatmulVerifier.cpp`、`ShapeRelation.h` 与本日版本逐字节相同。本报告同时引用了 LLVM 18.1.8 的 `Statistic.h`、`Pass.h` 与上游 `Passes.td`、`CSE.cpp`、`MlirOptMain.cpp`、`PassRegistry.cpp` 源码作为依据。

## 【错误】

#### 1. “想要统计表，换 RelWithDebInfo 重新配置即可”不成立——RelWithDebInfo 仍定义 NDEBUG，统计仍为空表
- **原文**：“想要真实统计表，把 `-DCMAKE_BUILD_TYPE=RelWithDebInfo` 或 `Debug` 重新配置即可（今天的实验不依赖它）。”
- **依据**：CMake 的 `RelWithDebInfo` 默认编译选项是 `-O2 -g -DNDEBUG`。我用 `ninja -t commands` 核对了按本教程命令以 RelWithDebInfo 重新配置的构建，`CountOpsPass.cpp` 的编译命令确实带 `-DNDEBUG`。LLVM 18 的 `llvm/ADT/Statistic.h` 第 35～40 行用 `#if !defined(NDEBUG) || LLVM_FORCE_ENABLE_STATS` 决定 `llvm::Statistic` 是 `TrackingStatistic` 还是 `NoopStatistic`（本发行版 `llvm-config.h` 中 `LLVM_FORCE_ENABLE_STATS` 为 0），因此 RelWithDebInfo 下 `totalOps = total` 仍是空操作。实测：以 `-DCMAKE_BUILD_TYPE=RelWithDebInfo` 重新构建后运行 `mini-opt -mlir-pass-statistics -mini-count-ops target_graph.mlir`，报告与 Release 一样只有表头、没有数据。“Release 构建的已知行为”这半句是对的，给出的修复路径这一半是错的。
- **置信度**：高（在本教程声明的环境中实测复现，并有 LLVM 头文件与编译命令双重证据）。

#### 2. 同一修复建议的另一半也不成立——Debug 构建下这份代码根本编译不过
- **原文**：“需要统计表时用 `RelWithDebInfo` 或 `Debug` 重新配置构建目录。”
- **依据**：把构建类型换成 Debug（无 NDEBUG，`LLVM_ENABLE_STATS=1`，`Statistic = TrackingStatistic`）后构建失败。g++ 9.4 的报错链：`mlir/Pass/Pass.h:457` 的 `PassWrapper<CountOpsPass,...>::clonePass()` 需要拷贝构造 `std::make_unique<CountOpsPass>(const CountOpsPass&)`，而 `CountOpsPass` 的成员 `Pass::Statistic totalOps` 此时继承自含 `std::atomic<uint64_t>`/`std::atomic<bool>` 成员的 `llvm::TrackingStatistic`（拷贝构造被删除，`Statistic.h:50`），导致 `CountOpsPass` 的拷贝构造被隐式删除。MLIR 官方文档（Pass Management → Instance Specific Pass Options / Pass Registration）明确要求带 options/statistics 的 Pass 显式提供拷贝构造（示例中的 `MyPass(const MyPass& pass) {}`）；上游 CSE 把统计放进 tblgen 生成的 Base 类、由其显式拷贝构造重新初始化统计成员，正是为了绕开这个问题。结论：按本教程的写法，Release/RelWithDebInfo 下统计永远为空，Debug 下无法编译——不存在任何 build type 能让 `-mlir-pass-statistics` 打出数据，5.6 节和“错误 4”给出的两条修复路径都不可行。
- **置信度**：高（Debug 编译错误已在本教程声明的环境中复现，报错路径与行号可直接对照 `/usr/lib/llvm-18/include/mlir/Pass/Pass.h` 与 `/usr/lib/llvm-18/include/llvm/ADT/Statistic.h`）。

#### 3. “5 种类型”数量对不上——全图只有 3 种张量类型
- **原文**：“这张图就是"第一张端到端 mini IR"的全部内容：7 个 Operation、5 种类型、1 条从常量到返回的主链路。”
- **依据**：按 MLIR 的“类型”（Type）口径，这张图只出现 3 种张量类型：`tensor<2x3xf32>`（A）、`tensor<3x2xf32>`（B）、`tensor<2x2xf32>`（M、S、R、bias、return）；把函数签名类型 `() -> tensor<2x2xf32>` 算上也只有 4 种。能凑成 5 的口径只有“算子种类”——函数体内恰有 5 种（mini.constant、mini.matmul、mini.add、mini.relu、func.return，与同句“7 个 Operation”同样不含 func.func）。但把算子种类叫“类型”与全文口径冲突：第 4 节前后文和图 2 讲的“类型”都是 `tensor<...>` 类型流，初学者按字面去数类型会数出 3，与“5”对不上。
- **置信度**：中（数字与“类型”的标准读法不符是确定的；作者本意大概率是“5 种算子”，改一个词即可）。

#### 4. “func.return 打印成通用形式”是术语错误——那恰恰是自定义汇编格式，MLIR 的“通用形式”是另一种东西
- **原文**：“`func.return` 变成 `return`：`func` 方言的 return 打印成通用形式，语义没变。”
- **依据**：MLIR 术语里“通用形式”（generic form）专指 `"func.return"(%5) : (tensor<2x2xf32>) -> ()` 这种带引号操作名与类型签名的打印形式，即 `mlir-opt --mlir-print-op-generic` 的输出——与教程描述的现象正好相反。`func.return` 打印成不带前缀的 `return`，真正原因是：FuncOps.td 为它声明了自定义汇编格式（`let assemblyFormat = "attr-dict ($operands^ `:` type($operands))?"`），并且 FuncOp 的 `extraClassDeclaration` 里 `getDefaultDialect()` 返回 "func"（源码注释原文 "Allow the dialect prefix to be omitted"），允许嵌套在函数内的 func 方言算子省略 `func.` 前缀。这与 3.2 节自己讲的“打印器按每个 op 的 `assemblyFormat` 重新生成文本”是一致的，叫成“通用形式”反而自相矛盾，还会让读者日后把 `--mlir-print-op-generic` 的输出认错。
- **置信度**：高（依据 llvmorg-18.1.8 的 `mlir/include/mlir/Dialect/Func/IR/FuncOps.td` 源码核对；对本日实验结果无影响，改一句话即可）。

## 【存疑】

#### 5. “torch-mlir/IREE/ONNX-MLIR 的命令行工具长得都和 mlir-opt 一样，差别只在于……”未核实且过于绝对
- **原文**：“因为"注册"是所有编译器工具的入口机制：`torch-mlir`、`IREE`、`ONNX-MLIR` 的命令行工具长得都和 `mlir-opt` 一样，差别只在于各自往注册表里塞了哪些方言和 Pass。”
- **依据**：机制方向正确（这类工具历史上都派生自 `mlir::MlirOptMain`，例如 iree-opt、onnx-mlir-opt 都在自己的 main 里填 DialectRegistry 并注册 Pass 后调用 MlirOptMain），但本次审阅无法在当前环境中核实三个项目当前版本的 CLI 形态，需要访问各自仓库才能确认。此外“差别只在于往注册表里塞方言和 Pass”过于绝对：这类工具通常还有各自的输入格式、输出目标与自定义命令行选项。建议改为“典型如 …都基于同一套 MlirOptMain 框架，差别主要是各自注册的方言和 Pass”。
- **置信度**：低（未核实；不确定点：三个项目最新版本的工具入口是否仍直接复用 MlirOptMain，以及 torch-mlir 当前的工具形态）。

## 【建议】

#### 6. “9 组实验”与括号里的枚举相加不符
- **原文**：“以上 9 组实验（round-trip ×2、负例 ×2、CSE、count ×2、statistics、对照 ×2）可以用一条命令全部重放”
- **依据**：按括号里的条目相加是 2+2+1+2+1+2＝10 组；`run_all.sh` 的 9 个编号步骤（1/9 构建……9/9 对照 B）中第一步是构建，实验本身是 8 个步骤（round-trip 与 count 各含两条命令，两个负例各一步）。两种口径都与“9 组”对不上。另外“今日产出”里的“9 组真实实验记录”沿用同一口径。建议统一说法，例如“10 组实验记录，由 run_all.sh 的 9 个步骤（含构建）一键重放”。
- **置信度**：高（纯计数问题，两种口径都可直接核对）。

#### 7. 被标注为“真实输出”的引用块存在转录失真
- **原文**：“note: Registered dialects: acc, affine, amdgpu, amx, arith, arm_neon, arm_neon,”
- **依据**：本机实际运行 `mlir-opt-18 target_graph.mlir`，note 中 `arm_neon` 只出现一次；第 1 节这行把它写了两遍（5.7 节的同段引文是对的）。同类小失真还有四处：5.4 两个负例的真实输出里各有一行 `note: see current operation: %4 = "mini.add"(...)` 未显示；5.6 的 remark 命令输出省略了随后的 note 与整个 module 打印（完整输出远比正文长）；5.7 对照 A 的 note 末尾截去了 “; for more info on dialect registration see https://mlir.llvm.org/…”；B4 的实际输出是两行（`grep -c` 自己打印的 `0` 与 `|| echo` 的 `0（没有这一节）`），正文只展示了一行。这些块以“真实输出”名义呈现，建议补全或加省略号标记，方便读者逐行核对。
- **置信度**：高（逐条与实跑输出比对；不影响技术结论，但影响“真实记录”的可核对性）。

#### 8. CSE 合并条件“只有三个”过于简化
- **原文**：“条件只有三个：操作数相同、属性相同、无副作用——`mini.matmul/add/relu` 都挂了 `Pure` trait（Day 37 的 ODS），所以天然满足。”
- **依据**：上游 CSE（llvmorg-18.1.8 的 `mlir/lib/Transforms/CSE.cpp`）通过 `OperationEquivalence::isEquivalentTo(..., OperationEquivalence::IgnoreLocations)` 判定等价，除操作数与属性外还比较操作名与结果类型；同时 CSE 明确跳过终结符（`OpTrait::IsTerminator`）与含多基本块区域的算子。对本节探针图的结论没有任何影响（重复算子天然同名同结果类型），但“只有三个”的排他表述建议改成“至少要满足”，或补上“操作名与结果类型也相同”。
- **置信度**：高（依据上游源码；属于表述完整性问题，不影响当日实验结论）。

#### 9. “错误信息由 PassPipelineCLParser 发出”归因不准
- **原文**：“B2/B3 证明 Pass 表决定命令行选项的存在性：没注册就变成"未知参数"，错误信息由 `PassPipelineCLParser` 发出。”
- **依据**：实测的 `mini-opt: Unknown command line argument '-cse'. Try: '... --help'` 由 LLVM CommandLine 库（`cl::ParseCommandLineOptions`）打印；`PassPipelineCLParser` 的作用是让 `PassNameParser::initialize()` 把 Pass 注册表里的名字（`addLiteralOption`）登记为命令行可识别的字面量选项——没注册的名字因此在 cl 的全局选项查找中落空。结论（Pass 表决定选项存在性）不变，归因建议改成“由 LLVM 命令行库发出，PassPipelineCLParser 负责把注册过的 Pass 名字登记为可识别的选项”。
- **置信度**：高（依据 llvmorg-18.1.8 的 `mlir/lib/Pass/PassRegistry.cpp` 与 `mlir/lib/Tools/mlir-opt/MlirOptMain.cpp` 源码）。

#### 10. 必做练习的“数一数”口径与 remark 计数相差 1（func.func 是否计入）
- **原文**：“不跑 `-cse`，先在纸上数：`cse_dup_matmul.mlir` 里 `@dup` 这个函数一共有多少个 Operation（别忘了 `func.return` 和 `mini.constant`×3）？”
- **依据**：按提示数出的函数体内操作是 10 个（3 constant＋2 matmul＋2 add＋2 relu＋1 return），而实测 remark 报 `11 ops`——`func->walk` 从 `func.func` 自身开始遍历，`func.func=1` 也被计入。5.3/5.6 的 8 ops、5 ops 同样含 func.func，而第 4 节“7 个 Operation”与练习提示的口径又不包含它。两种口径并存且从未说明，学生按提示数会与 remark 差 1；建议在 5.6 或练习处点明“计数包含 func.func 本身”。
- **置信度**：高（实测 remark 为 `11 ops in @dup (func.func=1, func.return=1, mini.add=2, mini.constant=3, mini.matmul=2, mini.relu=2)`）。

#### 11. CSE 对照图的图注与图内容不完全对应
- **原文**：“右图里第二个 matmul/add/relu 方框被划掉，说明"查无此人"”
- **依据**：`images/03-example.svg` 的两个面板画的是代码行式列表（如 `%0 = constant A : 2×3`），右面板用一条划线加“%m2 %s2 %r2 消失”的文字注释表示删除，整张图里没有被划掉的“方框”；“两条 return 边都改指向幸存的那条 relu”的表述同样对应的是代码行 `return %5, %5` 而非边。技术内容（谁被删、返回值指向谁、合并三要素）都正确，只是图注把“代码行”说成了“方框/边”，改图注措辞即可。（注：本次审阅在 5.4 节新增 04-shape-relation.svg 后，该图的序号由“图 3”调整为“图 4”，文件名不变。）
- **置信度**：高（直接读 SVG 内容核对；纯图注与图面的一致性问题）。
