# 第 48 天技术校对报告

审阅对象：`tutorials/week-007/day-048/README.md`、当天 `code/`（含 mini 工程、5 个 `.mlir` 用例、`run_all.sh`）、已引用的 3 张 SVG。审阅环境与教程一致：Ubuntu 20.04（aarch64）、LLVM/MLIR 18.1.8（mlir-18-tools）、cmake 3.x＋Ninja、g++ 9.4.0。核对方式：当天全部实验在本机独立重放（构建、5 个 FileCheck、四组顺序对照、max-iterations 0/1、四组 diff 断言、count-ops 计数、`--mlir-print-ir-after-all` 快照、`-canonicalize{...}` 报错复现、`--mlir-pass-statistics` 空报告复现），另取 llvmorg-18.1.8 tag 的上游源码（GreedyPatternRewriteDriver.cpp、FoldUtils.cpp、Canonicalizer.cpp、Builders.cpp、PatternMatch.cpp/h）核对机制论断，并用临时目录里挂了"病态 Pattern"的 mini 工程副本做了对照实验。README 中所有可运行命令与贴出的输出经重放全部属实（1/0/1/0 存亡矩阵、9→4 计数、11.0 塌缩、逐字节相同断言、错误 3 的两种报错原文、空统计报告）。以下仅列与事实不符或需核实的条目。

## 【错误】

#### 1. 上游 mlir-opt 并没有 `-O2` 这类总开关
- **原文**：“上游 `mlir-opt` 的 `-O2` 这类总开关也是同样的机制。”
- **依据**：本机实测 `mlir-opt-18 -O2` 直接报 `Unknown command line argument '-O2'`（与教程错误 3 记录的报错格式同款）；`mlir-opt-18 --help` 的顶层选项里没有任何 `-O` 总开关——帮助文本里仅有的两处 `-O <uint>` 分别是 `--nvvm-attach-target` 和 `--rocdl-attach-target` 这两个 Pass 的子选项（GPU 目标的优化级别，与 Pass 管道注册机制无关）。“单个 Pass 与管道写同一张注册表、命令行解析器不区分二者”这个机制论断本身正确（§5.3 (e) 组的逐字节 diff 已证明），错的是举例：mlir-opt 18.1.8 不存在 `-O2`。若作者想说的是 LLVM `opt -O2`，那也不是 `PassPipelineRegistration` 机制（LLVM opt 走 PassBuilder 的默认管线）。`code/mini/lib/CombinedPipeline.cpp` 注释里“上游 -O2 就是这么拼的”是同一处不实举例（本报告只记录，不改代码）。
- **置信度**：高（本机两种写法实测报错＋--help 全文检索确认无顶层 -O 选项）。

#### 2. 常量去重的时机说错：MLIR 18.1.8 物化常量时并不复用已有节点
- **原文**：“加上驱动的常量去重（uniquing，物化重复常量时优先复用已有节点），所以无论谁先动手，输出都收敛到同一个 IR：一个值 5.0 的常量。”
- **依据**：llvmorg-18.1.8 的 `mlir/lib/Transforms/Utils/GreedyPatternRewriteDriver.cpp`（`processWorklist`）里 fold 成功后直接调用 `op->getDialect()->materializeConstant(...)` 物化新常量，这一步**不复用**任何已有节点；常量去重发生在每轮外层迭代开头的“工作表填充”阶段（`RegionPatternRewriteDriver::simplify` 里经 `OperationFolder::insertKnownConstant`，见 `FoldUtils.cpp`——重复常量在填充时被替换合并）。本机可复现的反例：构造 `add(5.0 常量, -0.0 常量)` 并让原 5.0 常量另有使用者，`canonicalize{max-iterations=1}` 的输出里有**两个** 5.0 常量，默认 10 轮才收敛成一个（多出来的那一轮恰好就是去重发生的时机）。冲突场景最终只剩一个 5.0 的真实原因是“输掉的一方失去使用者后被当死代码收走”＋下一轮填充期的去重，而不是“物化时优先复用”。“无论谁先动手都收敛”的结论本身成立（已实测），错的是括号里的机制描述——该描述更接近 MLIR ≤16 时代 `OperationFolder::tryToFold` 在物化时去重的旧行为。
- **置信度**：高（18.1.8 源码逐行核对＋本机用 max-iterations=1 与默认 10 两种预算实测出 2 个与 1 个常量的差异）。

#### 3. “预算防的是每次重写都生成新匹配的病态 Pattern”——这类病态恰恰防不住
- **原文**：“预算真正防的是**越改越大**的病态 Pattern（每次重写都生成新的可匹配操作），今天的 Pattern 都不做这种事。”
- **依据**：`max-iterations` 只在外层迭代之间检查（`RegionPatternRewriteDriver::simplify` 的 do-while 顶部 `if (++iteration > config.maxIterations ...) break`）；而通过 rewriter 新建的操作会经 `OpBuilder::insert → notifyOperationInserted → addToWorklist` **自动进表**（`Builders.cpp`、`GreedyPatternRewriteDriver.cpp`）。因此“每次重写都生成新的可匹配操作”的 Pattern 会让工作表永远排不空，卡死在第 1 轮**内部**，预算检查永远轮不到执行。本机实测：在 mini 工程副本（临时目录）里挂一个每次重写都生成两个新 `mini.add` 的 Pattern，`canonicalize{max-iterations=1}` 与默认 10 轮都在 10 秒超时内跑不完（exit 124，真挂起）；同一输入换回原版 mini-opt 则秒回。预算真正限制的是“每轮完整扫描（填充＋工作表处理＋区域化简）”的重复次数，防的是**跨轮才显形**的不收敛（每轮结束都有改动、但工作表内已到头的乒乓局面）；超限时 Canonicalizer 按 best-effort 停止且不报错（`Canonicalizer.cpp` 注释原文："Non-convergence is not a pass failure"）。当天 0/1/10 的对照实验结果全部属实，需改的只是这处因果解释。§5.4 末尾“需要上限防住病态循环，这也是选项默认给 10 而不是无限的原因”同此问题。
- **置信度**：高（18.1.8 源码控制流核对＋病态 Pattern 在两种预算下均实测挂起）。

#### 4. “会生成新操作的 Pattern 吃多轮预算”与当天自己的实验矛盾
- **原文**：“真正吃多轮预算的是"会生成新操作的 Pattern"——那类重写每轮都可能制造新的匹配机会，需要上限防住病态循环，这也是选项默认给 10 而不是无限的原因。”
- **依据**：`cascade_chain.mlir` 的每一层折叠都会**物化一个新常量节点**（本篇 §3.3/§4 自己写明 fold“物化一个新常量”），这正是“会生成新操作”的重写；但整个级联在一轮工作表排空内就完成（§5.4 自己实测 `max-iterations=1` 与默认输出逐字节相同）——因为新建操作自动进表、当轮就会被处理（依据见上一条的源码引用）。同段把当天的重写归为“删减型（只删节点、只换边）”也不准确：fold＋物化是“删旧节点、造新节点”，净减少但并非不新增。§3.2 的“`=1` 时已与默认输出逐字节相同——因为”删节点、换边“这类不新增操作的重写，一轮工作表排空就能到底”是同一处误标（该结论本身正确，理由错位）。真正需要多轮的场景是“改动对工作表回表不可见”的情形（例如区域/CFG 化简之后才出现的匹配、对容器算子的匹配）。
- **置信度**：高（以当天自己的实验为反例＋源码确认新操作自动进表）。

## 【存疑】
- 无。

## 【建议】

#### 1. 改动半径收据里“两处注释标点差异”有一处实为内容删减
- **原文**：“`diff -rq` 实测相对 Day 47 只有上述 5 处功能改动＋两处注释标点差异。”
- **依据**：本机重放 `diff -rq`：共 7 条差异（6 个文件不同＋1 个新文件），与“5＋2”的数量一致；但两处注释差异中，`MiniDialect.td` 一处确是引号样式（"值"→“值”），另一处是 `AddFold.cpp` 注释删掉了整段“（见教程 4.3 节）”交叉引用，属内容删减而非标点。数量对、措辞不准。
- **置信度**：高（diff 原文在手）。

#### 2. 选做挑战的提示“规范化只会删节点”表述过强
- **原文**：“（提示：规范化只会**删**节点，不会把已细化的 `2x2` 变回 `?`，也不会造出新的 `?`。）”
- **依据**：canonicalize 的 fold 会物化新常量节点（本篇 §3.3/§4 自述），“只会删节点”作为一般论断与本篇自相矛盾；就该挑战场景而言结论成立（fold 的类型护栏要求物化常量类型与结果类型一致，不会引入 `?`），但理由宜写成形状不变式（“不会把静态维改回 `?`、物化常量类型跟随结果类型”）而非“只删节点”。
- **置信度**：高（机制由 §3.3 自述＋AddFold.cpp 源码证实）。
