# 第 87 天技术校对报告

审阅对象：`tutorials/week-013/day-087/`（README.md、`code/init_pass.py`、`code/make_images.py`、`code/outputs/` 三份产出、`images/` 四张 SVG）。审阅环境：aarch64 Linux、Python 3.11.4、numpy 1.26.4（与教程声明一致）。全部冻结产物已在临时目录复跑核对：`test-report.txt`、`init-ir.txt`、`debug-log.txt` 与四张 SVG 均可字节级复现（`make_images.py` 亦逐字节复现）；`--shape 2 3 2` 练习模式输出与 §5.4 实验一一致；把 `GARBAGE_BASE` 改为 100.0 重跑，IT3 none 策略实测 12 次未初始化读、max|C-ref| = 1.770e+02、首个垃圾值 100.0，与 §5.4 实验二的描述一致。MLIR 相关论断已对照官方文档（SCF Dialect、MemRef Dialect、DialectConversion、Linalg Dialect）与 llvm-project 源码（main、release/19.x/17.x/14.x、release/13.x）逐条核实：`memref.alloc` 不清零、`scf.for` 的 iter_args/yield 语义（含零次迭代结果＝初值、三方类型一致）、`-debug-only=dialect-conversion` 的调试输出格式均与文档相符。Day 85/86 的交叉引用（清单③、12 op 骨架、K≤8 选做、7.77e+02）均已核对无误。

## 【错误】

#### 1. `memref.fill` 不是上游 MLIR 的 op，教程把它当成 MLIR 的标准初始化写法教给读者
- **原文**：“想让内存里有确定的值，必须再有显式的写：`memref.fill`（整块写）或 `memref.store`（逐元素写）。”
- **依据**：已核对 llvm-project（main、release/19.x、release/17.x、release/14.x、release/13.x）的 `mlir/include/mlir/Dialect/MemRef/IR/MemRefOps.td`（memref 方言唯一 op 定义源，CMake 的 `add_mlir_doc` 也只从它生成文档）、当前官方 MemRef 方言文档的操作目录、`mlir/test/Dialect/MemRef/` 全部测试文件：memref 方言没有 `fill` 这个 op。上游用于给输出清零的标准结构化 op 是 **`linalg.fill`**（linalg 方言，destination-passing 风格，官方文档 FillOp："Fills the output tensor with the given value … takes a buffer and an additional scalar value"，语法为 `linalg.fill ins(%value : f32) outs(%dest : memref<...>)`）。本教程把 `memref.fill` 当作 MLIR 机制反复使用：README 第 3 行（“零起点放在**内存里**＝`memref.fill`＋读改写”）、§3.2（“必须先 `memref.fill %zero, %c` 保证读到 0.0”）、§7 选做（b）（“rewrite 多 create 一个 `memref.fill %zero, %c`”）、§9（“内存里（`memref.fill`，付 96 B）”），以及 `init_pass.py` 头部"MLIR 里的机制"对照表（"memref.fill %zero, %c ：把 C 全部元素写成 %zero"）和 `TARGET_LEGAL`、图 2 的方案 A 泳道。读者会合理地把 `memref.fill` 记成真实 op 并在真实 MLIR 里使用（将无法解析）。方案 A 的语义（先清零再读改写）与流量账（+96 B）本身正确，仅 op 引用失实。该错误与 day-085/technical-review.md 错误 2 是同一问题，Day 87 未修正、继续沿用并强化（README 第 5 行声称“文中 MLIR 行为描述均依据官方文档……核对（2026-11）”，但引用的两份文档都不覆盖 memref.fill）。
- **置信度**：高（对“当前上游 MLIR 的 memref 方言无此 op”已五版本源码级核实；真实等价物 `linalg.fill` 的存在与语义亦经官方文档核实）。

#### 2. 图 4 的"待填账本"把今天新增的 op 数写成 2，与真实计数矛盾（10＋2≠11，实为 10＋1＝11）
- **原文**：“Day 86 骨架 10 op ＋ 今天填的 2 处（`%zero` 常量＋iter_args/yield 升级）＝ 11 目标 op，Day 88 待填 5 op（load×2、mulf、addf、store），11＋5＝16 收官。”
- **依据**：今天 Pass 相对 Day 86 骨架**只新增 1 个 op**（`%zero = arith.constant 0.0 : f32`）：`iter_args(%acc = %zero)` 是对既有 `scf.for` 的修改（operands 追加初值、区域参数重建），`scf.yield` 从无操作数升级为带操作数也仍是同一个 op——README §1 自己写明“op 数 12 → 13”（12＝func＋alloc＋constant×5＋for×3＋yield＋return，13＝constant×6），冻结产物 `test-report.txt` 口径附注也写“主图 3 op → 13 op（骨架 10 ＋ %zero = 11 目标 op）"（即 10＋1＝11）。而 04-results.svg 把这段账本直接画成算术错误的文字：“今天已填：初始化（2 op）"“骨架 10 ＋ 2 = 11 目标 op"——10＋2＝12≠11，且"初始化（2 op）"与 13＝12＋1 的真实计数冲突（`make_images.py` 生成、字节级可复现）。README 图注的"10 op ＋ 今天填的 2 处 …… ＝ 11 目标 op”是同一混淆的源头："2 处”是两处**编辑**（其中只有一处新增 op），单位混用后落到图里就成了"2 op"。账本正是这张图的教学重点（左边面板），数字必须与 §1、§5.3、test-report 的三处口径一致。
- **置信度**：高。op 计数已由复跑 `init_pass.py` 与冻结产物双重核实（13 op；目标 op 口径 11＝10＋1）。

#### 3. §6 错误二声称"仿真里解释执行到 scf.for 时报类型不匹配"，实际仿真没有这个行为
- **原文**：“现象：类型检查失败，或仿真里解释执行到 `scf.for` 时报类型不匹配。”
- **依据**：把错误二描述的写法（`iter_args(%acc = %c0) -> (f32)`，初值为 index 常量）直接灌进 `Interp` 实测：将 `build_full_ir("B")` 产出的最内层 `scf.for` 的第 4 个操作数换成 `%c0 : index` 后，解释执行**不报任何错**，且因 Python 的 int 0 仍能当零起点，结果甚至保持位等价（实测 max|C-ref| = 0.0）。原因：`Interp` 全程无类型检查——`exec_for` 只取 `operands[3:]` 的值（init_pass.py 第 812~813 行），`Op` 构造、打印机、驱动器也都不校验类型；"类型检查失败"这一分支在本代码库同样无处发生（无 verifier）。真实 MLIR 里该错误确实会被抓住（scf 方言文档："The number and types of the scf.for results must match the initial values in the iter_args binding and the yield operands"，且 index≠f32 类型不匹配会被验证器拒绝），错误二讲的**机制**正确；错的是把“仿真会报错”写成已存在的现象——这正是 SKILL.md“不伪造执行结果”底线所禁止的那类描述，读者按图索骥会发现仿真既不报错、结果还全对，反而更加困惑。
- **置信度**：高（已用最小实验直接复现"不报错"的行为；代码逐行确认无类型校验路径）。

## 【存疑】

#### 4. §3.4 动态 alloc 的写法过于含糊：`memref<?x3>` 类型本身合法，且 `memref.alloc(%M, %N)` 与"仅 M 动态"的场景对不上
- **原文**：“动态 shape（比如 `tensor<?x6xf32>`，M 由运行时决定）下，alloc 的类型写不出 `memref<?x3>`（需要动态分配 `memref.alloc(%M, %N)`）”
- **依据**：官方 MemRef 文档对 `memref.alloc` 的规定是"dimension operands are bound to the dynamic dimensions specified in its memref type"，示例 `%0 = memref.alloc(%d) : memref<8x?xf32, 1>`——**动态尺寸操作数与类型里的 `?` 一一对应**。对照本句语境（M 动态、N=3 静态，输出类型 `memref<?x3xf32>` 只有一个 `?`），正确写法应是 `memref.alloc(%M) : memref<?x3xf32>`（一个操作数）；`memref.alloc(%M, %N)` 需要类型里有两个 `?`（如 `memref<?x?xf32>`），照抄会在验证器报错。另外"alloc 的类型写不出 `memref<?x3>`"按字面读是错的：`memref<?x3xf32>` 是完全合法的 MLIR 类型（静态/动态维可混合，alloc 文档的 `memref<8x?xf32>` 即是例证），本 README 的 IT4 也刚刚展示了签名转换产出 `memref<?x6xf32, strided<[6, 1]>>`；想表达的应是“本 Pattern 的无操作数静态 alloc 产不出带 `?` 的类型（`memref.alloc() : memref<?x3xf32>` 会因操作数与动态维数不符而非法）"。
- **置信度**：中。alloc 操作数与 `?` 维一一对应的规则已由官方文档核实（高）；存疑点仅在原句的两种读法——按“静态 Pattern 写不出动态类型”理解则结论成立、仅括号示例不符，按“该类型写不出”字面理解则为错误。建议改写为无歧义表述并修正示例。

#### 5. §5.4 实验三"不带 --debug 的普通运行里这行原因不存在"与本工具的真实输出不符，表述过于绝对
- **原文**：“而不带 `--debug` 的普通运行里，这行原因**不存在**——只有驱动器的"无法合法化 'mini.matmul'：已注册的 Pattern 都拒绝了这次匹配""
- **依据**：实测普通运行（`python3 init_pass.py`，不带 --debug）的 stdout：IT4 一行明确包含截断版拒绝原因——“拒绝原因（只在 --debug 调试树）：动态维度（A('?', 6) @ B(6, 3)）：alloc 类型与循环边界无法编译期确定…保守路径，宁拒不猜（True）"；同时 `outputs/debug-log.txt`（三个产出之一）**在任何运行模式下都会写入**，其案例 2 含完整的 `} -> FAILURE : 动态维度…` 行和驱动器的"无法合法化…”消息（test-report.txt、debug-log.txt 均已复跑核对）。反过来，句子声称"只有"的驱动器消息"无法合法化 'mini.matmul'：已注册的 Pattern 都拒绝了这次匹配"在普通运行的 stdout 里**并不出现**（它只存在于 `ConversionResult.message` 和 debug-log.txt）。若把“这行原因不存在”理解成驱动器 API 层面（不开 debug 时 `debug_lines` 为空、只返回失败消息）则成立，理解成用户可见输出层面则两处都与事实相反。教学意图（两级失败、排障要开 --debug）本身正确且重要，但作为“看两副面孔”的实验指引，描述应与实际输出对齐。
- **置信度**：中。工具输出已实测核实（高）；存疑点在于该句可以按“驱动器诊断 API”而非“stdout 呈现”解读，两种读法一真一假，需要作者澄清本意后改写。

## 【建议】

#### 6. §5.3 "初始化版 IR 全文"实为注释压缩版，与 `outputs/init-ir.txt` 逐字对照会不一致
- **原文**：“初始化版 IR 全文（`outputs/init-ir.txt`，留白处用预留注释标出 Day 88 的填空题）：”
- **依据**：代码块中的 op 行与冻结产物逐行一致，但注释被压缩重排：产物里每个常量后面的独立注释行（如“// 下界 0"）在 README 里改成了行尾注释，`// 任务① 输出缓冲 48 B…`、`// 任务③ 初始化 1/2…`、`// 任务③ 初始化 2/2…` 等行被省略，文件头部三行生成说明也未展示。对照学习的学生逐字 diff 会发现"全文"名不副实。建议改称"节选（注释压缩，op 行与产物逐行一致）"，或照抄产物原文。
- **置信度**：高（两份文本已逐行比对）。

#### 7. §5.4 的"（%c2 与 %c2' 去重）"用词易误读为常量合并（CSE），实际只是名字消歧
- **原文**：“%c0/%c1/%c2/%c2'/%c3 = arith.constant      // 0 / 1 / M=2 / N=2 / K=3（%c2 与 %c2' 去重）”
- **依据**：实际行为是创建了 **5 个** constant op（值 0/1/2/2/3），两个值恰为 2 的 op 各自存在，`cname()` 只对**名字**去重（撞名时追加撇号得到 `%c2` 与 `%c2'`），没有任何 op 或值被合并；总 op 数 13（含 6 个 constant）也证明未做 CSE。"去重"一词会让读者以为值相同的常量被合并掉了（真实 MLIR 里这要靠 canonicalizer/CSE pass 做，而不是命名时发生）。建议改成“名字消歧（两个值为 2 的常量各有其 op）"。
- **置信度**：高（`--shape 2 3 2` 实测输出与代码 `cname` 逻辑均已核对）。

#### 8. §6 错误三的“（或恰好只等于最后一项）”与该条讨论的两种病因对不上
- **原文**：“现象：Day 88 填完 load/mulf/addf 之后跑数值验证，C 全是 0（或恰好只等于最后一项）；”
- **依据**：本条讨论的两种错误形态——`yield %zero`（回传初值）和 `yield %acc`（回传自己）——都是恒等循环，下一迭代的 `%acc` 始终是 0.0，最终 C 全为 0；“C 恰好只等于最后一项”只有当 yield 回传**裸乘积** `%p`（而非部分和 `%s`）时才会出现，那是另一种未在本条提及的错误。建议要么删去这个括号，要么补一句“回传 %p（裸乘积）时才会只剩最后一项”，避免学生拿症状对错病因。
- **置信度**：高（对三种 yield 写法的语义推演均已在 exec_for 语义下验证成立）。

#### 9. §9 与 test-report 的“失败不留痕/回滚不留痕”未限定级别：Pattern 级为真，整个转换层面签名已被改写
- **原文**：“动态 `?` 保守拒绝、回滚不留痕——零起点显式化，垃圾读数为零，初始化这一层验收干净。”
- **依据**：IT5 的两条可验证结论本身都准确（“终图与只用 Init 的结果逐字相同：True”是 print_module 级全比较；“op 序列 = ['func.func', 'mini.matmul', 'func.return']（与转换前相同：True）”限定为 op 序列）。但"回滚不留痕”作为总结容易被读成“失败后 IR 与转换前完全相同"——实际驱动器的签名转换（`_convert_signature`）在合法化开始**之前**就已把函数签名改成 memref 形态，失败后不会回滚（代码路径：`apply()` 先 `_convert_signature` 再 `_legalize`），`%x/%w` 由此成为悬空引用。Day 86 评审（day-086/technical-review.md 错误 2）已在同一套基础设施上指出此问题。建议把“不留痕”限定为“Pattern 级事务（半成品 op 不残留）”，或补一句“签名转换已生效，op 序列不变”。
- **置信度**：高（代码路径与 Day 86 评审结论一致；Day 87 自身的两条逐字引用无问题，仅总结措辞过度）。

#### 10. “full 失败／partial 残留”未说明真实 MLIR 里 partial 容忍残留的前提是 op 未被显式标为非法
- **原文**：“驱动器换规则，full 模式下最终整体失败、partial 模式显式残留 `['mini.matmul']`。”
- **依据**：官方 DialectConversion 文档对 partial 模式的定义是“allow pre-existing operations that **were not explicitly marked as 'illegal'** to remain unconverted"——partial 容忍的只是 **unknown**（未标非法）的 op；若 `mini.matmul` 被显式标为非法（如 `addIllegalDialect("mini")`），所有 Pattern 拒绝后 partial 模式同样整体失败。本教程的 `TARGET_LEGAL` 白名单未明说对应哪种目标构造法：按“只 addLegalOp（mini 方言未标非法，视作 unknown）”读，仿真行为与真实 partial 完全一致；按“mini 方言显式非法”读则不一致。Day 85 评审（day-085/technical-review.md 错误 1）曾把“标非法＋partial 残留”的组合判为错误。这里"拒绝也是调度手段”“交给后续 Pass”的叙事完全正确，但初学者容易带走“partial 总能把没转完的 op 留下来”的过度推广——建议补一句边界：要留给后续 Pass 的 op 不能标非法（保持 unknown）。
- **置信度**：高（文档原文核实无误）；属准确性边界说明，不影响本教程在"白名单＝unknown"读法下的正确性。
