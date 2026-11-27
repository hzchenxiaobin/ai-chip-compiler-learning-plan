# 第 49 天技术校对报告

审阅方法：在教程声称的同一环境（Ubuntu 20.04.5 aarch64、gcc 9.4.0、cmake 3.20.5、ninja 1.10.0、Ubuntu LLVM 18.1.8）下于临时目录重新构建 day-049 工程，重放 `run_all.sh` 全部 17 个输出与 5 组断言（与冻结输出逐字节一致）；另构建 day-048 原工程与“删去 SimplifyMulOne 类型护栏”的变体工程做对照实验；核对 MLIR 18.1.8 安装头文件与上游 release/18.x 源码（`PassRegistry.cpp`、`GreedyPatternRewriteDriver.cpp`、`Passes.td`、`STLExtras.h`、`MlirOptMain.cpp`、`FoldUtils.cpp`）。仅报告问题，未改动任何教程原文、代码与冻结输出。

## 【错误】
#### 1. “错误 4”声称 Day 47 的折叠路径在真实编译器下编不过——与仓库冻结代码和实测构建相矛盾
- **原文**：“- **现象**：两连报错——`error: no declaration matches 'mlir::Operation* mini::MiniDialect::materializeConstant(...)'`；以及 `error: ... has no member named 'begin'`（`DenseElementsAttr` 上调 `lhs.begin<APFloat>()`）。”
- **依据**：两个报错都不可能由仓库中的 Day 47/48 代码产生。(1) day-047/day-048 的 `MiniDialect.td` 均已用 `extraClassDeclaration` 在 tblgen 生成的 `MiniDialect` 类体内声明了 `materializeConstant(...) override`（day-047 `MiniDialect.td` 第 31～36 行），类外定义因此有匹配声明。实测：在教程声称的同一工具链下完整构建 day-048 原工程（与 day-047 的这两个文件仅注释差异），编译链接全部成功，`mini-opt --version` 输出 18.1.8。C++“类外定义须对应本类声明”的规则本身没错（§6 原因第一条），但前提“只继承没声明”对本仓库代码不成立。(2) day-047 的 `AddFold.cpp` 第 102～107 行已经使用 `getValues<llvm::APFloat>()`，且其注释明确写着“MLIR 18 的 DenseElementsAttr 没有 begin<T>()/end<T>()，标准入口是 getValues<T>()”——`begin<APFloat>()` 从未出现在冻结代码里，“从未真实编译过留下的坑”无从谈起。day-047 README 也记载“全部实测通过”。该叙事还同步写进了 §5.2（“把 Day 47 的代码放进真实编译器……立刻报 `no declaration matches`”）、§2 末尾（“两个”从未真实编译过“的坑”）以及 `MiniDialect.td`/`MiniDialect.cpp`/`AddFold.cpp` 的注释。改用 `hasConstantMaterializer = 1` 与 `zip_equal` 本身是合理的规范化（上游 arith 方言即用该开关；`begin<T>()` 在 MLIR 18 `DenseElementsAttr` 上确实不存在，已核对 `/usr/lib/llvm-18/include/mlir/IR/BuiltinAttributes.h`），但“旧代码编不过、复盘时真实暴露”的情节是不实陈述，须改写为风格/规范层面的动机。
- **置信度**：高（基于冻结代码 diff、两处完整构建实测与 day-047 自述记录；唯一保留是 day-049 作者可能在一个未入库的中间状态遇到过这些报错，但那不是“本周代码”的状态）。

#### 2. §5.4 称去掉类型护栏后“使用者的类型就对不上，重写反而制造非法 IR”——对 combo_shape 用例不成立
- **原文**：“把一个 `2x2` 的结果整体替换成 `?x2` 的值，使用者的类型就对不上，重写反而制造非法 IR（Day 46 实测过的坑）。”
- **依据**：实测反驳。在临时副本中删去 `SimplifyMulOne` 的类型护栏（仅此一处）重新构建后跑 `-canonicalize combo_shape.mlir`：mul 被塌缩，输出为 `%0 = mini.matmul ... -> tensor<?x2xf32>`、`%1 = mini.relu %0 : tensor<?x2xf32> -> tensor<2x2xf32>`，进程 rc=0；`--verify-each`（mlir-opt 默认开启，见 MlirOptMain.cpp 中 `cl::init(true)`）与独立重新解析均通过——IR 合法。原因是本例中 mul 结果的使用者是 `mini.relu`，其 Verifier（`ReluVerifier.cpp`＋`ShapeRelation.h`）对动态维保守放行（`?x2` 与 `2x2` 记 Same），这正是教程自己在 §2 第 2 步讲过的事实，与“使用者的类型就对不上”自相矛盾。Day 46 的真实复现（`type_guard_negative.mlir`）成立是因为被替换的值直接流入 `func.return`，而 func 的 ReturnOp Verifier 做严格类型相等检查——day-049 把该结论错误地推广到了“使用者是宽容 Verifier”的 combo_shape 场景。连带问题：同句“护栏拦下的不是合法重写，是**信息不足的重写**”在本例中也不准确——该重写恰好是语义恒等且可通过验证的，护栏拦下它是因为 Pattern 只看局部、无法对“所有可能使用者的类型检查规则”给出证明，属保守策略而非“必然非法”。图 3 的 alt 文本与 `images/03-shape-unlock.svg` 内文字（“把 2x2 的结果换成 ?x2 的值，使用者的类型就对不上”）重复了同一不实论断。准确的表述应区分两种使用者：对 `func.return` 这类严格检查的使用者该重写会产生非法 IR（Day 46 的情形）；本例中它会得到“合法但类型不再一致”的 IR，护栏仍然合理，但理由是“局部证明不了安全”，不是“必然非法”。
- **置信度**：高（删护栏变体的完整构建＋三种验证途径均通过；`ReluVerifier.cpp`/`ShapeRelation.h` 源码可直接核对）。

#### 3. §2 改动表称 `zip_equal` “元素数不等时编译期报错”——实为运行期断言，且 Release 构建下关闭
- **原文**：“| **配对收紧** | `AddFold.cpp`：`zip` → `zip_equal` | 元素数不等时编译期报错，而不是静默越界 |”
- **依据**：`llvm::zip_equal` 的等长检查不是编译期检查。`/usr/lib/llvm-18/include/llvm/ADT/STLExtras.h` 第 868～875 行：“zip iterator that assumes that all iteratees have the same length. In builds with assertions on, this assumption is checked before the iteration starts”，实现是 `assert(all_equal({range_size(t), range_size(u), ...}))`——运行期断言，且仅在开启断言的构建中生效。元素个数是运行期属性（dense 属性里的数据量），编译器无法在编译期比较。教程自带的构建命令是 `-DCMAKE_BUILD_TYPE=Release`（NDEBUG，断言被编译掉），此时若真出现不等长（lhs 比 rhs 长时按 zip_first 语义会越过 rhs 末端），仍是静默越界而非报错。本代码路径中类型护栏已保证两属性元素数相等，实际不会触发，故无现实 bug；但表中给出的安全性质描述不实。`AddFold.cpp` 注释里“元素数不等直接报错”若指运行期断言则可成立，README 的“编译期”必须改。
- **置信度**：高（STLExtras.h 源码逐行核对；实际影响为零这一判断置信度亦高——`getRes().getType()` 与两操作数类型相同的护栏先于遍历生效）。

#### 4. §5.1 文件布局注释称 `run_all.sh` “4 组断言”——实为 5 组，与本文另两处自述矛盾
- **原文**：“├── run_all.sh                     # 一键重放（17 个输出 + 4 组断言）”
- **依据**：`run_all.sh` 实际包含五组断言：A（06==07）、B（13==07）、C（20==02）、D（计数 remark）、E（disable 带括号失效），本文第 6 行（“17 个输出文件＋5 组断言全部实测通过”）与 §5.1 正文（“五组 diff/计数断言（A……E）”）也都写的是 5。17 个输出文件的数量经实测核对无误（01～07、10～18、20 共 17 个）。顺带指出代码侧的同类陈旧注释：`run_all.sh` 文件头第 11 行仍写“脚本末尾自动做三组断言（全链 vs 默认、预算、组合 vs 推导+规范化）”，其中“组合 vs 推导+规范化”断言在当前脚本中已不存在（见【建议】第 3 条）。
- **置信度**：高（脚本内容与 README 多处自述可直接核对，本次重放五组断言全部实际通过）。

## 【存疑】
- 无。

## 【建议】
#### 1. §3.3 的 debug name 示例写法与 g++ 实际生成的不一致
- **原文**：“g++ 生成的名字是 `{anonymous}::SimplifyDoubleRelu` 这种随编译器变化的字符串——难敲也不可移植”
- **依据**：MLIR 18 的 `RewritePattern::create` 用 `llvm::getTypeName<T>()` 取 debug name（`PatternMatch.h` 第 282 行），GCC/Clang 路径基于 `__PRETTY_FUNCTION__`（`llvm/Support/TypeName.h`），匿名命名空间中的 `SimplifyDoubleRelu` 实际生成 `(anonymous namespace)::SimplifyDoubleRelu`（含括号和空格）——`{anonymous}::` 是 demangler 风格的转写，g++ 并不产生这个字符串。论断的实质（随编译器变化、难敲、不可移植）完全成立，且实测按 `SimplifyDoubleRelu`、`(anonymous)::SimplifyDoubleRelu` 过滤均匹配不上（输出 6 ops）；顺带可补一句更强的理由：真实名字含空格，而文本管道选项以空格分隔（`PassRegistry.cpp` 的 `parseNextArg`），带空格的 debug name 几乎无法作为过滤值传入。建议改为实际字符串并注明出处，避免读者按 `{anonymous}::...` 去猜。
- **置信度**：高（TypeName.h 与 PatternMatch.h 源码核对＋命令行实测；属表述精度问题，不影响结论）。

#### 2. 图 4/§5.5 “擦除 → 操作数定义者回表”是无条件的说法，MLIR 18 实际带条件
- **原文**：“中间蓝框是回表的三种触发：改边 → 使用者回表；擦除 → 操作数定义者回表；物化新常量 → 新 op 入队。”
- **依据**：release/18.x `GreedyPatternRewriteDriver.cpp` 的 `addOperandsToWorklist`（第 666～678 行）只在操作数的使用数降至 0 或 1 时（`!operand.use_empty() && !operand.hasOneUse()` 则跳过）才把定义者回表，注释说明这是基于“零使用者可被删除、单使用者常有更多规范化机会”的启发式，并非无条件回表。图 4 依据该源码绘制，combo 的两次回表标注（mul 回表、外层 relu 回表）经机制核对均成立，三种触发中另外两种（`notifyOperationModified` → 使用者回表；物化/新建 op → 入队）与源码一致。建议在图或图注补上“（仅当该操作数剩余使用数 < 2）”的限定，避免读者得出“任何擦除都会把全部操作数定义者拉回清单”的过强结论。
- **置信度**：高（源码逐行核对；对本日实验结论无影响）。

#### 3. `run_all.sh` 文件头注释陈旧：写“三组断言”且列出不存在的断言项
- **原文**：“并在末尾自动做五组 diff/计数断言（A：全链 == 默认；B：预算 == 默认；C：括号陷阱 enable 侧；D：计数 remark；E：括号陷阱 disable 侧）。”
- **依据**：README 此处（以及第 6 行、§8 验收清单）与脚本实际行为一致（本次重放五组断言全部通过）；但 `run_all.sh` 自身的文件头注释（第 11 行）仍写“三组断言（全链 vs 默认、预算、组合 vs 推导+规范化）”——数量不对，且“组合 vs 推导+规范化”这个断言在当前脚本里并不存在（12 号输出只是被生成，未参与断言）。另外脚本第 91 行“断言 D：四个计数 remark”实际 grep 的是五个文件（14/15/16/17/18，五个 remark）。属代码注释与实际行为不同步，建议下次迭代代码时一并修正，以免读者以脚本注释为准。
- **置信度**：高（脚本内容逐行核对）。
