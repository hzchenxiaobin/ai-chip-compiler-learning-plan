# 第 56 天技术校对报告

校对方法：在报告同名环境的临时副本（/tmp）中重新构建并运行 `mini-journey` 四个用例、`run_all.sh`、`test_journey.py` 与 `make_images.py`，四个用例输出与仓库冻结输出逐字节一致（22/22 测试通过、14/14 断言打印通过）；对存疑论断另行做了 4 组对照实验（删除 `EraseDeadConstantPattern`、关闭 region simplification、禁用签名细化、拆除 `?` 护栏）并核对了 MLIR 18.1.8 驱动源码与 `mlir-tblgen` 真实报错。以下结论均可复现。

## 【错误】

#### 1. 「驱动不会顺手擦除失去使用者的旧常量」与 MLIR 18 实际行为相反，错误 3 的现象不会发生
- **原文**："- **原因**：fold 的契约是"只返回值"——物化新常量、改使用者、擦除 add 都是驱动的活；但驱动**不会**顺手擦除"失去使用者的旧常量"。死代码消除是第 25 天就学过的独立职责。"
- **依据**：MLIR 18.1.8 `GreedyPatternRewriteDriver.cpp` 的 `processWorklist()` 对弹出工作列表的每个算子先做 "If the operation is trivially dead - remove it."（`isOpTriviallyDead`，见 `mlir/Interfaces/SideEffectInterfaces.h:365`）；`mini.constant` 带 `Pure`，失去全部使用者即被判定 trivially dead 并由驱动擦除，且 `notifyOperationRemoved` 会把使用计数下降的操作数定义者重新入列。实验：在临时副本里删掉 `runFoldStation` 的 `patterns.add<EraseDeadConstantPattern>`（进一步连 `enableRegionSimplification = false` 一起关掉）重新构建运行，阶段 3 输出与冻结输出逐字节相同（6 个 mini.*，两个 `dense<5.000000e-01>` 旧常量已消失）。因此错误 3 描述的"计数停在 8"在该环境不可能出现，`EraseDeadConstant` 是冗余模式（无害但非必要）；§4 站 3 "被挂进 Pattern 集的 `EraseDeadConstant` 收走"与错误 3 的"修复"同为此错误归因。
- **置信度**：高（驱动源码与两次删除实验相互印证；不排除极旧版本 MLIR 驱动无此行为，但本教程声明并实测的环境即 LLVM/MLIR 18.1.8）。

#### 2. run_all.sh 的「阶段 4 之后无动态维 ?x2」断言恒真，错误 5 宣称的修复与实际脚本不符
- **原文**："- **修复**：先用 `sed -n '/^===== 阶段 4/,$p'` 截取"阶段 4 之后"再做 grep；否定断言单独写 `check_no`（命令成功＝断言失败）。复盘启示：**断言的作用域要和断言的意图一致**——这和 Pass 测试里"检查最终 IR 而不是中间 IR"是同一个道理。"
- **依据**：run_all.sh:61 实际写的是 `check "阶段 4 之后无动态维 ?x2" bash -c "! tail_after_fuse '$OUT/journey-main.out' | grep -q '?x2'"`——没有用 `check_no`；且 `tail_after_fuse` 是脚本内的 shell 函数、未 `export -f`，`bash -c` 子进程解析不到它（command not found，127），管道退出码取 grep 的 1（空输入无匹配），`!` 取反后恒为 0，断言无条件 PASS。实测：向 journey-main.out 副本的阶段 4 段落之后追加一行含 `?x2` 的文本，该断言仍 PASS（对照组在同一 shell 直接 `sed | grep` 能检出）。因此"14/14 断言通过"里这一条不检验任何东西。另：同脚本对照 1 的 `check "终点仍含 ?x2（没人细化）" grep -q "?x2" "$OUT/journey-skip-infer.out"` 是全文 grep（阶段 0～2 本来就含 ?x2），终点即使无 ?x2 也会通过——恰是错误 5 强调的"作用域与意图不一致"。
- **置信度**：高（篡改文件复现恒真 + bash 语义核对；函数不跨 `bash -c` 传递是 POSIX/bash 的确定行为）。

#### 3. 「把 ?x2 顶替进融合产物，使用者类型对不上」经实验证伪：? 护栏的这一理由不成立
- **原文**："P1/P3 直接拒绝——把 `?x2` 顶替进融合产物，使用者类型对不上。"
- **依据**：P1/P3 创建融合算子时结果类型取 `m.getType()`（即 `?x2` 本身），`replaceAllUsesWith` 后使用者看到的仍是 `?x2`，类型一致；融合算子 Verifier 也允许结果维为 `?`（MiniRules.h 的结果维放行口径）。实验：临时副本把 `hasStaticTensorShape` 改为恒 true（拆除 ? 护栏）后以 `--skip-infer` 运行：P3 正常融成 `fused_matmul_bias_relu`（结果 `?x2`）、`[J4] verify 复查: 通过`、`accept=PASS`、终点 3 个算子——既无"类型对不上"，verify 也不"炸"。§6 错误 4 的现象（"融合产物类型带 ?，下游使用者类型对不上（或更糟：悄悄融了，verify 复查才炸）"）同样被证伪。护栏作为"信息不齐不重写"的设计选择本身可辩护（真正的代价是：融合结果的 `?` 不会被 `inferShapes` 细化，动态维被永久固化进 fused 算子），但教程给出的技术理由与事实相反。
- **置信度**：高（拆除护栏的对照实验直接复现"能融且 verify 通过"）。

#### 4. 「今天用『整张张量读写遍数』做的记账（融合前后 8→4）」：第 56 天代码与输出中不存在这笔记账
- **原文**："今天用"整张张量读写遍数"做的记账（融合前后 8→4）只是**玩具账本**，不是实测耗时"
- **依据**：grep 第 56 天全部代码与输出（mini-journey.cpp、run_all.sh、test_journey.py、mlir-mini/outputs、code/outputs）没有任何张量读写遍数记账逻辑或含"8→4"的记录；"整张张量读写遍数"的玩具记账与 8→4 这个数字出自第 55 天 mini-accept（day-055 README："代价账本（第 53 天口径的玩具记账：整张张量读写遍数）从 8 降到 4"）。图 3 第 4 张卡"融合省下中间张量的读写（记账 8→4）"同样把第 55 天的证据当本日证据展示。若本意是"本复盘沿用第 53/55 天口径的记账"，现表述会让读者在今天的工具里找不到这笔账。
- **置信度**：高（当日产物 grep 无果且出处可精确追溯；唯一不确定点是"今天"一词是否被作者有意用来指代整个第二阶段收官）。

#### 5. 「乘积 use 表为空」：P3/P1 的实际前置检查是"乘积恰好有一个使用者（即被匹配的 add）"
- **原文**："先查（bias 三分类 Same、全 f32、乘积类型静态、乘积 use 表为空、`%s` 唯一使用者是 relu）"
- **依据**：mini-journey.cpp 中 P1/P3 的检查是 `unsigned numUses = std::distance(m.use_begin(), m.use_end()); if (numUses != 1) return failure();`——乘积必须恰好被本 add 使用一次（use 表大小为 1 而非 0；被匹配的 add 本身就在 use 表里，"为空"在逻辑上不可能成立），P1 的拒绝日志"匹配 Add：乘积使用者 N -> 拒绝（Day 52 规则）"与对照实验中 shared 用例的拒绝行为均印证 numUses==1 语义。若想表达"除 add 外无其他使用者"，应写明。
- **置信度**：高（代码直读与日志印证；宽容解读"无其他使用者"与字面陈述"为空"是两回事）。

#### 6. 图 4 复跑命令路径缺 week-008/，且「make_images.py 可确定性重生成」对 04-results.svg 不成立
- **原文**："- [ ] 我保存了今天的全部产出：`mini-journey` 工具、三个对照输入、`run_all.sh`、`test_journey.py`、`outputs/` 全部记录和 4 张插图（`make_images.py` 可确定性重生成）"
- **依据**：冻结的 images/04-results.svg 中复跑命令为 `cd tutorials/day-056/code/mlir-mini && ninja -C build && bash run_all.sh` 与 `cd tutorials/day-056/code && python3 test_journey.py`，均缺 `week-008/` 层级（真实路径是 tutorials/week-008/day-056/...，照图执行会报目录不存在）。在临时目录重跑 make_images.py 后 diff：01/02/03 三张逐字节一致，唯独 04-results.svg 与仓库冻结版不同（生成器现在输出含 week-008/ 的正确路径）——冻结图与生成器不同步，"可确定性重生成"对该文件不成立。
- **置信度**：高（diff 实测；不排除作者事后改了生成器而未重生成图片，但这正是需要修正的不一致）。

## 【存疑】

#### 1. 「第 74 天的 CostModel 才建账」的跨天指认偏松
- **原文**："第 74 天的 CostModel 才建账。"
- **依据**：按学习计划与 day-074 教程，第 74 天主题是「合法性与收益性分离」（`should_fuse` 决策门，确实在此组装净收益/资源账，但公式与资源账来自第 72/73 天）；名称就叫 "Cost Model" 的是第 76 天（day-074 README 原文："后三天（D75 负例库、D76 Cost Model）"）。"建账"的说法大体成立，但把"CostModel"归到第 74 天不够精确；图 1/图 3 也沿用同一指认。
- **置信度**：中（已核对计划与 day-074 教程原文；属指认口径问题而非结论错误，不排除计划口径本身允许这种简称）。

## 【建议】

#### 1. 图 3 卡③/卡④ 混入第 55 天与未来的证据，与图注「各配今天的真实负例和日志原文」不符
- **原文**："右侧四张卡各配今天的真实负例和日志原文；"
- **依据**：卡③"叠加验证：融合前后 evaluate 对账（Python 层 R3）"——第 56 天没有 evaluate/R3（test_journey.py 为 T1～T5 文本断言，无数值对账；R3/evaluate 属第 55 天 mini-accept）；卡③"闸门：元素类型非全 f32 -> 拒绝"——第 56 天四个用例的日志均无此行（bad 在站 1 短路，Pattern 侧类型闸门日志只在第 55 天出现过）；卡④"记账 8→4"见【错误】第 4 条。卡①② 的日志确实能在 journey-shared.err／journey-skip-infer.err 中逐字找到。
- **置信度**：高（全部日志 grep 核对）。

#### 2. 图 2 站 4 口诀与正文不一致
- **原文**："中排四张站卡是本文 §3.1 职责表的图形版，每张卡右下角是口诀。"
- **依据**：SVG 中站 4 卡口诀为"改结构，语义不变"，而 §3.1 职责表与 §8 验收清单均为"改结构，先查后改"；图注声称站卡是职责表的图形版，其余三站口诀一致、唯独站 4 两处口径不同，建议统一。
- **置信度**：高（SVG 文本提取比对）。

#### 3. §5.3 引用的 stderr「真实记录」首行被缩短且未标注省略
- **原文**："[J2] matmul 结果 %3: ? 维细化为 tensor<2x2xf32>"
- **依据**：journey-main.err 中的实际行是 `[J2] matmul 结果 %3 = "mini.matmul"(%arg0, %arg1) : (tensor<2x3xf32>, tensor<3x2xf32>) -> tensor<2x2xf32>: ? 维细化为 tensor<2x2xf32>`；该段标注"（真实记录，`outputs/journey-main.err`）"，读者按引文 grep 将找不到。签名那行用了"..."标注省略，首行（以及 §4 决策日志从 5 行节选 3 行）建议同样标注节选。
- **置信度**：高（逐字节比对）。

#### 4. §5.2 代码摘录注释的交叉引用指向错误的小节
- **原文**："// 类型护栏：动态维不折（见 §6 错误 2）"
- **依据**：§6 错误 2 讲"站 2 之后 verify 复查失败——签名没跟着细化"，与 fold 的动态维护栏无直接关系；源文件 MiniDialect.cpp 同位置注释为"（第 49 天第 6 节错误 1 的教训）"，该护栏真正对应的话题更接近 §6 错误 4（? 的全局判断 vs 局部判断）或第 49 天的原始记录。
- **置信度**：高（小节标题比对）。

#### 5. 「匹配成立（对照 2、3 里都成立或可成立）」对对照 3 不适用
- **原文**："**匹配成立（对照 2、3 里都成立或可成立）≠ 可以动手**"
- **依据**：journey_bad.mlir 只有一个 matmul＋return，图中不存在 add/relu，任何融合 Pattern 都无可匹配结构（它演示的是验证站短路，不是"匹配成立但被边界拒绝"）。对照 2 的"匹配成立"属实；把对照 3 并列进来容易让读者误以为 bad 图里存在被拒的融合候选。
- **置信度**：高（输入文件直读）。

#### 6. 冻结日志中的「%s」是未替换的占位符，作为证据引用时易误读
- **原文**："[P3] 匹配 MatMul + Add -> fused_matmul_bias（%s 还有别的使用者时不吸收 Relu）"
- **依据**：该行出自 mini-journey.cpp 的 `llvm::errs() << "  [P3] 匹配 MatMul + Add -> fused_matmul_bias" "%s 还有别的使用者时不吸收 Relu）"`——"%s"是 printf 风格残留，`raw_ostream <<` 不会替换，真实日志里就是字面 %s（README 引用忠实于冻结输出，本身没有转述错误）。建议后续修正源码日志或在教程注明，避免读者寻找"%s 指谁"。
- **置信度**：高（源码直读）。
