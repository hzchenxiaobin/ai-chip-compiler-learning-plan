# 第 85 天技术校对报告

审阅对象：`tutorials/week-013/day-085/`（README.md、`code/lowering_design.py`、`code/make_images.py`、`code/outputs/` 三份产出、`images/` 四张 SVG）。审阅环境：aarch64 Linux、Python 3.11.4、numpy 1.26.4（与教程声明一致）。全部冻结产物已在临时目录复跑核对：`test-report.txt`、`ir-loop.txt`、`design-doc.md` 与四张 SVG 均可字节级复现；`--shape 2 3 2` 练习模式输出与 §5.4 实验二的描述一致（6/6 PASS、P1 strides [1,2] 四红、流量账 32 B）。MLIR 相关论断已对照官方文档与 llvm-project 源码（main、release/19.x、17.x、14.x、llvmorg-13.0.0）逐条核实。

## 【错误】

#### 1. applyPartialConversion 的语义被讲反：显式标为非法的 op 在 partial 模式同样整体失败
- **原文**：“**构件三：`apply_conversion()`——驱动器仿真。** op 级工作列表：合法 op 跳过、有 Pattern 的非法 op 被替换成目标 op 序列、没 Pattern 的非法 op 在 full 模式整体失败、partial 模式显式残留（对应 `applyFullConversion` / `applyPartialConversion` 的语义差别）。”
- **依据**：真实 MLIR 中 partial 模式只容忍“既未标合法也未标非法”的 unknown op 残留，**显式标为非法的 op 无 Pattern 时 partial 模式也失败**。官方文档（DialectConversion - Modes of Conversion）：“A partial conversion will legalize as many operations to the target as possible, but will allow pre-existing operations that **were not explicitly marked as 'illegal'** to remain unconverted.”；源码 `mlir/lib/Transforms/Utils/DialectConversion.cpp` 的 `OperationConverter::convert` 在 partial 分支里写明 `if (opLegalizer.isIllegal(op)) { …; return failure(); }`，且诊断会带 “that was explicitly marked illegal”。本教程用 `addIllegalDialect` 把整个 mini 方言标非法（§5.2、design-doc §5），TP4 里无 Pattern 的 `mini.conv` 正是显式非法 op——真实 MLIR 下 `applyPartialConversion` 会失败而非“成功但残留”。受影响的同一论断还出现在：§3.2（“`applyPartialConversion`（允许残留给后续 Pass）”）、§5.3 引用的真实输出“含 mini.conv 变体 partial 模式：成功但显式残留 ['mini.conv']（交给后续 Pass）”（test-report.txt 第 32 行、design-doc §6）、图 2 底部红框、§5.4 实验三（“等 mini.conv 的规则写好了再谈 partial”——逻辑恰好反了：要把 op 留给后续 Pass 的正确做法是**不把它标非法**（保持 unknown），标了非法后 full/partial 都必须消除它）、§6 错误二的修复选项三（“改用 `applyPartialConversion` 并确认下游有人接手”，若保留非法标记同样会失败）。仿真代码 `apply_conversion()` 的 partial 分支把显式非法 op 当可残留处理，与它声称“对应”的 API 语义不符。
- **置信度**：高。依据为官方文档原文与 main 分支源码逐行核对；该行为在各历史版本中长期稳定。

#### 2. `memref.fill` 不是上游 MLIR 的 op，方案 A 的“做法”引用了一个不存在的算子
- **原文**：“| A：fill＋读改写 | `memref.fill(%c, 0.0)`，k 循环外先 load C[i,j] 再累加 | +2×M×N×4 = **96 B** | ✓ |”
- **依据**：已核对 llvm-project（main、release/19.x、release/17.x、release/14.x、llvmorg-13.0.0）的 `mlir/include/mlir/Dialect/MemRef/IR/MemRefOps.td`、当前官方 MemRef 方言文档的操作目录以及 `mlir/test/Dialect/MemRef/ops.mlir`：memref 方言没有 `fill` 这个 op。上游用于给输出清零的标准结构化 op 是 **`linalg.fill`**（destination-passing 风格，语法为 `linalg.fill ins(%value : f32) outs(%dest : memref<...>)`，见官方 linalg 方言文档 FillOp）。本教程同表其余 op 名（`memref.alloc`、`scf.for`、`memref.load/store`、`bufferization.to_tensor`）均为真实 MLIR op，§6 错误一还专门以“真实 MLIR 里 bufferization 已经提供了……标准实现”的口径引用真实 op，读者会合理地把 `memref.fill` 也当成真实 op 记住（仿真里的 `TARGET_LEGAL` 同样收录了 `memref.fill`，强化了这一印象）。此外，即使按 `linalg.fill` 的口径，其操作数顺序是 value 在前、dest 在后且使用 ins/outs 语法，`memref.fill(%c, 0.0)` 的括号式写法（memref 在前、值在后）也不对应任何真实 op 的汇编格式。方案 A 的语义（先清零再读改写）与流量账（+2×M×N×4=96 B）本身正确，仅 op 引用失实。
- **置信度**：高（对“当前上游 MLIR 的 memref 方言无此 op”）。不排除个别下游 fork 定义过同名 op，但教程语境明确指向上游 MLIR。

#### 3. 冻结产物 `outputs/ir-loop.txt` 的 alloc 行缺一个收尾 `>`，README 展示版与实际产物不一致
- **原文**：“  %c = memref.alloc() : memref<4x3xf32, strided<[3, 1]>>”
- **依据**：README §5.3 称该代码块是 `outputs/ir-loop.txt` 的内容（节选常量定义），但实际冻结文件第 6 行是 `  %c = memref.alloc() : memref<4x3xf32, strided<[3, 1]>          // [类型] 结果缓冲，48 B`——`strided<[3, 1]>` 之后只有一个 `>`，memref 类型的外层 `>` 缺失，括号不平衡；同一行还原样嵌入在 `outputs/design-doc.md` 的附录里。原因是生成模板笔误：`lowering_design.py` 的 `make_ir_text` 中该行模板为 `strided<{sc}>`（漏写最后一个 `>`），其余行（如函数签名的 `strided<[6, 1]>>`）均平衡，在临时目录重跑可逐字节复现该缺陷。README 展示时“顺手”补上了括号，掩盖了产物文件的问题。
- **置信度**：高。文件内容已直接核验，并经重跑生成器复现。

#### 4. “Day 83 终图剩下的 `reshape((24,)→(4,6))`”误述了该 op 的输入形状
- **原文**：“底部两条设计备注各管一头：**向前衔接**——Day 83 终图剩下的 `reshape((24,)→(4,6))` 在 Lowering 里免费（连续存储重排只是 strides 元信息改写，零搬运，Day 84 补讲 1 已证明）；**向后铺垫**——Day 86 把 S2 从"规则表"变成真正的 ConversionPattern 骨架，今天的三张清单就是那天的填空题。”
- **依据**：Day 83 终图（`tutorials/week-012/day-083/code/outputs/ir-02-after-fusion.txt`）里剩余的 op 是 `%13 = reshape %x new_shape=[4, 6]`，其中 `%x` 形状为 (2,12)——即 **reshape(2,12 → 4,6)**；原图 reshape 链里的 (24,) 中间形状在“Reshape 合并”后已不存在（Day 83 审计日志：“Reshape 合并 @ %13：reshape(reshape(%x)) → 一次到 [4, 6]”）。Day 84 补讲 1 自己的表述也是“终图剩下的 `reshape(2,12→4,6)`”。Day 85 把它写成 `reshape((24,)→(4,6))`（同样的说法还出现在 §7 选做挑战与 design-doc §9.1）与被引用的终图不符。24 元素连续存储、零搬运、“strides 元信息改写”的结论本身不受影响，仅被引用 op 的输入形状写错，属于跨天引用的事实性偏差。
- **置信度**：高（Day 83 冻结 IR 与 Day 84 原文均可直接核对）；对当天计算无影响。

## 【存疑】

#### 1. `bufferization.to_memref` 在最新 LLVM main 已更名为 `to_buffer`，教程未标注版本口径
- **原文**：“修复：在 TypeConverter 里补对应方向的物化钩子；真实 MLIR 里 bufferization 已经提供了 `bufferization.to_tensor`/`to_memref` 这对标准实现。”
- **依据**：该说法对 LLVM ≤ 20（含多数现行发行版与教材）是正确的：release/20.x 的 `BufferizationOps.td` 定义了成对的 ToTensorOp/ToMemrefOp，且 to_tensor 的描述明确写着二者“useful for source/target materializations when doing type conversions”。但当前 llvm-project main 已把 `to_memref` 更名为 **`to_buffer`**（官方 Bufferization 文档现列 `bufferization.to_buffer`/`bufferization.to_tensor`，Bufferization 综述文档的示例也已全部改用 `to_buffer`）。教程全文未标注所依据的 MLIR 版本；若按写作时点的最新主线核对，此处应更新名称或加版本注记。同一名称也出现在图 2 的“物化钩子①”与仿真的 `TARGET_LEGAL` 中（仿真内部命名无需改，但“真实 MLIR”层面的表述需核版本）。
- **置信度**：高（对“main 已更名”这一事实，已核对官方文档与 20.x 源码）；更名具体落入哪个 release 版本未逐一核实，不确定点仅在版本边界。

## 【建议】

#### 1. 索引任务表把 k 循环边界挂在 C[i,j] 行，容易误读为“C 的寻址与 k 有关”
- **原文**：“| C[i,j] | (i,j) | 3·i + 1·j | k ∈ [0,6) | A.shape[1]==B.shape[0]（内维契约） |”
- **依据**：C[i,j] 的读/写发生在 i、j 两层循环里，其线性地址只含 i、j；k ∈ [0,6) 是归约循环（A、B 的累加维度）的边界，不属于“C[i,j] 所属循环”。表格为把三条循环边界各列一次，把 k 边界分配到了 C 行，初学者容易据此以为 C 的地址公式与 k 相关（A 行、B 行同理也只各列了两条相关边界中的一条）。建议 C 行改标 i/j 循环，k 边界单列一行“归约循环 k（内维契约）”；design-doc §3.2 与图 3 便签② 有同款表述可一并斟酌。表中公式、边界数值本身全部正确（已复算）。
- **置信度**：高（对“关联误导”的判断）；属表述组织问题，不涉及数值错误。

#### 2. `ir-loop.txt` 与真实 MLIR 语法的差距宜显式声明，避免读者日后照抄 parse 失败
- **原文**：“        %xa = memref.load %a[%i, %k]     // addr = 6*%i + 1*%k”
- **依据**：真实 MLIR 的 `memref.load`/`memref.store` 自定义汇编要求尾随类型（`memref.load %a[%i, %k] : memref<4x6xf32, strided<[6, 1]>>`，见 MemRefOps.td 的 assemblyFormat 及官方文档示例），`ir-loop.txt` 的所有 load/store 都省略了 `: memref<...>`；`return %c : memref<4x3xf32>` 用的是不带 strided 的类型，与 `%c` 声明的 strided 类型不一致（真实 MLIR 中 return 类型须与值类型一致）；§1 源图用裸 `return`，而现行 func 方言的终结符是 `func.return`（教程自己的 `TARGET_LEGAL` 写的也是 func.return）。作为“仿真示意 IR”这些省略可以接受，但 README 未声明“省略了类型标注”，读者把这段贴进 mlir-opt 会直接 parse error。建议在 §5.3 或 `ir-loop.txt` 头部注释补一句说明。顺带核实：`strided<[6,1]>` 不写 offset 在真实 MLIR 中是合法语法（`mlir/test/Dialect/MemRef/ops.mlir` 中大量出现无 offset 用例），这一点无误。
- **置信度**：高（语法要求均已对照官方文档/源码核实）。

#### 3. §5.2 代码摘录中 `Cf` 未定义即被使用
- **原文**：“        Cf[:] = np.float32(0.0)”
- **依据**：摘录顶部的 `...` 只覆盖了函数开头到 `C = np.full(...)` 之前的行，而完整代码里 `Cf = C.ravel()` 位于 `C = np.full(...)` 之后（lowering_design.py 第 100 行），摘录把它省略了却未再标注 `...`，导致 `Cf` 首次出现即被赋值使用。照抄该骨架运行会 NameError。建议在摘录中补上 `Cf = C.ravel()` 一行，或在 `if design.init ...` 之前再加一个 `...`。
- **置信度**：高（摘录与完整代码已逐行比对）。

#### 4. “驱动器入口”只列了两种模式，遗漏 applyAnalysisConversion
- **原文**：“**构件三：`apply_conversion()`——驱动器仿真。** op 级工作列表：合法 op 跳过、有 Pattern 的非法 op 被替换成目标 op 序列、没 Pattern 的非法 op 在 full 模式整体失败、partial 模式显式残留（对应 `applyFullConversion` / `applyPartialConversion` 的语义差别）。”
- **依据**：官方 DialectConversion 文档列了三种模式：Partial（`applyPartialConversion`）、Full（`applyFullConversion`）、Analysis（`applyAnalysisConversion`——只分析哪些 op 可合法化、不做任何改写）。§3.2 的“驱动器入口是 `applyFullConversion`……和 `applyPartialConversion`……”同样只提两种。对当天教学主线（full vs partial）而言省略 Analysis 不算错误，但既然给出了入口清单，补一句“另有 applyAnalysisConversion 只分析不改写”更完整，也为后续阶段“先体检再动手”的方法论留了接口。
- **置信度**：高（文档核实无误）；属完整性建议，不影响现有论述正确性。
