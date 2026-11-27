# 第 55 天技术校对报告

审阅对象：`tutorials/week-008/day-055/`（README.md、`code/mini_fuse_accept.py`、`code/test_negative_acceptance.py`、`code/mlir-mini/` 全部源码与 inputs/outputs、`images/` 下 4 张 SVG）。审阅环境与教程自述一致：aarch64 Linux、g++ 9.4.0、Ubuntu LLVM 18.1.8、Python 3.11.4 + numpy。已实际执行：`python3 mini_fuse_accept.py`（14/14，rc=0）与 `--no-type-guard`（11/14 ✘，rc=1），两次运行的完整输出与冻结文件 `outputs/python-accept-full.txt`、`outputs/python-accept-no-type-guard.txt` 逐字节一致；`python3 test_negative_acceptance.py` 16/16 通过（0.008s）；`mini-accept` 在临时目录全新 CMake+Ninja 构建成功，M01～M10 逐一重跑的 .out/.err 与仓库冻结输出逐字节一致（仓库产物未改动）；主线数值 %m/%s/%r 手算核对无误；MLIR 18 头文件与上游 release/18.x 源码（PatternMatch.h、GreedyPatternRewriteDriver.h/.cpp、DialectConversion.h）逐条核对；第 50～54 天教程与主计划第 60/74 天条目交叉核对。特别核实：§3.3 关于「MLIR 对 matchAndRewrite 的约定是返回 failure 就不许动过图、贪心驱动不替你回滚」的论断属实——MLIR 18 `PatternRewriter::canRecoverFromRewriteFailure()` 默认 false，贪心驱动（GreedyPatternRewriteDriver）未覆写它且无回滚机制，上游源码的 ExpensiveChecks 注释明确把「Pattern returns failure but the IR has changed」列为 broken pattern；全库唯一覆写为 true 的是 DialectConversion 驱动（事务式回滚），与本教程所述不冲突。

## 【错误】

#### 1. §7 错误 1 的归属天数错误：「改接事故」发生在第 52 天，不是第 54 天
- **原文**：“第 54 天的改接事故里，`relu(a+b)` 顶替 `a+b` 喂给第二个使用者时，verify 一样通过，数值悄悄变错。”
- **依据**：该事故是第 52 天的核心案例：day-052 README §1 的选项 C 原文为「改接 %t：第二个 `mini.add` 会拿到 `relu(a+b)` 而不是 `a+b`——图结构完全合法、`verify` 通过、**数值悄悄变错**」，其图 2、§5.1 与错误清单均围绕它展开；而 day-054 全文检索不到「改接」或「relu(a+b)」——第 54 天的事故是「抢跑」（Pattern 集 [P51,P3] 两种遍历收敛到两个不同形态），与「数值悄悄变错」不是同一类事故。第 55 天 §1/§10 自己也把「两种遍历最终 IR 一致」归给第 54 天、把「多使用者铁律」归给第 52 天。应改为「第 52 天的改接事故」。
- **置信度**：高（第 52/54 天教程原文可直接核对）。

#### 2. 「parse 阶段就拦下／parse 就报错」：形状错误由 op Verifier 在 verify 阶段报出，parse 阶段不运行 Verifier
- **原文**：“M09 的 Verifier 报错（`outputs/M09_bad_shape.err`，parse 阶段就拦下，Pattern 根本没运行）：”
- **依据**：MLIR 的 `parseSourceFile` 只做语法解析与构 op，不调用算子 Verifier；M09 报错文案「'mini.add' op 两个操作数 shape 不匹配」在整个工程里唯一定义处在 `MiniDialect.cpp` 的 `AddOp::verify()`（emitOpError），由 `mlir::verify()` 触发。`mini-accept.cpp` 自己就是两步分开调用的：`parseSourceFile<ModuleOp>(...)` 成功返回后才 `failed(verify(modA.get()))`；`outputs/M09_bad_shape.err` 里也只有这一条带 `loc("inputs/m09_bad_bias_shape.mlir":7:8)` 定位的 verify 诊断，没有任何 parse 错误（语法完全合法的 .mlir 文本本就能 parse 成功）。§1 表格的「Verifier（parse 就报错）」同理不准；Python 层更是 build 之后跑 `verify_graph`，压根没有 parse 环节。对初学者这是真实易踩的坑：以为 Parser 会做类型/形状检查，实际结构检查发生在 parse 之后的 verify 阶段。应改为「verify 阶段就拦下」。
- **置信度**：高（报错文案唯一定义处、工具源码两步调用、冻结 .err 内容三重核实）。

#### 3. 图 2 把 C12 的 bias 标成 2x3：Python 语料 C12 的 bias 是 1x2，2x3 是 MLIR 层 M09 的形状
- **原文**：“C12 Mismatch／C13 需广播”
- **依据**：该表行对应的 `images/02-gates.svg` 第②行标注「bias 2x3、[2] 对乘积 2x2」，且图题写明「（Python 层 14 用例的真实判决）」；但 Python 层 C12 的 bias 是 `tensor<1x2xf32>`（`mini_fuse_accept.py` 的 `build_c12` 用 `tt(1, 2)`，FEED 注释也是「%v1: 1x2」）——2x3 是 MLIR 层 `inputs/m09_bad_bias_shape.mlir` 的 `%arg0: tensor<2x3xf32>`。1x2 对 2x2 同为 rank-2、形状不同，同样判 Mismatch，判决与闸门分流不受影响，但图中的具体形状把 M09 的数据套在了 C12 标签下，与图题「Python 层」自相矛盾。建议图中改为「bias 1x2（C12）／2x3（M09）」或去掉具体形状。
- **置信度**：高（代码与输入文件可直接核对；仅图内标注错误，README 正文未复述该形状）。

## 【存疑】

#### 1. §5.2「与 Python 层完全同构」略强：Pattern 集与闸门确实同构，驱动机制并不同构
- **原文**：“验收管道 = 第 54 天收敛出的最终形态 Pattern 集（P1 两阶段／P2 吸收／P51g 让位版／P3 直接三算子）＋ 今天的类型闸门，与 Python 层完全同构。”
- **依据**：Pattern 层面已逐条核对，同构成立：4 个 Pattern 的 root 算子、benefit（P3=2，其余=1）、收手条件（乘积单使用者、bias Same、让位规则、f32 闸门覆盖 mm 两个输入＋bias）、类型闸门覆盖面在两层一一对应，且本日 24 例两层判决全部一致。但驱动不同构：Python 的 `run_pipeline` 每次改写成功就 `break` 出去从头重扫整张图（`while True` + 内层 `break`），MLIR 18 的贪心驱动维护工作表增量调度、把改写波及的算子重新入队（本报告核对了 release/18.x 的 GreedyPatternRewriteDriver.cpp；day-054 技术校对报告亦以插桩证实其工作表行为）。两者在本语料上殊途同归，但「完全同构」若被读者理解为「驱动行为也一致」则过强——换个更大的语料（例如存在震荡或顺序敏感的 Pattern 集）时两种驱动的收敛路径可以不同。另外 R2 断言的强度两层也不一致（见【建议】第 4 条）。建议措辞改为「Pattern 集与闸门完全同构，驱动各自实现，本语料判决一致」。
- **置信度**：中高（Pattern 集已逐条核对；驱动差异依据 MLIR 18 源码与第 54 天插桩结论，本日未重新插桩验证）。

## 【建议】

#### 1. §4.1「全部沿用主线尺寸…第 51 天起没换过」与当天语料和历史均不符
- **原文**：“14 个用例全部沿用主线尺寸（`2×3 · 3×2` 矩阵家族，第 51 天起没换过）”
- **依据**：14 例中 C03（%a2/%b2）、C09（%x/%y）、C14（%x/%y）用的是 2×2 家族（代码注释自述「第 52 天同款」），并非「全部」2×3·3×2；且 2×3·3×2 主线出自第 50/53 天（day-050 原文「贯穿全文的例子沿用第 37 天的 shape 家族：`2x3 · 3x2 + bias 2x2 → relu → 2x2`」，day-53 同款），第 51/52 天的贯穿例子恰是 2×2（day-051 开篇「输入是两个 `2×2` 的 f32 张量」），「第 51 天起没换过」的起始日也对不上。建议改成「主线 2×3·3×2（第 50/53 天口径）＋ Add+Relu 小例子的 2×2（第 51/52 天同款）」。
- **置信度**：高（当天 FEED 与第 50/51/52/53 天教程原文可直接核对；不影响任何技术结论）。

#### 2. §5.3 M06 引文标注出自 `.err`，但末行 verdict 来自 `.out`
- **原文**：“M06 的真实记录（`outputs/M06_f64_add_relu.err`）：”
- **依据**：`outputs/M06_f64_add_relu.err` 只有 6 行（A/B 两路决策日志各 3 行）；引文末行「verdict=identity  accept=PASS」打印在 stdout，实际存于 `outputs/M06_f64_add_relu.out`。引文内容本身与冻结输出逐字一致，仅出处标注少了 .out；建议写成「（.err 决策日志＋.out 末行）」或删去末行。
- **置信度**：高（两份冻结输出可直接比对）。

#### 3. §4.3「真实节选」删行未加省略标记，`same` 用到的 `ref_out`/`new_out` 定义不在引文里
- **原文**：“每个用例都要过五关（真实节选）：”
- **依据**：所引代码块每一行都能在 `run_one_case` 里逐字找到，但中间被静默删掉了若干行：`ref_out = evaluate(g0, FEED)`、`new_out = evaluate(g1, FEED)`（`same = ...` 直接引用这两个变量，引文里看不到它们的来源）、`log = rec["log"] if verbose else None` 与 `log=log` 实参、`rec["got"]/"bypass_ops"/"post_ops"/"post_cost"]` 登记行，以及 `if expect_kind == "identity"` 的 else 分支（R1 最终算子名单检查）与「融合后 Verifier 复查通过」两条 check。§4.2 的节选用「# ……」标过省略，这里没有；建议补省略号或至少保留 `ref_out`/`new_out` 两行定义。
- **置信度**：高（与 mini_fuse_accept.py 逐行比对）。

#### 4. mini-accept 的 R2 只逐字比对 A 路：B 路恒等性仅靠 R1 的算子名单间接覆盖
- **原文**：“bool r2 = (postA == preIR);”
- **依据**：mini-accept.cpp 的 R2 断言只比 A 路（bottom-up）产物与输入 IR 的逐字一致；B 路（top-down）没有对应的 `postB == preIR` 检查，只被 R1 的 `namesA == namesB`（算子名单，不含 SSA 名与操作数）间接覆盖。本日 10 例上 B 路确实未动图（A/B 两路 .out 的 IR 已逐一比对一致），断言强度不影响当前结论；但 README 与图 3 表述的「R2 要求负例 IR 逐字恒等」强于实现——若未来某个 Pattern 在 B 路改了值名而不改算子名单，现状抓不到。建议补一行 `bool r2b = (postB == preIR);` 一并入 ok。
- **置信度**：高（代码事实明确；对当前语料无实际影响）。

#### 5. 练习 4 的 `--set=steal` 旗标属于第 54 天的 mini-fuse3：mini-accept 不支持该旗标，且未知旗标会被静默忽略
- **原文**：“把 `mini-accept.cpp` 的 B 路改成 `--set=steal`（第 54 天的抢跑集：P51 不带让位规则）”
- **依据**：`--set=...` 是 day-054 `mini-fuse3.cpp` 的旗标（其用法注释与 run_all.sh 均可核对）；`mini-accept.cpp` 的参数解析只认 `--expect=`，其余命令行参数一律静默忽略——读者若直接执行 `./build/mini-accept input.mlir --set=steal`，会得到与平时完全相同的运行且无任何提示，容易误以为「做完了实验」。练习本意是把抢跑 Pattern 集移植进 B 路（需改代码），建议措辞改为「把 B 路的 Pattern 集换成第 54 天 `--set=steal` 的集合（需改代码，mini-accept 没有 --set 旗标）」。
- **置信度**：高（两份源码的参数解析可直接核对）。

#### 6. 代码使用 `Type::dyn_cast` 成员函数：MLIR 20 起已标记 deprecated，建议注明版本适用范围
- **原文**：“热身需要 Python 3 + numpy；正餐需要 C++17 编译器与 MLIR 18”
- **依据**：`mini-accept.cpp` 的 `allF32` 用 `v.getType().dyn_cast<RankedTensorType>()`，在教程锁定的 MLIR 18.1.8 下编译运行均无问题（本报告已全新构建验证）；但上游 release/20.x 的 `mlir/IR/Types.h` 已给 `Type::dyn_cast` 等成员函数加上 `[[deprecated("Use mlir::dyn_cast<U>() instead")]]`。教程锁定 MLIR 18 并无错误，只是读者环境升级到 MLIR 20+ 后会出现弃用告警（MLIR 19 是否已弃用未逐一核实）；建议在 README 或代码注释加一句「MLIR 20+ 请改用自由函数 `mlir::dyn_cast`」。
- **置信度**：高（release/20.x 头文件已核对；19.x 未核实，已注明）。
