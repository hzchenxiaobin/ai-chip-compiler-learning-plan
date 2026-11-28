# 第 119 天技术校对报告

校对范围：`tutorials/week-017/day-119/`（README.md、code/ 全部脚本、outputs/ 全部冻结产物、images/ 三张 SVG），并交叉核对 D113~D118 冻结产物与 D53/D71~D74/D78~D81/D85~D87/D102~D105/D106/D111 等被引天。验证方式：本机复跑 `map_layers.py`、`run_all.sh`（Linux aarch64，Python 3.11.4，无 mlir-opt，8/8 自检通过，产物与冻结值一致）；census.py 逐文件复算；gemm-3.ll / gemm-3.s / gemm-2-llvm-dialect.mlir / llvm23-2-llvm-dialect.mlir 逐行核对；版本史实经 llvm-project 提交记录核实。本机无 mlir-opt，跨版本段无法现场重跑，只核对了冻结的两侧产物文本。

## 【错误】

#### 1. 实验 B 把 i 循环上界 4 认成 ubN、“N=3 的矩阵宽度”
- **原文**：“4 是 ubN 常量（gemm.mlir `%ubN = arith.addi %c3, %lb`，其中 `%lb = %c6 - %c6 = 0` 的朴素冗余被 canonicalize 折叠）→ 它是 N=3 的矩阵宽度”
- **依据**：`gemm-3.ll` 第 33 行 `%39 = icmp slt i64 %38, 4` 是最外层 i 循环的边界；i 循环上界在 gemm.mlir 里是 `%ubM = arith.muli %c2, %c2`（=2×2=4，即 M——4×3 结果的行数），`%ubN = arith.addi %c3, %lb`（=3+0=3）对应第二个（j）循环，导出后是 `icmp slt i64 %42, 3`（gemm-3.ll 第 41 行）。`gemm-0-optimized.mlir` 同样显示 `scf.for %arg2 = %c0 to %c4`（i 上界 4）。所以 4 是 ubM 而非 ubN；且 4×3 矩阵的“宽度”是 N=3，4 是行数 M——“它是 N=3 的矩阵宽度”自相矛盾。按此指引反查的学习者会拿 `%ubN`（=3）去解释指令里的 4，对不上号。
- **置信度**：高（gemm.mlir、gemm-0-optimized.mlir、gemm-3.ll 三份冻结文件交叉验证）。

#### 2. Tile 决策叙事与 `icmp slt i64 %38, 4` 错误挂钩，“Tile 32×64”无仓库记录出处
- **原文**：“②Tile 决策在循环层消费：D106 搜索空间 → D111 冠军 tile=32 的决策，到 scf.for 变成边界常量，到 .ll 变成 `icmp slt i64 %38, 4`”
- **依据**：gemm.mlir 自述为“朴素前端”风格（无任何 tile），走完 D117 管道的这条 .ll 里的 4 是朴素上界 ubM（2×2），与任何 tile 决策无关——tile=32 的决策从未进入本周管道。D111 的真实冠军记录（code/outputs/tune-summary.json、self-test.txt）是“32³ ikj U=1”（自测）与“64³ ikj U=1”（S1），是 tile 三元组＋循环序＋展开，全库检索不存在“Tile 32×64”这个冠军。§3.3“没有‘Tile 32×64 是搜索出来的’”与图 2 泳道 B“循环层边界常量 32/64 内联 → .ll 层 `icmp slt i64 %38, 4`”同样把 32/64 与该指令并列——被引指令里的立即数是 4，句内自相矛盾；泳道 B 末尾“机器码 subs 立即数”也与 gemm-3.s 不符（实际是 `add x12, x12, #1`＋`cmp x12, #5`，无 subs）。“决策变成边界常量、来历消失”的机制论述本身成立，但具体证据引用是错配：本例能演示的是“朴素边界常量”，演示不了“搜索出来的 tile”。
- **置信度**：高（gemm.mlir 头注释、gemm-3.ll、D111 冻结记录三方对照）。

#### 3. “bias 融合决策（D78~D81）”天号错位
- **原文**：“bias 加在 k=0 圈的融合决策（D78~D81）在任务单里写死后，循环层再也看不出 bias 与普通 add 的区别”
- **依据**：D78~D81 的主题是数值精度与量化（D78 浮点表示与累加误差、D79 参考实现与误差指标、D80 FP16/BF16 测试、D81 INT8 量化基础，见 week-012 各天 README 与 overview），与算子融合无关。MatMul+Bias 融合出自 D53（“MatMul＋Bias 融合——bias 的形状对上了”），融合收益/代价账在 D71~D74，“bias 融合在 k=0 圈”的约定见 D102/D103/D105（D105 原文：“bias 融合在 k=0 圈，同 D102/D103”），Lowering 任务单的 bias 预填初始化见 D85~D87。§4 泳道 A“图层的融合决策（D78~D81）”同错。按现在的写法，学习者回读 D78~D81 会完全找不到出处。
- **置信度**：高（各天 README 标题与内容直接核对）。

#### 4. “LLVM 15 起 poison 全面替代 undef”版本论断错误
- **原文**：“＋`undef`→`poison` 的改名（LLVM 15 起 poison 全面替代 undef）”
- **依据**：教程自己的冻结证据即反证：D117 产物出自 LLVM 18.1.8（D117 README 环境声明），其中仍是 `llvm.mlir.undef`（3 处）——若“LLVM 15 起（2022 年）全面替代”为真，LLVM 18 不会打印 undef。实际变化来自 llvm-project 提交 f4e3b8783cb9eb9a442b14ec8ce7356fa6853387（2025-02-06，"[mlir][LLVM] Switch `undef` for `poison` for uninitialized values (#125629)"，进入 LLVM 21 开发周期），落在 18 与 23 之间，与两份文件观察吻合。且这不是 op 改名，而是转换模式从 UndefOp 切换到 PoisonOp；LLVM IR 中 `undef` 与 `poison` 并存至今，该提交自述也只是"moving away from `undef`"，并非“全面替代”。§5.3 引用的 run-all-log 括注“（LLVM 15+ 起 undef 全面让位 poison）”同错。
- **置信度**：高（冻结文件＋上游提交双重证据；MLIR 侧结论确定，LLVM IR 侧“并存”依据 LangRef 长期状态）。

#### 5. `%47 = phi float` 在机器码里对应的寄存器写错（s1 应为 s0）
- **原文**：“`%47 = phi float` 变成 `s1` 寄存器”
- **依据**：gemm-3.s 内层循环为 `ldr s1, [x19, x12, lsl #2]` / `fmul s1, s1, s2` / `fadd s0, s0, s1`——phi `%47`（k 圈累加器）的落点是 **s0**（`fadd s0, s0, s1` 的目的操作数），s1 只是装载 A 元素/乘积的临时寄存器。寄存器号与冻结汇编不符。
- **置信度**：高（gemm-3.s 第 55~59 行直接可查）。

#### 6. 图 3 周总账“66 项”与正文“63 项”矛盾（SVG 自身也不一致）
- **原文**：“我按每周复盘模板完成第 17 周总账：63 项（5+7+8+9+22+12）、双环境验证、三笔跨天账（残账、胶水、malloc 债务）各有去向”
- **依据**：03-week-report.svg 的总账行写“六天全部 PASS：8+7+8+9+22+12 = 66 项”，而同一张图的 D113 卡片写“5步过 PASS”——求和行把 D113 记成了 8（疑为把 D115 的 8/8 抄串），正确口径是 5+7+8+9+22+12=63，与 README 两处（今日目标“六天 63 项 PASS 判定”、§9“63 项判定（5+7+8+9+22+12）”）一致。图与正文、图与自身卡片互相矛盾；验收清单要求“63 项”时，对着图会数出 66。
- **置信度**：高（SVG 文本提取验证：总账行为 8+7+8+9+22+12=66，D113 卡片为“5步过 PASS”）。

#### 7. census 分解“arith 10”与实测 arith 11 不符，分解合计只有 20
- **原文**：“实测：census：21 op（func 1、arith 10、scf 4、memref 4、return 1...）”
- **依据**：本机复跑 census.py（与 D117 逐字节同款）得：arith.constant×6＋arith.addf/addi/mulf/muli/subi 各×1＝**arith 11**；func.func 1＋func.return 1；memref.alloc 1＋load×2＋store×1＝4；scf.for×3＋yield×1＝4；合计 21。README 所列分解相加只有 1+10+4+4+1=20，arith 少了 1（漏数了 6 条 constant 或 5 条运算之一）。该错误同时固化在 map_layers.py 的 LAYERS 表与冻结产物 lowering-map.txt（README §5.2 代码块同文）。
- **置信度**：高（机器复算，口径与教程自带的 census.py 完全一致）。

#### 8. 周测第 8 题参考答案把 `_mlir_ciface_gemm` 的生成者写成 mlir-translate
- **原文**：“`code/outputs/information-test.txt`（12 题周测，样例 10/12＋参考答案）”
- **依据**：该产物中第 8 题“_mlir_ciface_gemm 是谁生成的？”的“正确答案”A 写“mlir-translate 由 llvm.emit_c_interface 属性驱动自动生成”——生成 `_mlir_ciface_gemm` 包装的是 mlir-opt 的 `--convert-func-to-llvm`（FuncToLLVM 转换），不是 mlir-translate：D117 冻结的 `gemm-2-llvm-dialect.mlir`（mlir-opt 阶段 2 产物，尚未运行 mlir-translate）第 86 行已包含 `llvm.func @_mlir_ciface_gemm`；mlir-translate 只负责把 LLVM 方言翻成 .ll 文本。此错误沿承自 D117 README“让 mlir-translate 自动生成”的表述（错误源头在 D117，本日周测把它固化成“正确答案”教给学习者），后续修正需两天同改。本条原文引用锚定 README 对周测产物的介绍行，错误文本位于 information-test.txt／map_layers.py 的 QUIZ。
- **置信度**：高（冻结中间产物直接证明包装在 translate 之前已存在）。

#### 9. 主产物 lowering-map.txt 层 7：“机器码只有位宽没有 f32/i64 之分”与自身证据矛盾
- **原文**：“`code/outputs/lowering-map.txt`（**今日主产出：七层×保留/丢失/新增对账表＋面试口径**）”
- **依据**：主产物层 7“丢失”栏写“类型——机器码只有位宽没有 f32/i64 之分”，但其证据文件 gemm-3.s 里 f32 与 i64 分明可见：浮点用 s 寄存器与 `fmul s1, s1, s2`／`fadd s0, s0, s1`，整数用 x 寄存器与 `add x12, x12, #1`／`cmp x12, #5`——AArch64 机器码通过寄存器类别与指令编码明确区分浮点/整数。真正丢失的是“类型检查/类型系统”（无 Verifier、无类型名），不是“f32/i64 之分”。该过度概括被当天自己的汇编证据反证。本条原文引用锚定 README 对主产物的介绍行，错误文本位于 lowering-map.txt 层 7。
- **置信度**：高（gemm-3.s 逐行核对）。

#### 10. 主产物 lowering-map.txt 层 3：“四块×3 循环”与同句“9 块”算术矛盾
- **原文**：“③cf 层（9 块、3 cond_br，蓝）”
- **依据**：README 引的“9 块、3 cond_br”属实（gemm-1-scf-to-cf.mlir 实测 9 个带标签块、3 条 cf.cond_br），但主产物 lowering-map.txt 同层“实测”栏写“9 块、3 cond_br（四块×3 循环）”、丢失栏写“拆散进 init/header/latch 四块”——4×3=12≠9，且“init/header/latch”只列 3 个名字却称“四块”。实际结构（gemm-1-scf-to-cf.mlir）：i 循环 bb1/bb2/bb8、j 循环 bb3/bb4/bb7、k 循环 bb5/bb6（body 与 latch 合并）＋出口 bb9，前置块与上一循环共享。D117 图 2 的“一层 scf.for 变四个块”是教学抽象，直接相乘到 9 块上算术不成立。本条原文引用锚定 README 图 1 描述中对 cf 层的引述，错误文本位于 lowering-map.txt 层 3。
- **置信度**：高（块结构逐块核对，12≠9 的矛盾确定）。

#### 11. “%c1a 变 %14”映射与 R2 规则及冻结文件均矛盾
- **原文**：“丢失 ✗ MLIR 的名字——%c1a 变 %14、^merge 变 10:（D113 R1 重编号）”
- **依据**：gemm-3.ll 中不存在 %14：参数 %0~%13 之后第一条指令是 %15——%14 正是 D113 自己讲的“入口块占槽位却从不显示”，不是任何常量。%c1a（常量 1）在优化层已与 %c1b 被 CSE 合并成一条 `%c1 = arith.constant 1`（gemm-0-optimized.mlir），方言层对应 `%20`／`%24` 一类的 `llvm.mlir.constant(1 : index)`，到 .ll 层按 R2 直接内联为立即数（如 `add i64 %46, 1`）——常量从不占槽位，这正是 R2 的内容。"%c1a 变 %14"与教程同段引用的 R2 相互矛盾，也与三份冻结文件不符；"^merge 变 10:"是 D113 step 例子的真事实，两个不同例子的映射被拼接在了一起。
- **置信度**：高（gemm-0-optimized.mlir、gemm-2-llvm-dialect.mlir、gemm-3.ll 逐文件核对）。

## 【存疑】

#### 1. “+3 extractvalue”的成因表述与差异实际位置有出入
- **原文**：“（LLVM 23 的 finalize-memref-to-llvm 重建描述符时多提取 3 次字段）”
- **依据**：数字属实（实测 D17 冻结 14 条 → LLVM 23 产物 17 条 `llvm.extractvalue`），但 +3 全部位于 @gemm 循环体（`%46/%52/%61 = llvm.extractvalue %15[1]/%7[1]/%38[1]`——load/store 从描述符提取 aligned 指针），而 LLVM 18 冻结版的循环体直接使用裸指针参数 `%arg1/%arg8/%29`；即差异是“循环体访存改走描述符字段提取”，不是“重建描述符时”。具体由哪个 pass 的哪个版本变更引起，本机无 mlir-opt 无法逐版本核实（未做上游提交比对）。表述与实测差异位置略有出入，但不影响“+3 全是 extractvalue、结构语义稳定”的结论。
- **置信度**：中（差异位置已核实；成因归到 finalize-memref-to-llvm 的具体变更未经源码级确认）。

## 【建议】

#### 1. README 引用的“真机输出”与冻结 run-all-log.txt 不完全一致
- **原文**：“`./run_all.sh` 的真机输出（outputs/run-all-log.txt）：”
- **依据**：README 引用的日志块与冻结文件有两处出入：时间戳“2026-11-14 20:22” vs 冻结文件“20:23”；“[附] 跨版本 op 分布差异”在冻结文件中位于“汇总：合计：8/8”之后，README 引用挪到了之前。且 [附] 段并非 run_all.sh 的脚本输出（脚本不含该段，属人工附加的 diff 摘要）。学习者拿 README 对着 outputs/ 逐字 diff 会对不上。建议引用时逐字复制或注明节选。
- **置信度**：高（两份文本并排比对）。

#### 2. “每层五栏”列了 6 项、“七个字段”与实际 8 个键不一致
- **原文**：“每层五栏：形态/证据/实测/保留/丢失/新增”
- **依据**：该句列出的栏目是 6 项（形态/证据/实测/保留/丢失/新增）；§5.2 又称“每层七个字段”，而 map_layers.py 的 LAYERS 字典实为 8 个键（name/day/form/evidence/has/lost/gain/numbers）。计数口径前后不一，建议统一（如“三栏内容＋形态/证据/实测共六栏”）。
- **置信度**：高（原文与代码直接对照）。

#### 3. lowering-map.txt 层 5 的“新增”把 range 放错了层
- **原文**：“新增 ★ 寄存器级别的直线 SSA（优化器的输入形态）；值域注记（range）...”
- **依据**：层 5 的证据文件 gemm-3.ll 里没有任何 range 注记（已逐行核对）；`range(i32 41, 1)` 出现在 D113 step 的**优化后** IR，属层 6 的领地，且层 6 的“新增”已列“值域/溢出注记（nuw）”。层 5 把 range 列为自己的新增，与其“每条挂证据”的自述不符。建议把该项移到层 6 或注明出处是 D113 的 O2 产物。
- **置信度**：高（gemm-3.ll 无 range，事实清楚；归类属编辑问题）。

#### 4. “sret 三指针包装”宜注明是“sret 式”约定而非字面 sret
- **原文**：“`llvm.emit_c_interface` 生成 `_mlir_ciface_gemm` 的 sret 三指针包装”
- **依据**：冻结 .ll 里 `define void @_mlir_ciface_gemm(ptr %0, ptr %1, ptr %2)` 的第一个参数是普通 `ptr`（无 sret 属性），结果用 `store {...} %20, ptr %0` 写回；D115 的实测口径是“大于 16B 的返回在 aarch64 上走 x8 隐式结果指针（sret 式）”。周测 Q10 的“正确答案”也写“描述符经 sret 写回”。学习者在 .ll 里搜 `sret` 会搜不到，建议注明是类比说法（C ABI 的 sret 模式）而非 LLVM 属性。
- **置信度**：高（.ll 原文核对；D115 口径引用）。

#### 5. “D115 账本 14/18”天号与 D116 重跑口径不一致
- **原文**：“我能讲出至少一条跨三天的因果链（例：D114 排期 C1→D117 → D115 账本 14/18 残账 C1×4 → D117 清账 18/18 → D118 执行）”
- **依据**：14/18＋残账 C1×4 是 D116 重跑 D115 的 GEMM IR 得到的账本（D116 README：“D115 的 GEMM IR 重跑账本：14/18，残账恰好只剩 C1×4”）；D115 当天自己的账本是 8/18＋残账 10 条。本日“前置准备”里“D116 三层验证法＋账本（……GEMM 14/18 残账 C1×4）”归位正确，§6/§8 却写成“D115 账本 14/18”，前后不一。建议统一为“D115 的 GEMM IR 在 D116 重跑得 14/18”。
- **置信度**：高（D115/D116 两日 README 原文对照）。

#### 6. “malloc 折叠”未出现在当天方言层 diff 中，三项并列引用宜分层
- **原文**：“与 D118 实验 A 的观察（poison 替代、malloc 折叠、gep 加 inbounds nuw）互相印证”
- **依据**：当天冻结的 llvm23-2-llvm-dialect.mlir 直接体现了 poison 与 `llvm.getelementptr inbounds|nuw` 两项，但 malloc 字节数仍以 `gep＋ptrtoint` 计算（`%25 = llvm.mlir.constant(12)`→`getelementptr`→`ptrtoint`→`call @malloc`）——“折叠成 i64 48”是 D118 实验 A 在 .ll/优化层观察到的现象，不在本日的方言层产物里。三项并列说“互相印证”时，建议注明层级差异，避免学习者在本日产物里找“malloc 折叠”找不到。
- **置信度**：高（两份冻结产物逐行核对）。
