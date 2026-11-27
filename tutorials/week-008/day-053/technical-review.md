# 第 53 天技术校对报告

校对范围：README.md 全文、`code/` 全部源码与输入、`outputs/` 全部真实运行记录、`images/` 全部 4 张 SVG，并交叉核对了第 40/50/51/52/54 天教程与总计划。核实手段：本机重跑 `mini_fuse_bias.py`、`test_matmul_bias.py`（10/10 通过）、`mini-fuse-bias` 全部 11 组实验（stdout/stderr/退出码与 `outputs/` 逐字节一致）、`mlir-opt --convert-elementwise-to-linalg --linalg-fuse-elementwise-ops`（与 `linalg_fused.out` 一致）、在临时目录从零 cmake+ninja 重建（成功，约 6 秒）、numpy 广播语义实测。环境（aarch64 / g++ 9.4.0 / LLVM 18.1.8 / Python 3.11.4 / numpy 1.26.4）与 README 声明一致。

## 【错误】

#### 1. 「照抄 add 的第一个操作数类型」不会得到 tensor<2x3xf32>——类型来源张冠李戴

- **原文**：“- 照抄 `add` 的第一个操作数类型：得到 `tensor<2x3xf32>`。今天因为 `Same` 规则碰巧不会发生，但第 52 天的 Python 版 `create_op` 恰好就是这么偷懒的（`result_type = inputs[0].type`）——matmul 一来就露馅，所以本日把它改成显式传类型；”
- **依据**：本日所有输入图（`inputs/*.mlir`）里 `mini.add` 的两个操作数都是 `%m` 与 `%bias`（`bias_on_left.mlir` 是 `%bias` 与 `%m`），类型均为 `tensor<2x2xf32>`；`%a`（`tensor<2x3xf32>`，matmul 的 lhs）从来不是 add 的操作数。所以照抄「add 的第一个操作数」的类型得到的是 `tensor<2x2xf32>`——恰好正确。得到 `tensor<2x3xf32>` 的是**融合算子的第一个操作数 `%a`**（即第 52 天 `inputs[0].type` 里的 `inputs[0]`：本日融合算子操作数是 `[A, B, bias]`，见 `mini_fuse_bias.py` 的 `rw.create(fused_name, [mm.inputs[0], mm.inputs[1], bias], ...)`）。README 自己在 §1（“照抄「第一个操作数」”指 lhs %a）、§5.1（“`A` 是 `2x3` 而结果是 `2x2`”）和 §6 错误 1（“融合算子的结果类型照抄「第一个操作数」”）用的都是融合算子口径，唯独本句写成了「add 的第一个操作数」。此外本句后半「今天因为 `Same` 规则碰巧不会发生」与前半「得到 `tensor<2x3xf32>`」自相矛盾：若真的照抄 add 首操作数（%m），今天正是因为 Same 规则所有类型同为 2x2、恰好不会出错；会得到 2x3 的是融合算子首操作数那条路。应改为「照抄融合算子的第一个操作数（A）的类型」。
- **置信度**：高（所有输入图与代码均已逐个核对；唯一不确定点是作者原意，但从 §1/§5.1/§6 的平行表述看，本句属笔误性错位，不是另一种自洽口径）。

#### 2. Mismatch 行的示例「[1,2] 对 [2,2] 连广播都对不上、语义上就没定义」与 NumPy 广播语义矛盾

- **原文**：“| **Mismatch** | 连广播都对不上（如 `[1,2]` 对 `[2,2]`） | 拒绝，语义上就没定义 |”
- **依据**：本机 numpy 1.26.4 实测 `[[12,-13],[-27,28]] + [[10,-10]]`（即 `[1,2]` 对 `[2,2]`，前导 1 广播）合法，结果 `[[22,-23],[-17,18]]`，与 `[N]` 向量按行广播的结果完全相同。教程在 §3.1 自己用 numpy 作为语义参照（“numpy 会按行广播……求值器「能算」”），却把 `[1,2]` 说成「连广播都对不上」「语义上就没定义」——在 NumPy 广播规则下这句话是错的，语义有定义；初学者拿 numpy 一试就会发现矛盾。真正「连广播都对不上」的是 `[3,2]` 对 `[2,2]`（实验 I 的实际用例 `bad_bias_shape.mlir`，numpy 报 `ValueError: operands could not be broadcast together`）。本日 Python 测试 9 也用了 `tensor<1x2xf32>` 当 Mismatch 样例，`code/mini_fuse_bias.py` 的 FEED 注释还写着“1x2（错秩）”——秩其实相同（都是 2），错的是形状且该形状可广播。正确写法应是：`[1,2]` 在 NumPy 广播下同样对得上，只是第 53 天的三分类只认 `[N]` 行广播这一种，其余一律按 Mismatch 拒绝；或直接换用 `[3,2]` 这类真不可广播的例子。
- **置信度**：高（numpy 实测 + 实验输入文件双重核实）。

#### 3. 「沿用第 40 天的口径」不成立：第 53 天的三分类与第 40/50 天的分类器对同一输入给出相反类别

- **原文**：“一句通俗的解释：bias 是**浇在成品上的酱料**。它要么装成和成品同样大小的一整盒（每一口都有一份自己的酱，`[M,N]` 同形），要么是一小包、每一行浇同一份（`[N]` 按行广播）。对应到技术上是：**`mini.add` 的两个操作数里，不是乘积的那一个就是 bias；bias 的形状相对乘积形状做三分类**——沿用第 40 天的口径，今天写进共享头文件 `MiniRules.h`：”
- **依据**：第 40 天的 `classifyShapePair`（`week-006/day-040/code/mini/lib/ShapeRelation.h`，注释明确“在 NumPy 广播规则下相容（某维为 1、或秩不同缺位补 1 后相等）”）把 `[1,2]` 对 `[2,2]` 判为 **BroadcastOnly**——`x==1 → sawBroadcastDim → BroadcastOnly`；day-040 的测试 `add_broadcast_bias.mlir`（`2x2 + 1x2` bias“想广播”）正是此例，报“需要广播、Day 60 放行”。第 50 天 `FusedMatmulBiasReluVerifier.cpp` 同样复用这个 NumPy 式分类器。而第 53 天 `MiniRules.h` 的 `classifyBias` 只认「bias 是 `[N]` 且等于乘积末维」为 BroadcastOnly，`[1,2]` 对 `[2,2]` 落入 **Mismatch**（永久拒绝，SVG 2 还写了“语义上就没定义，谁来都不行”）。两个分类器对同一输入给出 BroadcastOnly（合法语义、第 60 天放行）与 Mismatch（永久非法）两种相反结论，因此「沿用第 40 天的口径」以及代码注释/SVG 2 的「口径与第 40/50 天完全一致」「逐字相同」都不成立：第 53 天实际把三分类从 NumPy 式收窄成了「只认 `[N]` 行广播」。本日 11 组 MLIR 实验没踩到这个分歧点（H 用 `[2]`、I 用 `[3,2]`，两个分类器结论一致），所以真实输出全部有效，但文字层面的口径声明与第 40/50 天矛盾，应显式说明收窄（例如“BroadcastOnly 今天只收 `[N]` 行广播一种，比第 40 天的 NumPy 式广播收窄”）。
- **置信度**：高（第 40/50/53 天三个分类器的源码均已逐行核对）。若把「口径」只理解为 Same/BroadcastOnly/Mismatch 三分框架加“第 60 天放行 BroadcastOnly”的政策，可以辩护为“沿用框架”；但分类行为确有分歧，初学者按第 40 天的规则推 `2x2 + 1x2` 会得到与第 53 天相反的预期。

## 【存疑】

- 无。

## 【建议】

#### 4. `inputs/*.mlir` 文件头注释里的实验编号与 README 差一位

- **原文**：“**实验 F——`%s` 被 relu 和 return 共用**（`inputs/shared_result.mlir`）：”
- **依据**：README 的实验字母表是 A~K（F=shared_result、G=both_matmul、H~K=四个负例），四张 SVG 和 `mini_fuse_bias.py`（“见教程 §5.4 实验 H”）都遵循它；但输入文件自己的头注释停在旧编号：`shared_result.mlir` 写“实验 E”、`both_matmul.mlir` 写“实验 F”、`rank1_bias/bad_bias_shape/fused_bad_result_type/fused_rank1_bias` 分别写 G/H/I/J（README 叫 H/I/J/K），`matmul_bias_relu_linalg.mlir` 还写着“跑法见教程 §5.4”（上游对照实际在 §5.5）。不影响运行与结论，但初学者对着文件找“实验 F”会看到文件自称“实验 E”，建议统一（本报告不改动任何文件）。
- **置信度**：高（全部 11 个输入文件的注释与 README 逐一比对过）。

#### 5. 图 1 图内文字「第 3 个 Pattern 进驻」与图注「第 2 个 Pattern 进驻」计数不一致

- **原文**：“**图 1**：上排是目标链与两个融合产物——没有 Relu 时融成 `mini.fused_matmul_bias`（今天新定义），Relu 被吸收时融成 `mini.fused_matmul_bias_relu`（第 50 天定义）；中排是 `mini-opt` 的优化管道，今天动的是「融合 Pass」这一格——第 51/52 天的 `add+relu` Pattern 之后，第 2 个 Pattern 进驻；下排是第 8 周路线，昨天的多使用者规则原样适用。底部三个色块就是 §1 的三个新问题。”
- **依据**：`images/01-overview.svg` 中对应文字是「② 今天动的是「融合 Pass」：第 3 个 Pattern 进驻」。两种数法各自成立：按“不同融合能力”数（第 51 天 `FuseAddReluPattern` 与第 52 天 `FuseAddReluMultiPattern` 是同一个 add+relu 融合及其策略升级，今天 matmul+bias 才是第 2 个 Pattern），图注“第 2 个”对；按“不同 Pattern 结构体/工具”数（51/52/53 三天三个 struct、三个工具），图内“第 3 个”也对。问题在同一天图文各说一个数，读者无所适从；建议统一口径（并注意第 54 天图 1 也说“第一次挤进多个互相竞争的 Pattern”，与“第 2 个/第 3 个”的叙事衔接最好一并理顺）。
- **置信度**：高（不一致本身确定；哪个数字“正确”取决于计数口径，属于表述一致性问题而非对错问题）。

#### 6. 「N 处上岗」的计数前后不一：SVG 写“两处”、README 写“三处”、枚举却有 4 个调用点

- **原文**：“`MiniDialect.cpp` 里的 `AddOp::verify()` / `FusedMatmulBiasOp::verify()` / `FusedMatmulBiasReluOp::verify()` 全部从这里取规则；`mini-fuse-bias.cpp` 的 Pattern 也从这里取——**同一条规则，三处上岗**。Pattern 的关键段（§4 图 3 的 (1)~(6) 步）：”
- **依据**：本行列举了 4 个取规则的调用点（AddOp::verify、FusedMatmulBiasOp::verify、FusedMatmulBiasReluOp::verify、Pattern），却说“三处上岗”；§4 图 2 图注按“add Verifier / Pattern classifyBias / 融合算子 Verifier”数出三道闸门（把两个融合算子的 Verifier 合并成一道）；而 `images/02-shape-types.svg` 同一位置写的是「同一条规则，两处上岗」却画出三道闸门。三种数法（4 个调用点 / 3 道闸门 / 2 端 = Verifier 端＋Pattern 端）都能自圆，但图、图注、正文各不相同。建议统一成一种（“三道闸门”最贴合图 2 的画法，只需说明两个融合算子共用同一道）。
- **置信度**：高（README 两处与 SVG 文字均已核对）。

#### 7. 目录树里「11 个 .mlir（7 正例 + 4 负例 + 上游对照）」算不平

- **原文**：“        ├── inputs/              ← 11 个 .mlir（7 正例 + 4 负例 + 上游对照）”
- **依据**：`inputs/` 实际 11 个文件 = 6 个正例实验文件 + 4 个负例文件 + 1 个 linalg 对照；7 个正例**实验**共用 6 个**文件**（`multi_user_product.mlir` 同时服务实验 D 与 E）。按括号里的分项相加是 7+4+1=12，与“11 个”对不上。§2 的“11 组真实运行记录（7 正例＋4 负例）和 1 张上游 linalg 对照”按实验数数是对的，此处把“文件数 11”与“实验数 7+4”混在一个括号里，建议改成“10 个 mini 输入（实验 D/E 共用 multi_user_product.mlir）+ 1 个 linalg 对照”一类写法。
- **置信度**：高（文件与实验对应关系逐一清点过）。
