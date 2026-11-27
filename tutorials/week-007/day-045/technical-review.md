# 第 45 天技术校对报告

校对环境与教程声称一致（Ubuntu 20.04.5 aarch64 / MLIR 18.1.8 / gcc 9.4.0 / cmake 3.20.5 / ninja 1.10.0）。以下判断均经本机实测或源码核实：完整重建 mini-opt（17/17 目标，产物 6,815,176 字节≈6.8 MB）；6 个探针 FileCheck 全部 PASS（rc=0）；count-ops 两条 remark 与教程逐字一致；四类错误（静默 UB、段错误 rc=139、hasCanonicalizer 缺失编译错、FileCheck 失败）全部在临时目录复现成功；§5.4 的 replaceOp 一行写法亦实测 6/6 全绿。核心机制论断（PatternRewriter 继承链、getCanonicalizationPatterns 收集流程、贪婪工作表重排队、folding/DCE 先于匹配）已对照本机 MLIR 18.1.8 头文件及 llvm-project release/18.x 源码逐条核实。

## 【错误】
#### 1. `MLIR_ENABLE_EXPENSIVE_CHECKS` 宏在 MLIR 18.1.8 中不存在
- **原文**："- **修复**：一律走 `rewriter.replaceAllUsesWith` / `rewriter.eraseOp` / `rewriter.replaceOp`。带断言或 `MLIR_ENABLE_EXPENSIVE_CHECKS` 的构建能拦住这类问题，Release 构建只能靠纪律。"
- **依据**：本机 `/usr/lib/llvm-18/include/mlir/Config/mlir-config.h` 第 20 行唯一的 EXPENSIVE 宏是 `#define MLIR_ENABLE_EXPENSIVE_PATTERN_API_CHECKS 0`；grep 全部已安装 MLIR 头文件无 `MLIR_ENABLE_EXPENSIVE_CHECKS`。llvm-project release/18.x 的 `mlir/lib/Transforms/Utils/GreedyPatternRewriteDriver.cpp` 里专门用于抓"绕过 rewriter 改 IR"的 ExpensiveChecks（指纹机制，其注释明言"op was erased without notifying the rewriter"时可能崩溃并建议配 ASAN）由 `#if MLIR_ENABLE_EXPENSIVE_PATTERN_API_CHECKS` 控制。LLVM 侧确有 `LLVM_ENABLE_EXPENSIVE_CHECKS`，但它在 HandleLLVMOptions.cmake 里定义的是 `EXPENSIVE_CHECKS` 宏、管 LLVM IR 层检查，开不了 MLIR 的 Pattern API 检查——教程里的这个名字两个体系都对应不上。另外，"带断言能拦住"这半句也找不到出处：18.1.8 驱动源码中 NDEBUG 守卫的检查只有"不许擦除 scope 区域父 op"一处，普通 op 被 `outer.erase()` 删掉并无断言防线。正确表述应指向 `MLIR_ENABLE_EXPENSIVE_PATTERN_API_CHECKS`（从源码构建 MLIR 时打开）或 ASAN。
- **置信度**：高（宏名已由本机头文件与 release/18.x 源码双重核实）；"断言拦不住"的判断基于源码通读，本机无断言版 libMLIR 可实测，把握中高。

#### 2. "Day 47（常量折叠）只是往同一个入口里加新规则"与 Day 47 实际实现矛盾
- **原文**："为什么今天值得单独一天？因为 Pattern 重写是 MLIR 图优化的**基本工作单位**——上游的 `arith`、`linalg`、Tosa 等方言的几十条化简规则全是这个套路。今天用一条规则把"Pattern 本体 / 挂钩 / 驱动"三层关系走通，Day 46（`Add(x, 0) → x`）和 Day 47（常量折叠）只是往同一个入口里加新规则。"
- **依据**：day-047 的常量折叠实际走 fold 钩子：`tutorials/week-007/day-047/code/mini/include/mini/MiniOps.td` 给 `mini.add`/`mini.constant` 打开的是 `let hasFolder = 1`（第 157、313 行），本体在 `lib/AddFold.cpp`（另配 `materializeConstant` 常量物化钩子）；day-047 README 自述"相比 Day 45/46，今天是**另一条生产线**：Pattern 拿 `PatternRewriter` 亲手改图；fold 连 Rewriter 的影子都见不到"。fold 由驱动逐 op 调用（GreedyPatternRewriteDriver.cpp 的 processWorklist 中 `op->fold(foldResults)`），不经 `getCanonicalizationPatterns` 收集——不是"同一个入口"。句中 Day 46 部分属实（day-046 的 AlgebraicSimplification.cpp 确实走 hasCanonicalizer 同一入口）。
- **置信度**：高（已对照 day-046/047 的代码与 README）。

#### 3. 前置准备说"两处改动"，与 §5.1"三处接缝"及实际 diff 矛盾
- **原文**："> **前置准备**：Day 41～44 的 mini 方言工程（`tutorials/week-007/day-044/code/mini` 基础上新增今天两处改动）、LLVM/MLIR 18.1.8（含 `MLIRConfig.cmake`）、CMake 3.20+ 与 Ninja、FileCheck（`/usr/lib/llvm-18/bin/FileCheck`）。实测环境：Ubuntu 20.04.5 LTS（aarch64）、gcc 9.4.0、cmake 3.20.5、ninja 1.10.0。"
- **依据**：`diff -r day-044/code/mini day-045/code/mini` 显示功能性改动恰为三处：① MiniOps.td（hasCanonicalizer 开关＋算子描述）、② 新增 lib/ReluCanonicalization.cpp、③ lib/CMakeLists.txt 登记源文件（另有一处 ShapeInferencePass.cpp 纯注释改写，见【建议】5）；§5.1 自己也写"今天只有**三处接缝**（无一处碰 mini-opt）"。同一篇文档前后计数不一致（两处 vs 三处）。若作者本意是"两处 1 行修改＋一个新文件"，也应与 §5.1 统一口径。
- **置信度**：高（不一致确凿；影响小，属计数口径问题）。

## 【存疑】
#### 1. "几十条化简规则全是这个套路"过于绝对
- **原文**："为什么今天值得单独一天？因为 Pattern 重写是 MLIR 图优化的**基本工作单位**——上游的 `arith`、`linalg`、Tosa 等方言的几十条化简规则全是这个套路。今天用一条规则把"Pattern 本体 / 挂钩 / 驱动"三层关系走通，Day 46（`Add(x, 0) → x`）和 Day 47（常量折叠）只是往同一个入口里加新规则。"
- **依据**：本机 `/usr/lib/llvm-18/include/mlir/Dialect/Arith/IR/ArithOps.td` 统计：`hasFolder = 1` 出现 49 处，`hasCanonicalizer = 1` 出现 19 处——仅 arith 方言里走 fold 钩子的算子就约是 RewritePattern 的 2.5 倍，"全是这个套路"与事实不符；day-047 README 也自述上游"fold 和 Pattern 各占半壁江山"。若作者本意只数 RewritePattern 规则（linalg/Tosa 确有几十条），句子虽可自洽，但初学者容易据此误以为 fold 机制不存在——而 §3.3 引用的头文件原文恰恰说明驱动"顺带做 folding"。建议改为"Pattern 是主力之一，另有 fold 钩子这条路（Day 47 见）"。
- **置信度**：高（对"全是"不成立已核实）；对作者原意的解读存在不确定性，故列存疑而非错误。

## 【建议】
#### 1. 探针 6 的"真实输出"代码块里混入了人工注释
- **原文**："    %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>   // ?x2 → 2x2"
- **依据**：实测 `mini-opt pipeline_dynamic.mlir -mini-infer-shape -canonicalize` 的输出不含任何行尾注释；第 205/207 行的 `// ?x2 → 2x2`、`// 两层 → 一层` 是作者标注。该代码块以 `$ mini-opt ...` 开头、§5.3 又声明"全部真实运行"，读者复跑会发现注释并不存在。建议注明"行尾斜体/注释为人工标注"或把注释移出代码块；IR 本身与实测输出逐字一致。
- **置信度**：高（已实测比对）。

#### 2. 图 3 图注"同一条命令只交换 Pass 顺序"描述不准确
- **原文**："**图 4**：六张卡对应上面六个探针的实测结论；底部那条 count-ops 对照值得单独看——同一条命令只交换 Pass 顺序，`mini.relu` 计数从 2 变 1，这是"IR 真的变小了"的机器可读证据："
- **依据**：所引两条命令（第 222、224 行）中第一条 `mini-opt double_relu_basic.mlir -mini-count-ops` 根本没有 `-canonicalize`；第二条是在 `-mini-count-ops` 之前**多插了**一个 `-canonicalize`。差异是 Pass 集合不同，不是"交换顺序"——若真是交换顺序（`-mini-count-ops -canonicalize`），计数将发生在塌缩之前（仍是 4）。建议改为"同一输入，第二条命令在计数前多跑了 `-canonicalize`"。计数 4→3 本身已实测无误，只影响表述。
- **置信度**：高。

#### 3. "`Operation::erase` 是 `PatternRewriter` 同名方法"这半句不成立
- **原文**："- **定位**：审自己的 `matchAndRewrite`：所有改 IR 的调用是不是都带 `rewriter.` 前缀？（`Value::replaceAllUsesWith` 和 `Operation::erase` 是 `PatternRewriter` 同名方法的"无通知版"，编译器不会替你区分。）"
- **依据**：MLIR 18.1.8 `PatternMatch.h` 中 `RewriterBase` 提供的是 `replaceAllUsesWith`（与 `Value::replaceAllUsesWith` 确实同名）和 `eraseOp`/`eraseBlock`——不存在名为 `erase` 的 rewriter 方法；`Operation::erase` 对应的是 `rewriter.eraseOp`，两者并不同名。顺带值得点破：这个命名差异本身就是 API 的刻意设计提示（eraseOp 少一个"Op"就绕过通知），教学上反而是亮点。
- **置信度**：高（本机头文件已核对）。

#### 4. §5.2 ③ 对 Day 47 的前瞻描述与实际实现有出入
- **原文**："**③ 挂钩为什么一行就够**（第 96～99 行）：`results.add<SimplifyDoubleRelu>(context)` 把 Pattern 注册进驱动发来的集合。Day 46 的 `Add(x, 0) → x` 会给 `mini.add` 加同样的挂钩，Day 47 的常量折叠走 `mini.constant`——**每条规则挂在自己的算子上**，驱动收集时自然拼成完整规则库。"
- **依据**：day-047 的常量折叠核心在 `mini.add` 的 fold（`lib/AddFold.cpp` 同时实现 mini.add 与 mini.constant 两条 fold，外加 `MiniDialect::materializeConstant`），并非"走 `mini.constant`"一家；且 fold 钩子由驱动逐 op 调用，不进入 `getCanonicalizationPatterns` 收集的"规则库"。与【错误】2 同源但涉及另一处行文，建议一并改写，避免读者带着错误预期进入 Day 47。
- **置信度**：高（对照 day-047 代码与其 README）。

#### 5. "三处接缝"之外还有一处注释改写未说明，且该注释与仓库现状矛盾
- **原文**："在 Day 44 的 mini 工程上，今天只有**三处接缝**（无一处碰 mini-opt）："
- **依据**：diff 显示 day-044→day-045 还改写了 `lib/ShapeInferencePass.cpp` 第 111～115 行的注释块（去除注释后两文件代码逐字一致，不影响"三处功能性接缝"的结论）。但新注释自述"day-044 交付的代码就栽在这一行……今天开工前先补上这个修复"，而 day-044 的文件里这行代码已是修复后的 `::mini::` 写法（day-044 README §6.1 记录的正是这次修复的来龙去脉），注释与仓库现状对不上。建议在 §5.1 提一句"另有一处注释澄清"，或修正该注释的时态表述，免得读者 diff 时困惑"到底改了几处"。
- **置信度**：改动事实高（已 diff 比对）；注释与 day-044 现状的矛盾为高；作者想表达的历史语境无法独立还原。
