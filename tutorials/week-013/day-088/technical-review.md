# 第 88 天技术校对报告

校对方法：在临时目录完整重跑 `loop_pass.py`（默认、`--shape 2 3 2`、`--shape 4 0 3`、`--debug`）与 `make_images.py`，四件 outputs 与 4 张 SVG 均逐字节复现；`scf.for` 语义逐条对照 mlir.llvm.org 官方 SCF dialect 文档（2026-11 在线版本），涉及 verifier／lowering 行为的论断对照 llvm-project main 分支源码（mlir/lib/Dialect/SCF/IR/SCF.cpp、mlir/lib/IR/Verifier.cpp、mlir/lib/Conversion/SCFToControlFlow/SCFToControlFlow.cpp、mlir/lib/Transforms/Utils/DialectConversion.cpp）。本机未装 MLIR，无法用 mlir-opt 实测，凡引用源码处均已注明。总体结论：核心语义（半开区间、trip 公式、step 严格为正、iv 为区域第一参数、终止器显隐规则）与官方文档完全一致，代码与产出真实可复现；以下问题集中在少数计数口径与标注上。

## 【错误】

#### 1. (2,3,2) 被标为"非方形"，与教程自己的方阵判据和"5 组非方形"计数冲突
- **原文**：“边界成员：最小 (1,1,1) · 行向量 (1,5,3) · 内维 1 (5,1,3) · 非方形 (2,3,2)/(3,2,7) · 贯穿例 (4,6,3) · 零趟 (4,0,3)”
- **依据**：SHAPES 里的 (2,3,2) 即 A(2,3)@B(3,2)→C(2,2)，M=2、N=2，按 §3.1 自己给出的判据"如果 M = N（方阵）……测试全绿"属于方阵，§5.4 也明说"M = N = 2 是**方阵**"，§3.1/§6 又说"BT5 有 5 组"非方形（= (1,5,3)/(5,1,3)/(3,2,7)/(4,6,3)/(4,0,3)，不含 (2,3,2)）。把 (2,3,2) 标进"非方形"两处都矛盾；若改按"A 是 2×3 非方阵"理解，非方形就有 6 组，"5 组"又错。该行由 loop_pass.py 硬编码生成，README §5.3 节选与冻结产出 test-report.txt 同错，修任一侧需同步另一侧（boundary-table.txt 第 4 行本身无此标注，不受影响）。
- **置信度**：高。

#### 2. "骨架 10 op ＋ Day 87 初始化 2 op ＝ 11 目标 op"算术不成立
- **原文**：“骨架 10 op ＋ Day 87 初始化 2 op ＝ 11 目标 op”
- **依据**：Day 86 报告原文"转换后 12 op：func.func + 骨架 10 op（alloc 1 ＋ constant 5 ＋ for 3 ＋ yield 1）＋ func.return"，Day 87 README 写"op 数 12 → 13"——Day 87 相对 Day 86 只新增 %zero 这 1 个 op（iter_args 挂载与 yield 升级都不是新增 op）。10＋2＝12≠11；自洽的写法是"骨架 10＋Day 87 初始化 1＝11 目标 op"。冻结的 images/04-results.svg（"骨架 10＋D87 初始化 2 = 11 目标 op"）与 README 图注同错。
- **置信度**：高。

#### 3. "13 op → 16 op 收官"把两种 op 计数口径接在同一支箭头上
- **原文**：“13 op → 16 op 收官”
- **依据**：本日 test-report.txt 口径附注 1 明确区分两种口径：总 op 数含 func.func/func.return（今天 13 = func＋alloc＋constant×6＋for×3＋yield＋return），"目标 op"不含它们（今天 11）。"16 目标 op"= 11＋Day 89 待填 5；同口径下明天之后是 13＋5＝18（总）或 11＋5＝16（目标）。"13 op → 16 op"左端用总口径、右端用目标口径，读者按任一口径核算都得不到 16。Day 87 结尾预告的写法（"收官 16 目标 op"）带了"目标"限定，本句丢失了该限定。
- **置信度**：高。

#### 4. "想倒序遍历……交换 lb/ub"的建议不成立：交换后是零趟空循环
- **原文**：“想倒序遍历不是用负步长，而是交换 lb/ub”
- **依据**：官方 scf.for 规则 1（已在 mlir.llvm.org SCF 文档核对，2026-11）：trip = max(0, ceil((UB−LB)/Step))。把 lb、ub 的值互换后 UB−LB 为负，max(0, ·)＝0——得到的是零趟空循环（正是本日 §3.3/BT5 的零趟语义），不会倒序执行任何元素；scf.for 也没有任何写法能倒序枚举。真正的做法是保持 step 为正、升序枚举，再在循环体内把下标映射成 ub−1−j 一类。BT5 的 (4,0,3)（上界 0 ≤ 下界 0 → trip 0）就是"ub≤lb 零趟"的实测反例。
- **置信度**：高。

## 【存疑】

#### 1. "st ≤ 0 直接非法"过于绝对：scf.for 的 verifier 并不检查常量 step 的符号
- **原文**：“`st ≤ 0` 直接非法”
- **依据**：官方文档确实写"The step is required to be strictly positive"，语义层面的引用无误。但 2026-11 的 mlir/lib/Dialect/SCF/IR/SCF.cpp 中 ForOp::verify()/verifyRegions() 只查 iv 类型与 iter_args 数量，不查 step 符号；同文件只有 scf.parallel 的 verify 会报"constant step operand must be positive"。即常量负/零 step 的 scf.for 能通过解析与验证，属于"文档规定非法"而非"工具直接拒绝"；SCFToControlFlow lowering 用 `iv slt ub` 做循环条件，lb<ub 时负 step 变成不终止的循环、lb>ub 时零趟——两种情况都不会倒序执行。"直接非法"宜改为"官方语义规定非法（scf.for 的 verifier 不强制，scf.parallel 会拦常量非正 step）"。
- **置信度**：高（文档与 llvm-project main 源码已核对；本机无 MLIR，未用 mlir-opt 实测拒绝与否）。

#### 2. "max(iv) 必须等于 ub − step"的对账口诀只在 step 整除 (ub−lb) 时成立
- **原文**：“`max(iv)` 必须等于 `ub − step`”
- **依据**：由官方规则 iv = lb + j·step（j = 0…n−1）、n = max(0, ceil((ub−lb)/step))：当 (ub−lb) 不被 step 整除（ceil 多出一趟）时，max(iv) = lb + (ceil((ub−lb)/step)−1)·step，可以严格大于 ub−step。反例：lb=0、ub=5、step=2 → n=3、iv∈{0,2,4}、max=4 ≠ ub−step=3。本日全部循环 step=1（恒整除），实测 3=4−1、2=3−1、5=6−1 都成立；但 §3.2 已预告 Day 94 的 tile 步长与 Day 95 的非整除尾部，届时这条口诀会失效，可靠的不变式是"max(iv) < ub"。建议给口诀加上"step 整除 (ub−lb)（含 step=1）时"的限定（§8 验收清单与图 2/图 3 的"iv 最大值 = ub−step"同此）。
- **置信度**：高（数学事实，可由官方公式直接推出）。

## 【建议】

#### 1. 支配性错误的"真实报错文本"与 MLIR 实际诊断格式不符
- **原文**：“use of value '%i' does not dominate”
- **依据**：mlir/lib/IR/Verifier.cpp 的 diagnoseInvalidOperandDominance 实际输出是 op.emitError("operand #") << operandNo << " does not dominate this use"，形如"'xxx' op operand #0 does not dominate this use"，并没有"use of value '%i' does not dominate"这种文案。教程用反引号把它呈现为真实输出，宜标注为转述或改用真实格式；技术结论本身（verifier 用支配性检查拒绝体外使用 iv）正确。
- **置信度**：高（源码核对；未在本机用 mlir-opt 实测）。

#### 2. "四要素缺了两个"与 §5.4"会动态的只有 ub"自相矛盾
- **原文**：“alloc 类型也写不出，四要素缺了两个”
- **依据**：§5.4 原文"四要素里有两个（lb 的 0、step 的 1）永远静态，**会动态的只有 ub**"——动态 '?' 真正影响的四要素只有 ub 一个；alloc 类型写不出是另一件事，但 alloc 类型不属于"四要素"。§3.4 与 test-report.txt 的"四要素缺了两个"均与之矛盾。建议统一为"ub 这一要素物化不出来（输出 alloc 类型也写不出）"。
- **置信度**：高（教程内部文本可直接对照）。

#### 3. "(2,3,2) 只当练习、不进 BT5 的非方形名单"容易被读成"不在 BT5 里"
- **原文**：“所以它只当练习、不进 BT5 的非方形名单”
- **依据**：SHAPES 包含 (2,3,2)，boundary-table.txt 第 4 行"A(2,3) @ B(3,2) → C(2,2)：trips(i,j,k) = (2, 2, 3)……PASS"——它就在 BT5 的 7 组名单里，并非"只当练习"；准确说法是"它在 BT5 里只是普通成员（方阵组），不属于 5 组非方形"。配合【错误】第 1 条的标注问题，两处一起改可以消除"这个形状到底在不在 BT5、算不算非方形"的歧义。
- **置信度**：高。

#### 4. 官方语义漏收了第二条规则：LB + n·Step 必须可表示，否则未定义行为
- **原文**：“官方语义五条钉死（`[lb, ub)` 半开、`trip = max(0, ceil((ub-lb)/step))`、iv = `lb + j·step`、step 严格为正、iv 是区域第一个参数）”
- **依据**：官方 scf.for 文档的精确语义由两条编号规则给出，第 2 条是"No-overflow condition: LB + n*Step must be representable in the type of the induction variable. Otherwise the behavior is undefined"（为了让 lowering 可以用"单寄存器递增＋比较"实现）。本日的 iv 全是 index 类型，实际几乎碰不到溢出，但 scf.for 的 lb/ub/step 也允许 i32 等整型（图 2 自己写了"index 或整数类型"），此时这就是真实的坑。属可选补充，不影响本日正确性。
- **置信度**：高（文档原文；对初学者影响小）。
