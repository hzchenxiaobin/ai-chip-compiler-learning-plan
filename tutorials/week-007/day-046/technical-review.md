# 第 46 天技术校对报告

校对环境与教程声称一致（Ubuntu 20.04.5 LTS aarch64 / mlir-opt-18 18.1.8 / gcc 9.4.0 / cmake 3.20.5 / ninja 1.10.0 / numpy 1.26.4）。以下判断均经本机实测或源码核实：全新重建 mini-opt（ninja 报 [18/18]，共 18 个构建步）；`bash run_all.sh` 完整重放——8 个 FileCheck 探针全绿、主线 (a)(b)(c) 的 `mini.add` 计数 1/0/1、非零 bias 回归通过、对照实验 A（删护栏 rc=1，报错信息逐字一致）与实验 B（`==` 版 2→1）复现成功；上游 arith 探针输出、§5.3/§5.5 各输出块、ieee_witness.py 节选均与实测逐字一致；错误 1 的"无开关"变体在临时目录复现（AlgebraicSimplification.cpp:164/169 同款报错，构建 rc=1）；练习一/练习二按 README 描述独立验证通过（含 `dense<0x7FC00000>` 的 NaN 位模式写法）；核心机制论断（canonicalize 对已注册算子收集 Pattern、贪婪驱动按 benefit 降序先试高收益、`isOpTriviallyDead` 的简单 DCE、`OperationFolder::insertKnownConstant` 的常量前移、`APFloat` 的 `operator==`/`isNegZero`/`isExactlyValue` 语义、`DenseElementsAttr::isSplat` 判定、`tblgen` 生成 `getCanonicalizationPatterns` 声明与 `getValue()` 返回 `DenseElementsAttr`）已对照本机 LLVM/MLIR 18.1.8 头文件、构建生成的 MiniOps.h.inc 及 llvm-project release/18.x 源码逐条核实。

## 【错误】
#### 1. 首次构建步数写成 17，实测为 18
- **原文**："cmake --build /tmp/day046/build     # 首次约 1~3 分钟，17 个构建步"
- **依据**：删除 /tmp/day046 后从 day-046 源码全新配置并构建两轮，ninja 均报告 `[18/18]`，即 18 个构建步；对照构建 day-045 的 mini 工程为 `[17/17]`（17 步）。day-046 相对 day-045 恰好多一个编译目标（新增 `lib/AlgebraicSimplification.cpp`），步数 +1，本句的"17"疑为沿用 Day 45 的计数。构建时长约 1～2 分钟，"约 1~3 分钟"属实。
- **置信度**：高（两轮独立全新构建核实；影响仅为计数口径，不影响可复现性）。

#### 2. "负例一个字节不许变"在字节层面不成立
- **原文**："5. **打印**：输出 `.mlir`，正例图更短，负例一个字节不许变。"
- **依据**：实测所有负例探针的输出与输入在字节层面均不同：文件头注释全部丢弃、`func.return` 打印为 `return`、SSA 名全部重编号（如 `type_guard_negative.mlir` 输入 `%z = mini.constant dense<-0.0>`、输出 `%0 = mini.constant dense<-0.000000e+00>`）、浮点字面量改为科学计数法。负例"不许变"的可验证口径是算子集合与语义不变（8 个探针的 FileCheck 已验证，如 `CHECK: %[[S:.*]] = mini.add %arg0, %[[Z]]`），不是字节相等。初学者若照字面 diff 输入输出，会看到大量差异并误以为 Pattern 失守。建议改为"负例一个算子都不许少"。
- **置信度**：高（已对全部负例探针实测比对；影响小，属表述口径问题）。

## 【存疑】
#### 1. "x + (-0.0) = x 对一切 x 成立，严格安全"未覆盖非默认舍入模式
- **原文**："IEEE 754 规定 `x + (-0.0) = x` 对一切 x 成立（含 ±0.0、NaN、±Inf），严格安全"
- **依据**：IEEE 754-2019 第 6.3 节规定：两个异号操作数的和恰为零时，除 roundTowardNegative 外取 `+0`，roundTowardNegative 下取 `-0`。本机用 C 的 `fesetround(FE_DOWNWARD)` 实测：`(+0.0) + (-0.0)` 的 signbit=1（即 `-0.0`），与 x=+0.0 不一致；roundToNearest 下 signbit=0（一致）。即 x=+0.0 在 roundTowardNegative 舍入模式下是 `Add(x, -0.0) → x` 的真实反例，"对一切 x 成立、严格安全"只对默认舍入模式成立。同节"同号零相加得同号零，异号零相加得 `+0.0`"的后半句同样略去了该例外。教程的**实现取舍**没有问题——上游做同一假设（实测 `mlir-opt-18 -canonicalize` 对 `arith.addf %x, %cst(-0.0)` 无条件消除，且 arith.addf 不带 fastmath 标志），numpy 见证脚本也只能测默认舍入；但把"默认舍入模式下的结论"表述成"IEEE 754 规定……对一切 x"，过于绝对。
- **置信度**：高（标准条文与本机 fesetround 实测双重验证；实际影响小——mini 与上游均按默认舍入模式设计，仅建议措辞补一句舍入模式前提）。

#### 2. 对 Day 47 的"同一套骨架/匹配"表述与 Day 47 实际实现矛盾
- **原文**："今天把常量匹配、属性读取、收益前提走通，Day 47 的常量折叠（把整个运算在编译期算掉）只是在这套匹配基础上再加一步"算出来""
- **依据**：day-047 的常量折叠走的是 fold 钩子而非这套 Pattern 骨架：`day-047/code/mini/include/mini/MiniOps.td` 给 `mini.add`/`mini.constant` 打开的是 `let hasFolder = 1`，本体在 `lib/AddFold.cpp` 的 `AddOp::fold(FoldAdaptor)`——操作数常量值由驱动经 FoldAdaptor 递入（不需要 `getDefiningOp` 常量匹配），物化走 `MiniDialect::materializeConstant`，全程拿不到 PatternRewriter；day-047 README 自述"相比 Day 45/46，今天是**另一条生产线**：Pattern 拿 `PatternRewriter` 亲手改图；fold 连 Rewriter 的影子都见不到"。同框架的表述另有两处：图 1 图注"Day 47 的常量折叠连结果都算出来，骨架从未变过"，§5.2"常量匹配的骨架是公共资产，明天常量折叠还会再用它"——实测 grep day-047 代码，`isSplatConstant` 只出现在 `AlgebraicSimplification.cpp`（第 46 天遗留文件），`AddFold.cpp` 并未复用它。概念层面（读常量、判值、护栏）确有延续，但"只是再加一步""骨架从未变过""还会再用它"三处叠加，易让读者带着"fold 也是 RewritePattern"的错误预期进入 Day 47。
- **置信度**：高（已对照 day-047 代码与其 README 核实；因"骨架/匹配"可作概念性解读而非机制性表述，列存疑而非错误，建议下一版统一为"概念延续、机制换轨"的口径）。

#### 3. 图 1 的 Day 47 预告写"Fold 接手后能救回一半"，常量折叠救不了 type_guard
- **原文**："想让这条 add 能被优化，正确做法是先跑 `-mini-infer-shape` 把 `?` 细化成数字（§5.3 主线实验 (b)），而不是拆安全带"
- **依据**：正文正确指出 type_guard 拦下的 add 出路是 shape 推导；但 `images/01-overview.svg` 的 Day 47 预告框另写"今天拦下的 type_guard，Fold 接手后能救回一半"。常量折叠要求两个操作数都是编译期常量——day-047 的 `AddFold.cpp` 对 FoldAdaptor 里非常量的操作数直接返回 `{}`；而 `type_guard_negative.mlir` 的 lhs 是函数入口参数（§3.1 已说明 def-use 边上找不到定义者），fold 无法对它点火。day-047 的全文与测试也未提及救回 type_guard 用例（grep 无命中）。该图内一句话与正文给出的正确出路不一致，疑为预告措辞失准；本报告仅记录，不改冻结图片。
- **置信度**：中（图内文字含义模糊，"一半"所指无法还原，不排除作者另有所指；正文本身无误）。

## 【建议】
#### 1. 图 1 把 Pass 顺序实验标注为"5.4 节实测"，实际在 §5.3
- **原文**："5.4 对照实验：亲手弄坏两处，看负例怎么守住"
- **依据**：`images/01-overview.svg` 的 Day 48 预告框写"今天 5.4 节实测：顺序一换、优化就丢"，但三种 Pass 顺序的对照实验位于 §5.3（(a)(b)(c) 命令与图 3）及 §6 错误 4；§5.4 只做"删护栏"与"`==` 比较"两个对照实验。跨引错节号会让读者在 §5.4 找不到顺序实验，建议下一版修订图内文字为"5.3 节"。
- **置信度**：高（章节内容已核对）。

#### 2. run_all.sh 在残留构建目录时可能对旧二进制给出假绿
- **原文**："以下全部是本机真实执行结果（`bash run_all.sh` 一键重放，环境见文首）"
- **依据**：本机复现：当 /tmp/day046/build 残留指向另一源路径的 CMake 缓存时，第 1 步 cmake 报"source does not match the source used to generate cache"并以 rc=1 失败，但脚本 `set -uo pipefail` 未含 `-e`，不中止——后续 8 个探针全部对着旧二进制运行并照常打印 rc=0，"一键重放"给出假绿。建议构建步骤失败即退出（如 `cmake --build "$BUILD" || exit 1`），或先校验 build 目录缓存与当前源路径一致。全新环境（空 /tmp）下无此问题。
- **置信度**：高（本机复现；属健壮性改进，不影响教程陈述的事实正确性）。

#### 3. 回归用例输出中常量前移与 SSA 重编号未在 README 解释
- **原文**："回归用例 `pipeline_bias_nonzero.mlir` 同时确认：bias 是 `[[-1,-2],[-3,-4]]` 时，同样的命令下 add 原样保留——代数化简只对恒等运算动手（FileCheck 通过，rc=0）"
- **依据**：实测该命令的输出里 bias 常量被移到 matmul 之前、SSA 名全部重编号（%0～%3），README 未解释；`code/pipeline_bias_nonzero.mlir` 的文件注释自述"-canonicalize 的驱动会把 ConstantLike 常量 hoist 到入口块最前面（OperationFolder 的登记动作，教程 5.3 节展开）"，但 §5.3 并未展开。机制已核实：MLIR 18 `FoldUtils.cpp` 的 `OperationFolder::insertKnownConstant` 在装填工作表时对常量执行 `op->moveBefore(&insertBlock->front())`，本机构造的零改写对照用例（只有 relu/常量/add，无任何 Pattern 点火）同样观察到常量前移——搬家是驱动的装表动作，不是 Pattern 干的。读者 diff 输入输出时会困惑"add 没动、常量却搬家了"；本轮审阅以新增图 4（images/04-output-reformat.svg）承接该说明。
- **置信度**：高（输出与机制均已实测核实）。

#### 4. §5.5 的"真实输出"块里混入了实测输出没有的行尾注释
- **原文**："%0 = arith.addf %arg0, %cst : f32      // +0.0：上游也不消"
- **依据**：实测 `mlir-opt-18 -canonicalize arith_probe.mlir` 的输出不含任何行尾注释（IR 本身与该块逐字一致）；§5.3 的探针结果表同样在脚本真实输出"[文件] FileCheck 通过 (rc=0)"之外追加了说明列。与 day-045 审阅报告建议 1 同款问题：代码块冠以"真实输出"而混入人工标注，读者复跑时对不上。建议注明"行尾注释为人工标注"或将注释移出代码块。
- **置信度**：高（已实测比对）。

#### 5. §3.3 说"§5.5 有完整真实输出"，§5.5 自称"节选"
- **原文**："这张表不是抄书，是 `ieee_witness.py` 用 numpy 1.26.4 真算出来的（§5.5 有完整真实输出）"
- **依据**：§5.5 的输出块标题写"真实输出节选"，实际仅含表 1/2/4 各一行、符号零两行，表 3（x*1.0）与"整数没有这个烦恼"部分未展示；脚本完整输出共 20 行。两处口径不一，建议统一为"节选"或在 §5.5 补全。
- **置信度**：高（脚本输出已实测比对）。
