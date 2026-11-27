# 第 52 天技术校对报告

审阅范围：`tutorials/week-008/day-052/README.md`、`code/`（Python 版、MLIR 版及全部输入）、`images/` 下 4 张 SVG。核对方式：在本机重跑 `mini_fuse_multi.py`、`test_multi_user.py`（6/6 通过）、`mini-fuse-multi` 全部 5 组实验（A～E 输出与 README 逐字一致，`exit=0`），在临时目录全新构建 `mlir-mini`，重跑 §5.4 的 `mlir-opt --linalg-fuse-elementwise-ops` 多使用者与单使用者对照实验，并比对上游 LLVM 18.1.8 源码与安装头文件（`PatternMatch.h`）。环境核对无误：aarch64、g++ 9.4.0、Ubuntu LLVM 18.1.8、Python 3.11.4、numpy 1.26.4。未发现数值、IR 输出或 API 用法层面的造假；以下为逐条意见。

## 【错误】

#### 1. 前置准备中的章节交叉引用指向错误的小节
- **原文**：“第 51 天的 `FuseAddReluPattern`（本文 §5.4 复用同款 ODS／Dialect 壳，可独立构建运行）”
- **依据**：本日 §5.4 是「生产级对照：上游 linalg 遇到多使用者怎么办？」，内容是 `mlir-opt --linalg-fuse-elementwise-ops` 的对照实验，不含任何 ODS／Dialect 壳；「同款 ODS／Dialect 壳、原样复制、可独立构建」指的是 §5.2「正餐（30 分钟）：真实 MLIR 里的 `mini-fuse-multi`」——该节第一句即「Dialect 壳和 ODS 与第 51 天完全相同（同三个算子，`MiniOps.td`、`MiniDialect.h/.cpp` 原样复制）」。我已逐字节 diff day-051 与 day-052 的 `MiniOps.td`、`MiniDialect.h`、`MiniDialect.cpp`，三者确实完全一致，引用目标应为 §5.2。读者按 §5.4 跳转只能看到 linalg 对照，会找不到承诺的「可独立构建」材料。
- **置信度**：高（两节标题与内容可直接核对，diff 结果确凿）。

## 【存疑】

#### 1. 「生产级对照」与「上游佐证」的分量偏重：该 pass 在上游自述为仅供测试、拟废弃
- **原文**：“### 5.4 生产级对照：上游 linalg 遇到多使用者怎么办？”
- **依据**：行为描述核实无误——我在本机 MLIR 18.1.8 上重跑同一命令，多使用者输入确实保持 3 个 `linalg.generic` 不融合，单使用者对照确实融成 1 个（`addf`＋`maximumf` 同循环体）；其拒绝机制在 LLVM release/18.x 源码 `mlir/lib/Dialect/Linalg/Transforms/ElementwiseOpFusion.cpp` 中可查：pass 的默认控制函数为 `ControlFusionFn defaultControlFn = [](OpOperand *fusedOperand) { Operation *producer = fusedOperand->get().getDefiningOp(); return producer && producer->hasOneUse(); };`。但同一文件中该 pass 的定义注释写着「Pass that fuses generic ops on tensors. Used only for testing. TODO(ravishankarm): This pass is to be deprecated. The efficacy of the patterns added here heavily depends on the cost function used. Having an opinionated pass of this form is not recommended.」（https://github.com/llvm/llvm-project/blob/release/18.x/mlir/lib/Dialect/Linalg/Transforms/ElementwiseOpFusion.cpp）。也就是说，`--linalg-fuse-elementwise-ops` 是上游自述「仅供测试、拟废弃」的 pass，「拒绝多使用者」只是这个测试 pass 的默认控制函数，并不代表 linalg 生产管线的成本模型决策。把该节称为「生产级对照」、把结论称为「策略 A 的上游佐证」，分量偏重；正文结论句本身（「上游 MLIR 18 的 `--linalg-fuse-elementwise-ops` 选择了……保守路线：拒绝」）限定在 pass 名之内，是准确的。建议节标题改称「上游对照」或补一句该 pass 在上游的定位。
- **置信度**：高（行为、源码、pass 注释均核实）；「生产级」一词是否必须改属判断问题，故列存疑。

#### 2. 「改接中间值的使用者永远是语义错误」中的「永远」在逻辑上过强
- **原文**：“3. **改接中间值的使用者永远是语义错误**：融合结果 = `relu(中间值)` ≠ 中间值；`verify` 查不出来，必须有独立的数值验证；”
- **依据**：在本日反例（另一个使用者是第二个 `mini.add`）中改接确实变错，已实测 `[[11.5,10],[12,10]] ≠ [[11.5,8.5],[12,8]]`。但作为普遍命题「永远」存在反例：若 `%t` 的另一个使用者本身也是 relu，由于 relu 幂等（`relu(relu(x)) = relu(x)`），改接后该使用者计算的值不变，语义恰好保住。因此严格地说「改接后其他使用者拿到 relu(a+b) 而非 a+b」成立，但「一定变错」不成立。作为工程规则「一律禁止改接」完全正确（不能依赖幂等巧合）；鉴于本条位于「用文字固定下来，供后面几天引用」的合法性说明中，措辞可改为「一律视为语义错误并禁止」以免被当成逻辑必然。本日正文其余部分（§6 错误 1 的具体分析）均限定在本日反例上，无此问题。
- **置信度**：中（幂等反例在数学上成立，但与本日示例无关；作为规则书写的「永远」是否需要修改属编辑判断）。

## 【建议】

#### 1. 「出路只有 A 和 B」未提真实编译器还有第三条路：融合算子同时产出中间值（多结果融合）
- **原文**：“- **修复**：删除这条路径。多使用者的出路只有 A（拒绝）和 B（保留生产者）；第 55 天把这类负例固化为回归测试。”
- **依据**：对当前 mini Dialect（`fused_add_relu` 只有一个结果）而言，A/B 确实是仅有的两条正确出路，本日表述在其范围内成立。但真实编译器存在第三种做法：上游 linalg 的融合机制（同文件 `ElementwiseOpFusion.cpp`）里 `getPreservedProducerResults` 会把「被消费者之外的使用者引用」的生产者结果保留为融合算子的额外输出，即一个融合算子同时产出 `%t` 和 `relu(%t)`，既不拒绝也不复制计算。§9 总结「正确的出路只有拒绝……或保留生产者」也用了同款绝对表述。建议在 §5.5 或 §9 补一句脚注：本工具因单结果算子的限制只走 A/B，真实编译器还有「多结果融合」选项——避免读者把 A/B 误当成全部设计空间（这也与第 74～75 天收益话题衔接更自然）。
- **置信度**：高（上游机制已从源码核实）；是否补充不影响本日正确性。

#### 2. 构建耗时与编译告警的记录与实测不符
- **原文**：“构建（约 1～2 分钟，路径按你的 MLIR 安装调整）：”
- **依据**：在与 README 声明一致的本机环境（aarch64、g++ 9.4.0、Ubuntu LLVM 18.1.8）把 `mlir-mini` 复制到临时目录做全新构建（不覆盖仓库冻结产物），cmake 配置＋ninja 共 8 步、约 5 秒完成，远快于「约 1～2 分钟」；同时 g++ 报一条 `-Wunused-result` 告警：`mini-fuse-multi.cpp:152` 忽略了 `applyPatternsAndFoldGreedily` 返回的 `[[nodiscard]]` `LogicalResult`（头文件 `/usr/lib/llvm-18/include/mlir/Transforms/GreedyPatternRewriteDriver.h:139`）。建议把耗时改成「数十秒内」量级，并在代码中消费该返回值（`if (failed(...))` 或显式 `(void)`），与全文「决策必须说得出口」的工程风格一致。
- **置信度**：高（实测耗时与告警可在同环境直接复现）。
