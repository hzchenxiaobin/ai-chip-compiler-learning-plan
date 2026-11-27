# 第 54 天技术校对报告

审阅对象：`tutorials/week-008/day-054/`（README.md、`code/mini_fuse_pipeline.py`、`code/test_three_op_fusion.py`、`code/mlir-mini/` 全部源码与 18 组真实输出、`images/` 下 4 张 SVG）。
审阅环境与教程自述一致：aarch64 Linux、g++ 9.4.0、Ubuntu LLVM 18.1.8、Python 3.11 + numpy 1.26。已实际执行：Python 两脚本（12/12 通过）；`mini-fuse3` 17 组有界实验逐条重跑并与冻结输出 diff（全部一致）；`--set=oscillate --max-rewrites=6` 重跑一致（rc=2）；临时目录全新 CMake 构建成功；对 `GreedyDriver` 插桩追踪工作表弹出顺序；MLIR 18 头文件与上游 18.1.8 源码（PatternMatch.cpp、PatternApplicator.cpp、GreedyPatternRewriteDriver.cpp）逐条核对。

## 【错误】

#### 1. §3.3 四步对账的第 3 步：`fused_matmul_bias` 的弹出时机与结局与驱动真实行为不符（第 3、4 步顺序颠倒）
- **原文**：“3. 弹出 `fused_matmul_bias`：P1/P3 都锚 `add`，此 root 没它的份；P2 锚 `relu` 也没份——无匹配；”
- **依据**：对当天 `mini_fuse_pipeline.py` 的 `GreedyDriver`（集合 [P1,P2]，bottom-up 从表尾弹）插桩实测，真实弹出序列是：①弹 `relu`（P2 不匹配）→ ②弹 `add`（P1 命中，入队 `fused_matmul_bias` 和 `relu`，此时工作表为 `[matmul, fused_matmul_bias, relu]`）→ ③**下一次弹出的是队尾的 `relu`（第二次访问，P2 立即命中）**，随后才弹出新建的 `fused_matmul_bias_relu`（无 root 匹配）；而 `fused_matmul_bias` 在第③步 P2 命中时已被 `rw.erase(fm)` 擦除，等到它弹出时是被「已擦除→跳过」分支直接跳过的，**根本不会发生「无匹配」的访问**；`matmul` 同样是擦除后跳过。也就是说第 3 步描述的事件（先于 relu 第二次访问弹出 fused_matmul_bias 并无匹配）不存在，第 3、4 步顺序颠倒。这与本节自己的前提矛盾：「从尾部弹」＋下一段「P1 的改写把 `relu` 重新压回队尾」意味着下一个弹出的必然是 `relu`。MLIR 18 侧同理：`replaceAllUsesWith` → `modifyOpInPlace(使用者)` → `notifyOperationModified` → `addToWorklist`，工作表同样从尾部弹、已擦除算子弹出时跳过，`outputs/two_stage_main.err` 的三行日志与本轨迹一致。附带两处小口径问题：第 2 步「`add`/`matmul` 的结果被替换」不准确——P1 只替换 add 的结果 `%s`，matmul 的结果 `%m` 是随算子一起被擦除的；第 3 步写「P1/P3 都锚 `add`」，但两阶段集合里只有 P1/P2，并没有 P3。
- **置信度**：高（在当天代码上插桩实测；MLIR 侧行为由 18.1.8 源码与冻结输出双重确认）。

#### 2. §1 把 `Relu(Relu(x))` 说成「前天」的 Pattern，归属天数错误
- **原文**：“把第 51 天的 `Add+Relu`、昨天的 `MatMul+Bias(+Relu)`、可能还有前天的 `Relu(Relu(x))` 全部塞进**同一个** `RewritePatternSet`”
- **依据**：`Relu(Relu(x)) → Relu(x)` 是第 45 天的主角（`tutorials/week-007/day-045/README.md` 标题即「第一个 RewritePattern——让 mini-opt 自动消掉 Relu(Relu(x))」；第 51 天 README 也写「第 45 天的 `Relu(Relu(x)) → Relu(x)`」）。相对第 54 天，「前天」是第 52 天，而第 52 天的主题是「融合的多使用者限制」，与 Relu(Relu) 无关。应改为「第 45 天的」。
- **置信度**：高（第 45/51/52 天教程标题与正文可直接核对）。

#### 3. §3.2「把 benefit 调到 65535」撞上 `PatternBenefit` 的哨兵值，该值不可设置
- **原文**：“P51 的 root 是 `mini.relu`，P3 的 benefit 就是调到 65535，也管不到「P51 和 P3 谁先被访问」。”
- **依据**：MLIR 18 `mlir/IR/PatternMatch.h` 中 `PatternBenefit` 用 `unsigned short` 表示且 `ImpossibleToMatchSentinel = 65535`；上游 18.1.8 `PatternMatch.cpp` 的构造函数 `PatternBenefit::PatternBenefit(unsigned benefit)` 带断言 `benefit != ImpossibleToMatchSentinel`；`PatternApplicator::applyCostModel` 会把 `isImpossibleToMatch()` 的 Pattern 直接丢弃（debug 下打印 "Ignoring pattern ... because it is impossible to match"）。因此 benefit 的合法取值是 0~65534，把 P3 的 benefit 设成 65535 在 debug 构建下触发断言、在 release 构建下等价于让 P3 永不匹配——句子要表达的「跨 root 无比较」结论本身正确，但举例值恰好是不可用的边界值；同节前文的「0~65535 的无量纲整数」同样宜写成 0~65534（上游头文件自述为 "ranges from 0 ... to 65K"，65K 即保留给哨兵的 65535）。
- **置信度**：高（头文件与上游源码核实；修辞意图正确，仅取值不成立）。

#### 4. §6 错误 2 的原因解释：「注册顺序只影响工作表的初始排列」不成立
- **原文**：“注册顺序只影响工作表的初始排列，不影响「谁在改写后被重新访问」。”
- **依据**：当天 Python 驱动的播种是 `worklist = list(self.graph.ops)`，按**程序序**入队；MLIR 18 的驱动按 region 的 postorder（bottom-up）或 preorder 逆序（top-down）播种（`GreedyPatternRewriteDriver.cpp` 的 `RegionPatternRewriteDriver::simplify()`）。两者的工作表初始排列都与 Pattern 注册顺序**完全无关**。插入序真正影响的是另一处：同 root 且同 benefit 时的尝试顺序（`PatternApplicator::applyCostModel` 的 `std::stable_sort` 保序，即 §5.7 的实验）。按原文照做（想通过改注册序改变工作表初始排列）什么也观察不到。应改成「注册顺序只影响同 root、同 benefit 时 root 表内的尝试顺序」。
- **置信度**：高（当天代码与 MLIR 18 源码双重核实；句子前半句机制描述错误，后半句「不影响谁被重新访问」正确）。

#### 5. §6 错误 4 的定位指引：「总数≈改写上限」与当天实测数据矛盾
- **原文**：“两种 Pattern 的行数交替上升、总数≈改写上限，就是互逆拉锯；”
- **依据**：`--max-rewrites=N` 限制的是**单轮（iteration）内**的改写数（MLIR 18 `GreedyRewriteConfig::maxNumRewrites` 注释 "maximum number of rewrites within an iteration"），外层默认最多迭代 10 轮（`maxIterations = 10`），因此退出码为 rc=2 时日志里的成功改写总数约为 N×10。当天 §5.6 自测 `--max-rewrites=6` 时成功改写恰为 60 次（P1 1 次＋P2 30 次＋Unfuse 29 次，`oscillate_guarded.err` 逐行可数），6×10=60，与「总数≈改写上限」相差 10 倍。诊断特征应写成「总数≈改写上限×迭代上限（默认 10）」，否则读者按此定位会误判。
- **置信度**：高（MLIR 18 头文件注释＋当天冻结输出双重核实；影响的是排查指引，不影响正文结论）。

## 【存疑】

- 无。

## 【建议】

#### 1. §5.5 的「真实结果」IR 引文是示意改写，不是逐字输出
- **原文**：“%s' = mini.fused_matmul_bias %arg0, %arg1, %arg2 : tensor<2x2xf32>”
- **依据**：`outputs/two_stage_shared.out` 的真实输出是 `%0 = mini.fused_matmul_bias %arg0, %arg1, %arg2 : tensor<2x3xf32>, tensor<3x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>`（结果名是 `%0`，操作数带完整类型标注）；引文用了 Python 版的 `%s'`/`%r` 命名且只保留一个类型标注，不是合法 MLIR 语法，也不是 Python 版的逐字输出（Python 版打印 `%s' = mini.fused_matmul_bias %a, %b, %bias : tensor<2x2xf32>`）。同小节 P2 拒绝日志的引文「`[P2] 融合结果 %s' 有 2 个使用者 -> 不能吸收 Relu`」与真实日志「`[P2] 融合结果有 2 个使用者 -> 不能吸收 Relu（Day 53 场景 E 的规则）`」也有出入（多了 `%s'`、少了括注）。结构与语义都对，但标注为「真实结果」的引文建议改为逐字输出或明确标注「示意」。
- **置信度**：高（两份冻结输出可直接比对）。

#### 2. §5.3 B 组表格把「遍数」「数值」列在 run_all.sh 真实执行结果名下，实际来源是 Python 侧模型
- **原文**：“| 遍历 | 决策日志（`outputs/steal_*.err` 原文） | 最终形态 | 遍数 |”
- **依据**：`mini-fuse3` 只打印 IR 与决策日志，不算代价账本也不做数值求值（输入图是函数参数，无数据）；`run_all.sh`/`test-summary.txt` 里没有「遍数 6/4」和「数值 [[22,0],[0,8]]」。这两个数字来自 Python 版的玩具代价模型 `op_cost`（matmul 3 遍＋fused_add_relu 3 遍=6；fused_matmul_bias_relu 4 遍）和数值断言 `test_steal_order_dependent_fixpoint`（数值本身正确且已验证）。图 3 的「两次运行……数值都是 [[22,0],[0,8]]」同理。建议在表格/图注注明遍数与数值来自 Python 侧口径，避免读者在 MLIR 输出里找这两个数。
- **置信度**：高（两套产物均已通读；数字本身核对无误）。

#### 3. §5.1 目录树注释与实际代码位置有出入
- **原文**：“├── MiniRules.h            #   共享规则：bias 三分类、找乘积对”
- **依据**：`classifyBias`（bias 三分类）确实在 `MiniRules.h`，但「找乘积对」（`findMatmulPair`）在 `mini-fuse3.cpp`（Python 侧是 `_find_matmul_pair`），`MiniRules.h` 里没有；同时上一行「`MiniDialect.{h,cpp}`……（含 classifyBias 三分类，Day 53 口径）」也不准确——`MiniDialect.cpp` 只是 `classifyBias` 的调用方，定义在 `MiniRules.h`。两行注释建议对调/修正指向，不影响功能。
- **置信度**：高（源码文件可直接核对）。

#### 4. §3.2 表格「Unfuse 的 benefit=3 压过一切」措辞与 benefit 语义不符
- **原文**：“Unfuse 的 benefit=3 压过一切，它带来的只有不收敛（§5.6）”
- **依据**：benefit 只在同一 root 的列表内排序（本报告核对 `PatternApplicator::applyCostModel`：按 root 分组、`std::stable_sort` 降序）。Unfuse 独占 root=`mini.fused_matmul_bias_relu`，它与 P1/P2/P3 从不发生比较，谈不上「压过」；`mini-fuse3.cpp` 里 `--set=oscillate` 的注释自己也写明「benefit 3 的 Unfuse 在同 root 上没有对手——……benefit 根本管不到这种跨 root 打架」。数值上 3 确实是全集合最高，建议改成「benefit 3 是全集合最高，但也只在自己的 root 里独占——它带来的只有不收敛」。
- **置信度**：高（语义核对自 MLIR 源码；当天代码注释佐证）。

#### 5. 第 18 组实验的 .err 文件不在版本控制内，与验收清单表述有出入
- **原文**：“我保存了本日全部真实运行记录（`outputs/` 下 18 组 .out/.err 与 test-summary.txt）”
- **依据**：`git ls-files` 显示 `outputs/oscillate_hang.out` 已跟踪，但 410MB 的 `oscillate_hang.err` 被根目录 `.gitignore` 第 12 行显式忽略，新克隆的仓库里只有 17 组 .out/.err 加 `oscillate_hang.out`。本地工作区确实 18 组齐全，且 `run_all.sh` 可复现（10 秒 timeout），但建议在 README 或仓库说明中注明该文件不入库、需复跑生成，避免读者克隆后对不上「18 组 .out/.err」的说法。
- **置信度**：高（git 状态与 .gitignore 可直接核对）。
