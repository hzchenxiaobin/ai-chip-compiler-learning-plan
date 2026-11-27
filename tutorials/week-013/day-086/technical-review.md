# 第 86 天技术校对报告

校对方式：在临时目录完整运行 `lowering_pass.py`（默认、`--debug`、`--shape 2 3 2`、`--shape 2 2 2`）并逐字节比对三个产出文件与 `make_images.py` 再生的 4 张 SVG（全部一致，6/6 PASS 属实）；对 MLIR 相关论断核对官方文档《Dialect Conversion》《Pattern Rewriting》（mlir.llvm.org，2026-11）及 llvm-project main 的 `DialectConversion.h/.cpp` 源码；跨天事实对照 Day 64/65/85/87/88 的教程与代码。本报告只记录意见，不改动教程原文。

## 【错误】
#### 1. 选做练习（a）把 mini.transpose 的 match 问题误写成“2 个操作数”
- **原文**："match 问三个问题（2 个操作数？已是 memref？2 维？"
- **依据**：本仓库 mini 方言的 `mini.transpose` 是单输入算子：Day 65 `tutorials/week-010/day-065/code/transpose_elim_lab.py` 中 `MiniTransposeOp.print_ir()` 生成 `%r = mini.transpose %x permutation = [...] : (in_t) -> (out_t)`（1 个操作数）；Day 87/88 的 transpose 练习也都按单输入纯拷贝描述（`load A[j,i] → store C[i,j]`）。若按本句写 `len(adaptor.operands) != 2` 的检查，该 Pattern 会对所有 `mini.transpose` 永远 notifyMatchFailure，练习设定的验收目标“验证它被转换”不可能达成。正确写法应是“操作数恰好 1 个”。这是从 matmul 四连问复制时未改动的笔误。
- **置信度**：高。仓库内 Day 64/65 的 mini.transpose 定义与 Day 87/88 的引用一致，均单输入；不确定点仅在于若作者另有“双输入 transpose”的未公开设计则不成立，但仓库内无任何证据。

#### 2. 图 3／图 4 图注声称“失败后 IR 与转换前完全一样”，与实测结果不符
- **原文**："反例 B 证明只注册 HalfDone 时失败后 IR 与转换前完全一样"
- **依据**：在临时目录复现 DT6-B（只注册 `HalfDoneMatMulPattern`、full 模式）：失败后 op 名序列确为 `['func.func', 'mini.matmul', 'func.return']`，但函数签名已被驱动器的 S1 签名转换改写——`func @main(%a: memref<4x6xf32, strided<[6, 1]>>, %b: memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32, strided<[3, 1]>>`，而函数体里 `%mm = mini.matmul(%x, %w)` 与 `return %mm` 仍引用已不在参数表中的旧 tensor 值（%x/%w 成为悬空引用）。IR 不仅不是“完全一样”，甚至不再是自洽 IR；`dt6_atomicity_and_contract` 的检查本身也只比对 op 名序列（`after_names == before_names`），没验证签名。同病还出现在 §5.3 图 4 图注“只注册半途而废 Pattern 时失败后 IR 与转换前完全相同（失败不留痕）”；而 §5.4 实验三的表述“IR 的 op 序列与转换前一致”和 pass-report.txt 的“op 序列……与转换前相同”都是准确的。两处图注应改为“op 序列与转换前一致、无骨架半成品残留”，或注明签名转换已生效。
- **置信度**：高（实际运行逐行对比转换前后 `print_module` 输出；DT6-B 的代码逻辑亦可静态推出同一结论）。

## 【存疑】
#### 3. “create/replaceOp/eraseOp 都只写进暂存区”若外推到真实 MLIR 不准确
- **原文**："对应到技术上是三段式事务：`create`（新建 op）、`replaceOp`（结果替换＋擦除 root）、`eraseOp` 都只写进**暂存区**"
- **依据**：官方文档《Dialect Conversion》“Immediate vs. Delayed IR Modification”一节的表格明确：Op Insertion / Movement（create/insert）在 rollback 模式**和** no-rollback 模式下都是 Immediate（立即生效），被延迟的只有 Op Replacement（replaceOp）、Op Erasure（eraseOp）、Value Replacement（replaceAllUsesWith）等且仅限 rollback 模式；真实 MLIR 没有“把 create 攒进暂存区、commit 时统一插入”的机制，失败时靠 undo 动作删除已建 op。本节随后的“诚实声明”只说明了 replaceOp/eraseOp 的延迟和整路径回滚，未点出 create 是立即生效，读者容易把“全部走暂存区”当成真实 ConversionPatternRewriter 的语义。同段“事务性保证：每条 Pattern 看到的 IR 都是干净的”对真实 MLIR rollback 模式也偏乐观——官方文档明说转换中途 IR 是新旧混合（“users see a mixture of old and new IR”）。作为对第 86 天仿真（create 确实进 `_Txn`）的描述则完全正确。
- **置信度**：中。判定取决于读者把这句当成 MLIR 语义还是仿真语义；建议在诚实声明里补一句“真实 MLIR 的 create 是立即插入 IR 的，本仿真把 create 也暂存是为了简化”。

#### 4. “找 `* Pattern : ...` 块末尾的 `FAILURE : 原因`”只适用于仿真格式，真实 MLIR 的原因在块内
- **原文**："重跑，找 `* Pattern : ...` 块末尾的 `FAILURE : 原因`。"
- **依据**：真实 MLIR（llvm-project main 的 `mlir/lib/Transforms/Utils/DialectConversion.cpp`，2026-11 核对）中，`ConversionPatternRewriterImpl::notifyMatchFailure` 在被调用时即在 pattern 块**内部**打印 `** Failure : <原因>`；而 pattern 块的收尾行由 onFailure 固定打印 `} -> FAILURE : pattern failed to match`，不带具体原因。且真实调试树的 pattern 行打印的是 `* Pattern : '<root op> -> (<generated ops>)'`（官方文档 Debugging 示例：`* Pattern : 'func.return -> ()'`），不是 Pattern 的 debug 名（仿真里是 `* Pattern : 'MatMulSkeletonPattern'`）。按本句指引去真实 MLIR 的块末行找原因，只能找到 "pattern failed to match"，原因其实在块内上一行。教程已声明调试树“刻意模仿”该格式，且 §3.3 关于“dialect conversion 把 remark 放进 -debug-only=dialect-conversion 调试树、普通运行不打印”的核心论断与源码一致，故列为存疑而非错误。
- **置信度**：中高（源码与官方文档示例双重核对）。建议在该句后补一句真实格式的差异（`** Failure : 原因` 在块内、收尾行固定为 `pattern failed to match`）。

#### 5. “全绿才走到 SUCCESS”与紧邻展示的调试树打印顺序不一致
- **原文**："而 Insert 出来的 10 个新 op 会被驱动器逐一"Legalizing"检查合法性，全绿才走到 SUCCESS。"
- **依据**：`outputs/debug-log.txt` 案例 1 的实际顺序是：mini.matmul 的 pattern 块先打印 `} -> SUCCESS : pattern applied successfully` 和外层 `} -> SUCCESS`，**然后**才逐个出现 10 个新 op（alloc、constant×5、for×3、yield）的 `Legalizing operation` 块；仿真里若某个新 op 非法，matmul 的 SUCCESS 也已经打印出去了（`_try_patterns` 先记 SUCCESS，新 op 由 `_legalize` 下一轮循环检查）。真实 MLIR 恰好相反：`legalizePatternResult` 先递归 legalize 生成的新 op、再打印 “pattern applied successfully”（官方文档 Debugging 示例中 spirv.Return 的 Legalizing 块位于 pattern 块**内部**、SUCCESS 之前）。本句若指“最终整趟转换成功（转换完成）”则成立；若指所示调试树里的 SUCCESS 行，则与自己的输出顺序矛盾，且仿真与真实 MLIR 在此处的顺序差异未被“诚实声明”覆盖。
- **置信度**：中。语义有歧义（两种读法一种成立一种不成立）；建议明确“全绿”指哪一层 SUCCESS，或注明仿真把新 op 的 Legalizing 打在 SUCCESS 之后、真实 MLIR 打在 pattern 块之内。

## 【建议】
#### 6. “骨架 IR 全文”实为节选，注释位置有重排
- **原文**："骨架 IR 全文（`outputs/skeleton-ir.txt`，留白处用预留注释标出 Day 87/88 的填空题）："
- **依据**：skeleton-ir.txt 实际 28 行：开头有 3 行文件头注释，且每个常量 op 的说明注释（`// 下界 0`、`// 步长 1`、`// M ← A.shape[0]` 等）独立成行跟在 op 之后。README 的“全文”省略了头注释和 %c0/%c1 的两行注释，并把其余注释内联到 op 行尾（如 `%c4 = arith.constant 4 : index      // M ← A.shape[0]`）。op 行与类型本身逐字一致，不影响技术正确性，但初学者逐行对照文件时会发现“全文”并不全。§5.4 实验一引用的 `--shape 2 3 2`“真实结果”同样做了注释内联并把三重 for 压缩成一行。建议标注“节选、注释格式有精简”。
- **置信度**：高（与产出文件逐行比对）。

#### 7. §5.2 代码摘录的省略未打省略号，个别消息文案与文件原文有出入
- **原文**："（完整代码见文件，这里讲关键段）"
- **依据**：两段摘录都有无声省略：commit() 摘录省掉了 `if txn.replacements:` 分支（为空时走 eraseOp 路径 `body.remove(root_op)`）和 `self.last_created = list(txn.created)`，摘录形式上会让人以为 commit 无条件执行 `body[idx:idx+1] = top`；matchAndRewrite 摘录使用了摘录内未定义的 `cname()`（文件里是内嵌函数，还带 `used` 集合），且个别 notifyMatchFailure 消息与文件原文略有出入（文件为“操作数还不是 memref（拿到 {ta} / {tb}）——检查签名转换/TypeConverter”）。正文引用的 DT5/DT6 输出与真实文件一致，不受影响。建议在摘录省略处加 `...` 或注一句“有删节”。
- **置信度**：高（与 lowering_pass.py 逐行比对）。

#### 8. 补一句“真实 MLIR 的 adaptor 只保证类型、不保证值身份”
- **原文**："配了 TypeConverter 时，这些值的类型就是合法化之后的类型。"
- **依据**：官方文档《Dialect Conversion》“Remapped Operands / Adaptor”一节的 Note 明确写道："The dialect conversion framework does not guarantee the presence of any particular value in the operands argument. The only thing that's guaranteed is the type of the operands SSA values. E.g., instead of the actual replacement values supplied to a replaceOp API call, operands may contain results of transitory builtin.unrealized_conversion_cast ops that were inserted by the conversion driver"。教程只讲了“类型已合法化”，没提醒值身份可能是驱动器插入的临时 unrealized_conversion_cast——这是从仿真走向真实 MLIR 时“拿值的名字/指针做身份判断”的经典坑（本仿真用对象 id 做映射，恰好掩盖了这一点）。加一句提示可避免误解。
- **置信度**：高（官方文档原文核对，2026-11）。不影响本仿真正确性，故列建议。

#### 9. 补一句“真实驱动器在试 Pattern 之前会先尝试 Fold”
- **原文**："按 benefit 从高到低找 Pattern 试；"
- **依据**：官方文档《Dialect Conversion》Debugging 一节的示例输出里，每个 op 先出现 `* Fold { } -> FAILURE : unable to fold` 块，之后才是 `* Pattern : ...` 块；DialectConversion.cpp 也有对应的 `OperationLegalizer::legalizeWithFold` 路径（fold 成功即视为合法化成功，失败才继续试 pattern）。教程 §2 五步路线与 §5.2 构件三都未提 Fold，初学者第一次打开真实 `-debug-only=dialect-conversion` 输出会看到陌生的 `* Fold` 块。一句话带过即可，与本仿真无冲突（仿真没有实现 fold）。
- **置信度**：高（官方文档示例与源码双重核对）。
