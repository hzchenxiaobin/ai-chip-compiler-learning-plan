# 第 22 天技术校对报告

校对方式：在 Python 3.11.4（Linux）上实际运行 `code/pass_manager.py`（demo 输出与 README 5.3 节逐字节一致，仅差文末换行）和 `--self-test`（33/33 通过）；复跑 5.4 节三个参数实验核实结论；逐行比对 day-020 与 day-022 的共享代码；MLIR/LLVM 论断逐一对照 llvm-project 官方源码与文档（mlir.llvm.org/docs/PassManagement/、mlir/lib/Pass/Pass.cpp、mlir/lib/Tools/mlir-opt/MlirOptMain.cpp、llvm/include/llvm/Support/LogicalResult.h 等）。本报告只记录问题，不修改教程原文、代码或冻结输出。

## 【错误】
#### 1. MLIR 的 `Pass::runOnOperation()` 返回 void，不返回 LogicalResult
- **原文**：“这对应 MLIR 里 `Pass::runOnOperation()` 返回的 LogicalResult（成功 `success()` / 失败 `failure()`），失败会中断整条管线”
- **依据**：MLIR 官方文档《Pass Infrastructure》明确写的是“Override the virtual `void runOnOperation()` method”，并说明失败机制是“the pass can directly signal a failure to the pass manager via the `signalPassFailure` method”；llvm-project 主线 `mlir/lib/Pass/Pass.cpp` 中调用处为 `pass->runOnOperation();`，返回值不被使用，失败状态通过 `passState->irAndPassFailed` 传递。返回 `LogicalResult` 的是 `PassManager::run()`（以及 `Pass::initialize()`），不是 `runOnOperation()`。我们的 `run(graph, am) → True/False` 在语义上更接近“`signalPassFailure()`＋`PassManager::run()` 的 LogicalResult”的组合，而不是 `runOnOperation()` 的返回值。同一错误还在 5.2 节内嵌代码的模块注释中重复出现：“* Pass::runOnOperation() 返回 LogicalResult，failure() 会中断整条管线；”（README 第 181 行）。教程中“失败会中断整条管线”这一半是正确的（signalPassFailure 后同一管线内后续 Pass 不再执行）。
- **置信度**：高（已对照官方文档与主线源码；2019 年至今的 MLIR 各版本 `runOnOperation` 均为 void，`signalPassFailure()` 才是失败上报通道）。

#### 2. mlir-opt 没有 `--mlir-disable-verifier` 这个旗标
- **原文**：“默认在每个 Pass 之后运行 Verifier（`--mlir-disable-verifier` 可关）”
- **依据**：“默认在每个 Pass 之后运行 Verifier”属实（`PassManager` 构造函数 `verifyPasses(true)`，`mlir-opt` 侧对应旗标默认开），但旗标名错了：llvm-project 主线 `mlir/lib/Tools/mlir-opt/MlirOptMain.cpp` 注册的是 `verifyPasses("verify-each", cl::desc("Run the verifier after each transformation pass"), cl::init(true))`，关闭应写 `-verify-each=false`。该旗标自 2019-03 引入时就叫 `verify-each`（commit 50efe0fc85），release/14.x、17.x、main 一致；当前主线不存在名为 `mlir-disable-verifier` 的旗标（另有一个 2024-11 加入的 `-mlir-very-unsafe-disable-verifier-on-parsing`，只作用于解析阶段，语义不同）。同一错误也在 5.2 节内嵌代码注释中出现：“* mlir-opt 默认在每个 Pass 之后运行 Verifier（--mlir-disable-verifier 可关）；”（README 第 183 行）。
- **置信度**：高（已逐一检索 Pass.cpp、PassRegistry.cpp、MlirOptMain.cpp、MLIRContext.cpp 及官方文档，均无此旗标；不排除极老的分支或其他第三方 MLIR 工具自行注册过同名旗标，但就 mlir-opt 而言结论明确）。

## 【存疑】
#### 1. “失败直接终止编译”在 MLIR 多线程/嵌入场景下不成立，表述过于绝对
- **原文**：“真实编译器同样如此：失败直接终止编译，没人把 IR 恢复原样。”
- **依据**：“不回滚”属实：MLIR/LLVM 都没有“失败后把 IR 恢复原样”的机制，这一点与我们的 PassManager 一致。但“失败直接终止编译”过于绝对：MLIR 的 `PassManager::run()` 只是返回 `failure()`，由驱动决定后续；且多线程管线里一个嵌套管线失败后，其它无关操作的管线仍会继续跑完（主线 `Pass.cpp` 异步执行处注释即写着“Continue processing independent operations after a pipeline failure”，随后才汇总 `hasFailure` 并 `signalPassFailure`）。对 `mlir-opt` 这种顶层单管线的驱动，说“以失败退出”没问题；作为对“真实编译器”的一般性论断则不准确。
- **置信度**：中高（“不回滚”与 mlir-opt 行为高置信；“一般化论断不准”依据为主线源码的异步分支注释，未实际构造多线程失败复现）。

#### 2. “空 Pass 用于隔离测量，真实编译器里也是这么用的”未找到依据
- **原文**：“③ 隔离测量（空 Pass 的耗时≈管理器自身开销，真实编译器里也是这么用的）。”
- **依据**：检索 MLIR/LLVM 官方文档与标准 Pass 清单，未发现内置 no-op Pass 用于“测量 PassManager 自身开销”的公开实践；LLVM 的耗时观测走 `-time-passes`（PassTimingInfo），MLIR 走 `-mlir-timing`（PassTiming instrumentation），两者都不依赖一个“空 Pass”来标定基线。“空 Pass 的耗时≈管理器开销”作为本演练场自己的实验结论成立，但“真实编译器里也是这么用的”这一行业论断未能核实。
- **置信度**：中（不确定点：未穷尽检索编译器内部测试工具与各公司内部实践，不能排除有工具这样做，但至少 MLIR/LLVM 公开文档中无此用法）。

## 【建议】
#### 1. `raise` 失败是在步骤②（运行 Pass）被抓的，正文与图 2 都归到③
- **原文**：“返回 False 或抛异常（`PassFailure`/`GraphError`）都拉闸”
- **依据**：代码里 `try: ok = p.run(graph, self.am) except (GraphError, PassFailure)` 包住的是②运行 Pass 这一步（代码注释也标着“② 运行 Pass”），异常在②就被接住并直接进 `_stop`，并不是等③查返回值时才发现；③只负责 `ok is not True`。图 2 的③框同样写着“不是 True ⇒ 拉闸（return）；抛异常 ⇒ raise”。属步骤归属的口径小偏差，不影响结论，但既然全文强调“六步循环的顺序”，建议在②或③注明 try/except 的位置，避免读者对照代码时困惑。
- **置信度**：高（直接对照 5.2 节代码即可确认）。

#### 2. `pm.describe()` 的最后一行不是失败行
- **原文**：“定位：`pm.describe()` 最后一行就是失败行”
- **依据**：以 5.3 节 [4] 的真实输出为准，`describe()` 打印的最后两行依次是“失败：no-support（kind = return）”和“跳过：fold-add-zero”——失败行是倒数第二行，最后一行是跳过清单（仅当没有跳过项时失败行才是末行）。说法与自家冻结输出不符，建议改成“失败行就在 `describe()` 结尾”。
- **置信度**：高（对照 README 第 1009–1011 行的冻结输出）。

#### 3. “一行不改／原样搬来”与两份代码的实际情况有出入
- **原文**：“Day 20 的 AnalysisManager 今天一行不改地被请进调度台”
- **依据**：逐行对比 day-020 与 day-022 的代码：`get()` 的对账逻辑逐行一致，但类 docstring 被压缩、`GraphError` 消息文案被改短（“分析 {name} 在 run 期间修改了图（epoch X → Y）：分析 Pass 只读，改图请写成变换 Pass”→“分析 {analysis.name} 在 run 期间修改了图：分析 Pass 只读”）、`describe()` 标题由“缓存对账”改为“分析管理器对账”；`UnusedResult` 还删掉了 `format()` 方法。行为契约确实没变，但“一行不改”“原样搬来”（第 147 行）字面上不成立，建议改成“逻辑一行不改”或注明“仅精简了注释与文案”。
- **置信度**：高（已做逐行 diff）。

#### 4. mlir-opt 的“有变化才打印”变体必须与其它 after 旗标联用才生效
- **原文**：“（mlir-opt 也有只在有变化时打印的变体）”
- **依据**：MLIR 官方文档对该旗标（`-mlir-print-ir-after-change`）专门注明“This option should be used in unison with one of the other 'mlir-print-ir-after' options above, as this option alone does not enable printing”，且变化检测靠前后哈希对比、可能哈希碰撞误报。初学者若单独传它，会一个字都打不出来并误以为管线没跑。我们的 `print_ir="change"` 是独立档位，与 mlir-opt 的用法有这个差异，建议补半句点破。
- **置信度**：高（官方文档原文核实）。

#### 5. `LogicalResult` 标注了 `[[nodiscard]]`，“能被无视”漏掉了编译器告警这层保护
- **原文**：“（C++ 里 `LogicalResult` 同样能被无视）”
- **依据**：llvm-project 主线 `llvm/include/llvm/Support/LogicalResult.h:25` 为 `struct [[nodiscard]] LogicalResult`。忽略返回值仍能编译（告警不是错误，除非 `-Werror`），所以“能被无视”字面成立，但 C++ 编译器会发警告，与 Python“完全静默”不同。建议措辞改为“C++ 里 `LogicalResult` 能被无视（只是会吃 `[[nodiscard]]` 警告）”，正好强化“语言不强制、纪律来补”的论点。
- **置信度**：高（主线头文件原文核实）。

#### 6. bypass 行的“Day 12 对应：契约违反”不是 Day 12 的类别
- **原文**：“| `bypass` | 记账绊线 | 语句数变了 epoch 却没动——绕过了修改方法直接改表 | 契约违反 |”
- **依据**：Day 12 的三分法只有“构造失败／验证失败／运行失败”三类，没有“契约违反”。bypass 违反的是今天才引入的“改图走方法”契约，在 Day 12 的分类里没有对应物——表格列名“Day 12 对应”会让读者以为 Day 12 教过这一类。建议该格改写为“（Day 12 无对应，今天新增）”，与 entry/return/raise/verify 四行能真正映射到三分法形成对照。
- **置信度**：高（已核对 day-012 README 的分类表）。

#### 7. 引用的那句话在 Day 20 的开篇，不在结尾
- **原文**：“Day 20 的结尾留了一句话：”
- **依据**：“现在想象你要当 PassManager 的作者（Day 22 的预告）”出自 day-020 README 第 1 节开头（第 10 行，即“今天解决什么问题”一节）；Day 20 真正的结尾（第 9 节）预告的是 Day 21 复盘。属跨日引用的位置错误，不影响技术内容，建议把“结尾”改成“开篇”。
- **置信度**：高（已检索 day-020 README 全文确认该句仅出现一次，位于开篇）。
