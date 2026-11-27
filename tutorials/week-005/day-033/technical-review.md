# 第 33 天技术校对报告

审阅范围：`tutorials/week-005/day-033/README.md`、`code/` 下 4 个文件、`images/` 下 3 张 SVG。核实环境与教程声明一致（Ubuntu 20.04 aarch64、LLVM 18.1.8，`mlir-opt-18`／`mlir-cpu-runner-18`）。除标注外，全部结论均在本机实际运行复核：完整重放 `probe.sh`（写入 `/tmp/day033/`），并对存疑点做了控制变量实验与 MLIR 18.1.8 上游源码比对（llvm-project release/18.x）。教程的绝大部分实测数据（方言计数 8/1/2/4/2＝17、五级行数／op 数 16/17→18/19→35/32→65/47→97/68、s3 的 16 块＋15 条 cf 分支、s4 的 malloc／icmp／getelementptr、JIT 139／270、探针①～⑥报错原文、错误 7 的静默无效等）复现一致，值得肯定；以下只列有问题的条目。

## 【错误】

#### 1. 错误 1 的机理："大数或 NaN → fptosi 饱和成 INT_MIN"在本机（aarch64）对 NaN 和正大数不成立
- **原文**："原因：`tensor.empty()` 的内容未定义，bufferize 后是一块**没清零的 malloc 内存**；`linalg.matmul` 的 outs 是累加语义，`C[i][j] = 垃圾 + A·B`。垃圾里若有大数或 NaN，`fptosi` 转不出来就饱和成 INT_MIN。"
- **依据**：在声明环境（aarch64、LLVM 18.1.8）用教程同款五级管道做了控制垃圾值的实测（把 outs 预填成已知值再走完 bufferize→…→canonicalize→JIT）：填 NaN（0x7FC00000）→ JIT 打印 **0**；填 +3.0e30 → 打印 **2147483647（INT_MAX）**；填 -3.0e30 → 打印 **-2147483648（INT_MIN）**。即 fptosi 落到 aarch64 的 fcvtzs 指令：NaN 得 0、正溢出饱和到 INT_MAX、只有负向溢出才得 INT_MIN；"NaN／大数 → INT_MIN"是 x86 `cvttss2si` 的行为，搬到本教程的 aarch64 环境不成立。另外按 LLVM LangRef，fptosi 结果放不下目标类型时是 poison（未定义行为），"饱和"只是各平台的落实现象，不能当确定语义讲授。观测到的 -2147483648 应来自"负的大垃圾值"，而非 NaN 或任意大数。（补充：本次重放探针⑦三连跑均为 139——新进程的 malloc 恰好清零时"偶然对"会稳定出现，与"每次都可能不同"不矛盾，但也说明该现象依赖堆状态。）上游诊断（outs 未初始化、偶然对 ≠ 正确、修复用 linalg.fill）本身正确。
- **置信度**：高（三种垃圾值均经教程同款管道实测）

#### 2. 错误 3（探针③）因果归因错误：欠条残留的真正原因是漏了 `--canonicalize`，按原文"补上 --convert-index-to-llvm"并不能修复
- **原文**："原因：`index` 类型的转换没做完，框架插了 `builtin.unrealized_conversion_cast`（i64 ↔ index）欠条垫着；翻译到 LLVM IR 时欠条还不上，报错退出。"
- **依据**：探针③的管道与教程完整 PIPE4 其实有**两处**差异：既少了 `--convert-index-to-llvm`，也少了 `--canonicalize`（对照 probe.sh 第 17 行与第 68 行）。控制变量实测：A＝完整 PIPE4 只去掉 `--canonicalize`（**保留** index 转换）→ 仍残留 7 条 `builtin.unrealized_conversion_cast`，JIT 同样报 `LLVM Translation failed`；B＝只去掉 `--convert-index-to-llvm`（**保留** `--canonicalize`）→ 欠条 0 条，JIT 打印 139 成功。因此失败由缺 `--canonicalize` 引起，与 index 转换无关。进一步核实：本管道 IR 从头到尾没有任何 `index.*` 方言 op（各级方言清单都不含 index），MLIR 18 的 `ConvertIndexToLLVMPass` 只重写 index 方言 op（源码 `IndexToLLVM.cpp` 的 pattern 列表可证），在这条管道上本是空转。那 7 条 cast 检查后**全部没有使用者**（死代码）：它们是 func／arith→llvm 转换在消费者（memref.load 等）尚未转换时物化的 i64→index 桥，随后续 Pass 转完消费者自然死亡，靠 `--canonicalize`／`--cse` 清扫掉；LLVM IR 翻译器对哪怕死掉的 `builtin.unrealized_conversion_cast` 也直接报错。所以"欠条还不上、要补 index 转换"的诊断不成立——按"修复"一节的字面建议（只补 index，不加 canonicalize，即场景 A）复跑仍会失败。顺带指出：图 2"欠条"卡（"漏 --convert-index-to-llvm：残留 cast"）与图 4（原图 3）D 面板"③ 欠条没还：漏 index 转换"沿用了同一错误归因；对初学者真正该讲的坑是"漏 `--canonicalize` 会把死欠条留在产物里、JIT 才爆"。
- **置信度**：高（A／B／C 三组对照均在本机复现，并与 MLIR 18.1.8 源码一致）

#### 3. 选做 (c) 的"实测答案"与题面操作的实际结果不符：只漏 `--convert-cf-to-llvm` 时 JIT 成功打印 139，不会挂在欠条上
- **原文**："任选其一：(a) 把 A 改成 3×3（A ＝ [[1,2,3],[4,5,6],[7,8,9]]，其余不动），**先预测** C[2][0] 和 i 循环上界各是多少（笔算：7·7＋8·9＋9·11），再跑验证——M 的变化应该只传播到 i 上界，k 仍是 3；(b) 复现错误 7：自己构造一个"顺序错→静默无效"的例子（比如把 `--convert-scf-to-cf` 放到 `--convert-linalg-to-loops` 之前），验证它同样 exit 0 且什么都没发生；(c) **先预测**：漏掉 `--convert-cf-to-llvm` 会怎样——是像漏 scf 一样报 `Dialect cf not found`，还是像漏 index 一样爆欠条？写下猜测再跑（本机实测的答案有点意外：产物里一条 `cf.` 都不剩——别的 Pass 把 cf 顺手处理掉了——最后挂在 `unrealized_conversion_cast` 的欠条上；查查产物里还剩什么 op，想想谁替 cf 干了活）。"
- **依据**：按题面在声明环境执行（完整五级管道仅去掉 `--convert-cf-to-llvm`，其余含 `--convert-index-to-llvm` 与 `--canonicalize` 全保留，单次调用与从 s3 分级调用各跑一遍）：mlir-opt exit 0，产物 0 条 `cf.`、0 条 `unrealized_conversion_cast`，`mlir-cpu-runner` 直接打印 **139**——完全成功，不挂任何欠条。"一条 `cf.` 都不剩、别的 Pass 把 cf 顺手处理掉了"这部分属实：MLIR 18 的 `ConvertFuncToLLVMPass` 在 `FuncToLLVM.cpp` 里显式加载了 cf 的转换模式（`cf::populateControlFlowToLLVMConversionPatterns`，源码注释带 TODO(issue 70982) 拟移除），即 `--convert-func-to-llvm` 会把 `cf.br`／`cf.cond_br` 顺手转成 `llvm.br`／`llvm.cond_br`（用只含 func＋cf 的最小文件单独验证过）。"最后挂在 unrealized_conversion_cast 的欠条上"只在**同时**漏掉 `--canonicalize`（或 index 转换）时才会发生（与探针③同机制）。按题面操作的学习者会看到 JIT 成功打印 139，与教程给出的"答案"直接矛盾；作者记录的现象疑似来自同时缺 `--canonicalize` 的管道。
- **置信度**：高（单变量复现＋最小用例＋源码佐证）

#### 4. "每级一张合法性清单（ConversionTarget）"对台阶②（linalg→loops）不成立，且与教程自己的错误 7 相矛盾
- **原文**："**③ 每级一张合法性清单**。ConversionTarget 声明"这级走完，`linalg`/`scf`/`memref` 必须消失"；漏掉某个转换 Pass，清单不闭合，产物里就有方言住户没搬走——JIT 到门口直接拒收（第 6 节 4 张"not found"罚单）。"
- **依据**：MLIR 18.1.8 的 `ConvertLinalgToLoopsPass`（`mlir/lib/Dialect/Linalg/Transforms/Loops.cpp`）根本没有 ConversionTarget：它用 `applyPatternsAndFoldGreedily` 贪心模式重写，且返回值被 `(void)` 显式丢弃——这个 Pass **永远不会报错**，linalg op 留在产物里也一声不吭。教程自己的错误 7 就是活反例：tensor 版 linalg op 原样穿过、exit 0、无任何报错——如果台阶②真有一张"linalg 必须消失"的清单，那次实验应当以失败告终。真正使用 ConversionTarget 的是台阶④（`--convert-scf-to-cf`：`target.addIllegalOp<scf::ForOp…>`＋`applyPartialConversion`）和各 *ToLLVM Pass（`LLVMConversionTarget`）。另外"not found 罚单"是 `mlir-cpu-runner` 解析层查方言注册报的错（执行前），也不是 ConversionTarget 在编译期拦的。台阶②／④／⑤机制并不相同，"每级一张清单"的统一叙述对台阶②失实，建议按 Pass 分别表述（scf→cf 与 *ToLLVM 有合法性清单；linalg→loops 是贪心重写、漏形态只静默跳过）。
- **置信度**：高（上游源码＋教程自身实验互证）

#### 5. 选做 (b) 的预期观察"什么都没发生"与实测不符：整条管道变化很大，静默无效的只是提前执行的那个 Pass
- **原文**："任选其一：(a) 把 A 改成 3×3（A ＝ [[1,2,3],[4,5,6],[7,8,9]]，其余不动），**先预测** C[2][0] 和 i 循环上界各是多少（笔算：7·7＋8·9＋9·11），再跑验证——M 的变化应该只传播到 i 上界，k 仍是 3；(b) 复现错误 7：自己构造一个"顺序错→静默无效"的例子（比如把 `--convert-scf-to-cf` 放到 `--convert-linalg-to-loops` 之前），验证它同样 exit 0 且什么都没发生；(c) **先预测**：漏掉 `--convert-cf-to-llvm` 会怎样——是像漏 scf 一样报 `Dialect cf not found`，还是像漏 index 一样爆欠条？写下猜测再跑（本机实测的答案有点意外：产物里一条 `cf.` 都不剩——别的 Pass 把 cf 顺手处理掉了——最后挂在 `unrealized_conversion_cast` 的欠条上；查查产物里还剩什么 op，想想谁替 cf 干了活）。"
- **依据**：实际执行 `mlir-opt-18 matmul_run.mlir --one-shot-bufferize --convert-scf-to-cf --convert-linalg-to-loops`：exit 0 ✓，但产物与输入差别巨大——linalg op 全部消失、生成 5 条 `scf.for`（fill 2＋matmul 3）、`cf.` 一条不剩。静默无效的只是**提前执行的 `--convert-scf-to-cf`**（运行时 IR 里还没有任何 scf op，无事可做），随后 `--convert-linalg-to-loops` 照常把 linalg 炸开成循环——这与错误 7 的"IR 基本原样吐回"性质完全不同，按错误 7 的定位方法（grep `scf.for` 没有结果）来验证反而会"失败"（能搜到 5 条）。若读者接着补齐后续 Pass，还会得到与探针⑥相同的"scf.for 残留"产物。该练习的预期观察写错了：不是"什么都没发生"，而是"该发生的那步（scf→cf）被跳过、其余照常发生"。
- **置信度**：中（按字面把"它"读作整条命令则明确失实，已实测复现；若作者本意是"提前放置的单个 Pass 什么都没做"，属表述歧义，但按错误 7 的对照口径读者必然误解）

## 【存疑】

#### 6. "你的项目也可以直接 scf → LLVM"：MLIR 18 并无现成的 scf→llvm 转换 Pass
- **原文**："两点补充：**cf（显式控制流）是 loop → LLVM 的中转站**——`scf.for` 先拆成块和跳转（台阶④，Day 31 的 CFG 正式形态）再进 LLVM，这是社区管道的惯例，你的项目也可以直接 scf → LLVM；**memref 的引入点**由 bufferization 决定——今天它发生在台阶②，你的项目在 Day 85～89 可以选择先留在 tensor 世界、最后统一 bufferize（Day 57 起再细究）。图 2 底部的三层塔就是这张表的图形版——**它就是今天要交的"Dialect 分层图"**。"
- **依据**：查 `mlir-opt-18 --help`（LLVM 18.1.8）：scf 相关转换只有 `--convert-scf-to-cf`／`--convert-scf-to-emitc`／`--convert-scf-to-openmp`／`--convert-scf-to-spirv` 等，不存在任何 scf→llvm 的现成 Pass；错误 6 自己也说"scf.for 没有到 LLVM 的直接转换规则"，与此处"可以直接 scf → LLVM"自相矛盾。若意指"自写 DialectConversion 规则直落 LLVM"，技术上可行，但要自己维护循环头块／条件块／步进与 i1/i64 映射，对初学者远非"换个开关"。表述容易让读者以为存在现成路径，建议改为"也可以自写规则从 scf 直落 LLVM，但通常沿用社区惯例 scf→cf→llvm"。
- **置信度**：中（现无现成 Pass 已核实；"可行"指自写转换，属解读层面）

## 【建议】

#### 7. 台阶⑤"4 个 LLVM 转换＋canonicalize"少算了 `--finalize-memref-to-llvm`，图内标注同样各漏一项
- **原文**："| s4 LLVM 层 | 4 个 LLVM 转换＋canonicalize | 97 | 68 | 只剩 **llvm**（其余全退场） |"
- **依据**：5.3 的命令里台阶⑤实际运行 5 个转换 Pass（`--convert-cf-to-llvm`／`--convert-func-to-llvm`／`--convert-arith-to-llvm`／`--convert-index-to-llvm` 4 个 `--convert-*-to-llvm` ＋ `--finalize-memref-to-llvm`）再加 `--canonicalize`，共 6 个；"4 个 LLVM 转换＋canonicalize"漏了 finalize（且按发现 2，真正让 JIT 跑通的 `--canonicalize` 恰是这句里最容易被当成"可有可无"的一项）。图 2 台阶箭头写"--convert-*-to-llvm ×4＋finalize"、图 4（原图 3）面板 A 写"×4＋canon"，两处各漏一项，三处口径还不一致。另外该行"只剩 llvm"与实测方言清单 `[builtin, llvm]` 有出入（正文 219 行已说明 builtin.module 壳仍在，表格可同样标注）。
- **置信度**：高（对照 5.3 命令即可复核）

#### 8. 图 1 交付物栏"probe.sh：6 组实验＋6 个错误探针"与正文和脚本对不上
- **原文**："> **今日产出**：`code/` 下 4 个文件：`matmul_run.mlir`（主例子：一条 op 走完五级台阶）、`matmul_run_k4.mlir`（5.4 对照：K=3→4）、`matmul_nofill.mlir`（翻车探针：未初始化 outs）、`probe.sh`（一键重放 3 组实验＋7 个探针），以及它们在本机的真实运行记录；外加四张图，其中图 2 底部的**项目 Dialect 分层塔**就是今天计划要求的交付物。"
- **依据**：probe.sh 的实际结构是 4 组实验段（实验①／②／③＋5.4 对照）＋7 个探针（①～⑦）＋1 段选做预告；README 全文口径是"3 组实验＋7 个探针"（把 5.4 单列）。图 1 交付物栏却写"6 组实验＋6 个错误探针"——两个数字在任何口径下都对不上（探针就是 7 个；"错误探针"若指错误 2～7 也只有 6 条但探针⑦对应错误 1 同样是错误探针）。属图文数值不一致，不影响机制理解，建议统一为"3 组实验＋5.4 对照＋7 个探针"。（注：本条引用锚点行因审阅后插入配图由"三张图"改作"四张图"，引用已同步为当前正文；该发现针对图 1 内的数字，不受影响。）
- **置信度**：高

#### 9. 5.4 对 A 的变化描述"补一行"应为"每行补一个元素（K 维补一列）"
- **原文**："`matmul_run_k4.mlir` 与主例子只差两行：A 变 `tensor<2x4xf32>`（补一行 [1,2,3,4]／[5,6,7,8]），B 变 `tensor<4x2xf32>`（补一行 [13,14]）。**先预测**：C[1][0] ＝ 5·7＋6·9＋7·11＋8·13 ＝ 35＋54＋77＋104 ＝ 270。跑两级看看（本机真实输出）："
- **依据**：A 从 `[[1,2,3],[4,5,6]]` 变为 `[[1,2,3,4],[5,6,7,8]]`：行数不变（仍 2 行），是**每一行末尾补一个元素**（K 从 3 到 4，即补一列）；B 才是真正的补一行（3 行变 4 行）。代码、形状与 270 的结果均正确，仅"补一行"的措辞容易让初学者误以为 M 变了（M 变是选做 (a) 的事），建议改成"每行补一个数（K 3→4）"。
- **置信度**：高
