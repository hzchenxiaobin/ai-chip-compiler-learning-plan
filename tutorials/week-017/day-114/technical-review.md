# 第 114 天技术校对报告

校对范围：README.md、code/（final_lowering.py、loop_ir.mlir、variants/residual.mlir、run_all.sh、gen_images.py）、code/outputs/ 全部冻结产物、images/ 三张 SVG。校对基线：在 /tmp/opencode 临时目录完整重跑 `python3 final_lowering.py`、`./run_all.sh`、`--shape 2 3 2`、`--shape 3 4 2` 与 `gen_images.py`，7/7 PASS，报告与样板文件（除时间戳）与冻结输出逐字节一致，环境（Python 3.11.4 / aarch64 / numpy 1.26.4 / llvmlite 0.50.0 内嵌 LLVM 22.1.0）与文中声明相符。涉及真实 MLIR 行为的论断逐条对照了 LLVM main 的源码与官方文档（DialectConversion.md、LLVM 方言文档、MemRefBuilder.h、MemRefToLLVM.cpp、TypeConverter.cpp、FuncToLLVM 测试、Passes.td）。

## 【错误】

#### 1. partial conversion 的语义与真实 MLIR 不一致：显式标记为非法的 op 翻不动时，applyPartialConversion 同样失败
- **原文**：“**partial conversion（部分转换）允许翻不完**——翻不动的 op 留在原地，驱动器给它打一份"残留报告"，整体算成功”
- **依据**：真实 MLIR 对 partial 的定义是“允许**未被显式标记为非法**的 op 留下”，而不是“允许翻不动的 op 留下”。官方文档（DialectConversion.md，Modes of Conversion）：“A partial conversion will legalize as many operations to the target as possible, but will allow pre-existing operations that were **not explicitly marked as ‘illegal’** to remain unconverted.”；驱动器源码（mlir/lib/Transforms/Utils/DialectConversion.cpp，OperationConverter::convert）注释更明确：“Partial conversions allow conversions to fail iff the operation was **not explicitly marked as illegal**”，且代码路径是 `if (opLegalizer.isIllegal(op)) { … return failure(); }`。本教程的 ConversionTarget 恰恰把 mini/scf/memref/arith/func 五个方言“整个非法”（§2 步骤 2、§3.2、代码 ILLEGAL_DIALECTS），实验 A 又扣掉 C1 模式——同一配置在真实 MLIR 里跑 applyPartialConversion 会得到 "failed to legalize operation ‘scf.for’ that was explicitly marked illegal" 并整体 FAIL，得不到“partial：14/18 转换成功……整体 SUCCESS”。§3.3 的核心直觉“残留清单一字不差，语义完全相反”只在教学仿真的语义里成立，而 §5.1 诚实声明称“full/partial 语义……对照真实 MLIR 的文档与行为建模”，这个对应关系不成立。真实 MLIR 渐进式施工的做法是：目标只把“本次要转的 op”标非法，其余方言保持未标记（unknown）或显式合法——例如真实 convert-scf-to-cf Pass（mlir/lib/Conversion/SCFToControlFlow/SCFToControlFlow.cpp）只把 scf 的 7 个循环 op 标非法并 `target.markUnknownOpDynamicallyLegal([](Operation *) { return true; })`，然后用 applyPartialConversion，partial 之所以成功，靠的是“别的 op 合法”，不是“非法 op 也能留着”。另外，真实 MLIR 的 partial 转换也不产出“残留报告”（最多经 ConversionConfig::unlegalizedOps 收集未合法化 op），打报告是本教学仿真自有行为。
- **置信度**：高（官方文档与 DialectConversion.cpp 源码均已核对；教学仿真侧的数字已本机复现，问题仅在“与真实 MLIR 语义一致”这一层）

#### 2. “每个 memref 参数在调用约定上就是一个 56 字节的聚合值”与真实 MLIR 默认 ABI 相反：参数被展开成 7 个独立标量，不是按值聚合
- **原文**：“这决定了 D115 要实现的 ABI：每个 memref 参数在调用约定上就是一个 56 字节的聚合值（2×8B 指针＋8B 偏移＋2×8B sizes＋2×8B strides）”
- **依据**：真实 MLIR 默认（struct 调用约定）下，函数签名里的 memref **参数**会被展开成多个非聚合参数。mlir/lib/Conversion/LLVMCommon/TypeConverter.cpp 的 `structFuncArgTypeConverter` 注释：“In signatures, Memref descriptors are expanded into lists of non-aggregate values”，即 rank-2 memref 参数变成 7 个独立参数（allocated ptr、aligned ptr、offset、2×size、2×stride）；上游测试 mlir/test/Conversion/FuncToLLVM/func-memref.mlir 的 CHECK 逐参数核对：`func.func @check_arguments(%static: memref<10x20xf32>, …)` 转换后每个参数对应 `CHECK-COUNT-2: !llvm.ptr` ＋ `CHECK-COUNT-5: i64`。相反，memref **返回值**才按值返回完整结构体（同文件 @memref_index 的 CHECK：`-> !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>`）。也就是说：参数＝7 个标量（合计恰 56 字节），返回＝按值结构体。把“参数按值传 56 字节聚合”说成 D115 要实现的 ABI 与真实行为相反；final_lowering.py 中 emit_llvm_text 的注释“真实 MLIR 默认按值传描述符”、outputs/design-doc.md 决策 4、outputs/legality-checklist.md 类型表“按值传递，64 位目标上 56 字节”都重复了同一说法。
- **置信度**：高（TypeConverter.cpp 源码与 func-memref.mlir 的 CHECK 行均已核对；注：描述符本体五字段、顺序与静态 shape 也保留 sizes/strides 字段这一点与真实 MLIR 一致，本条只针对“参数按值传聚合”）

#### 3. 管道里写的是 convert-memref-to-llvm——该 pass 名在当前 MLIR 已不存在（现名 finalize-memref-to-llvm）
- **原文**：“（`convert-scf-to-cf` → `convert-arith-to-llvm` → `convert-memref-to-llvm` → `convert-cf-to-llvm` → `convert-func-to-llvm`）”
- **依据**：当前 LLVM main 的 mlir/include/mlir/Conversion/Passes.td 中，MemRefToLLVM 段只注册了 `Pass<"finalize-memref-to-llvm", "ModuleOp">`（FinalizeMemRefToLLVMConversionPass），整个文件没有任何 "convert-memref-to-llvm"；mlir/lib/Conversion/MemRefToLLVM/MemRefToLLVM.cpp 的入口同样是 GEN_PASS_DEF_FINALIZEMEMREFTOLLVMCONVERSIONPASS，其描述还提醒复杂 memref op 需先跑 `expand-strided-metadata`。当前 mlir-opt 传入 `--convert-memref-to-llvm` 会报“未注册该 pass”。该名字是 2022 年前后的旧名（更名为 finalize-memref-to-llvm；更名确切年份未逐版本核实）。README §3.2 与 final_lowering.py 文件头的“真实名称与顺序”因此部分失实。其余 5 个 pass 名（convert-scf-to-cf／convert-arith-to-llvm／convert-cf-to-llvm／convert-func-to-llvm／reconcile-unrealized-casts）均已核对存在。附带说明：上游测试的惯用顺序是 convert-func-to-llvm 排在 convert-cf-to-llvm 之前（如 func-memref.mlir 的 RUN 行），两种顺序都能工作，“顺序”本身并非唯一。
- **置信度**：高（当前 pass 注册情况已核对源码；更名年份为印象，未逐版本核实）

#### 4. 必做练习 1 的验证方法无法执行：解析器不认 memref.dealloc 行，且脚本根本不读 loop_ir.mlir
- **原文**：“（验证方法：在 `loop_ir.mlir` 副本的 `return` 前加一行 `memref.dealloc %c : memref<4x3xf32, strided<[3, 1]>>`，然后想想驱动器会怎么处置它——`PATTERN_FOR_KIND` 里没有它的映射，答案就在残留报告里；真想让它转换，就给它登记一个模式再跑对照。）”
- **依据**：按此方法实测（临时副本）：parse_source 对该行直接抛出 `ValueError: 无法解析的行：memref.dealloc %c : memref<4x3xf32, strided<[3, 1]>>`——教学解析器的 CONST/ALLOC/LOAD/STORE/BINOP/YIELD/RETURN/GENERIC 规则都不匹配无结果名的 `memref.dealloc` 行，得到的是解析崩溃而不是残留报告。且 final_lowering.py 的 main() 从不把 loop_ir.mlir 当输入：源 IR 每次由 make_source_ir(M,K,N) 重新生成，loop_ir.mlir 只被写出（输入参数是 --shape）；修改该副本文件不会影响任何一次运行的输出。概念层面的预期答案（记成残留）与 drive() 的实现一致，但“答案就在残留报告里”给出的验证路径走不通。
- **置信度**：高（已在临时副本实际运行验证，两处行为均已复现）

#### 5. P1 探针的作用位置被指到 M1 的 extractvalue，实际在 M3 的 insertvalue（emit_alloc）
- **原文**：“P1 探针就是改这里相邻的 `[4,0]/[4,1]` 的填充顺序”
- **依据**：源码中 P1 分支只存在于 emit_alloc（M3）：`strides = list(mt["strides"]); if self.probe == "P1": strides = strides[::-1]`，随后 7 次 insertvalue 按位置 [4,0]/[4,1] 把反转后的 strides 填进描述符；emit_mem_access（M1，即该句紧随展示的代码）里只有 P2 的分支（`ity = "index" if self.probe == "P2" else "i64"`），没有任何 P1 修改——M1 只按正常顺序 extractvalue [4,0]/[4,1] 读出“被填反的值”。README §5.2 末尾自己也写“探针 P1/P2/P3……各改一处——P1 反转 strides 填充”（填充发生在 M3），与本句“改这里”（指代刚展示的 M1 代码）相互矛盾；按本句指引去 emit_mem_access 里找探针的读者会找不到。
- **置信度**：中（“这里”的指代存在歧义，可辩解为“[4,0]/[4,1] 这两个字段”；但最自然的读法——指代紧邻的 M1 代码——与源码不符）

## 【存疑】

#### 1. “三种驱动模式（full／partial／greedy）”与现行（及 LLVM 14 时代）文档的三种模式不符
- **原文**：“MLIR 给了三种驱动模式（full／partial／greedy）”
- **依据**：现行官方文档（DialectConversion.md，Modes of Conversion）列出的三种转换模式是 Partial / Full / **Analysis**（入口 applyAnalysisConversion：“analyze which operations are legalizable … no actual rewrites are applied”）；LLVM 14.x 时代的同一文档同样只列 Partial / Full / Analysis，均无 “greedy”。贪心重写（applyPatternsAndFoldGreedily，旧名 applyPatternsGreedily）确实存在，但它是 PatternRewriter 层的通用贪心模式重写入口，不与 ConversionTarget／合法性配套，不算 DialectConversion 的驱动模式。教程的说法可能源自更早期（约 2020 年前后）的文档或头文件注释表述，我未能取到该年代文档核实，不确定是否曾有“full/partial/greedy 三模式”的官方措辞。
- **置信度**：中（“现行与 14.x 文档中第三种是 analysis 而非 greedy”置信度高——两版均已核对；“旧版本曾如此表述”未核实）

## 【建议】

#### 1. “步数”的计数口径与文字描述不一致：211/51/87 是基本块执行次数，不是“逐 op”步数
- **原文**：“numpy 逐 op 仿真走 211 步、llvmlite MCJIT 编译后一次调用”
- **依据**：run_tir 的 `steps` 在每次进入一个基本块时自增 1（while 循环顶部），并非逐 op 计数。4×6×3 的 211＝k_body 72＋k_hdr 84＋k_done 12＋j_hdr 16＋j_body 12＋j_done 4＋i_hdr 5＋i_body 4＋entry 1＋i_done 1；若真按 op 计数，仅 k_body 的约 24 条 op × 72 次执行就超过 1700。练习 2 的提示“步数 ≈ 10×(M×N×K) 量级再加每层循环的固定开销”（原文见该行）与之口径也不符：实测 `--shape 3 4 2` 为 87 步（≈2×M×N×K＋低阶项），按提示模型算 240，相差近 3 倍，且偏差方向是“系数错了”而非“缺一项”，学生按“把它找出来”的提示会往补项方向找。建议在正文或图注中说明“步数＝基本块执行次数（≈2×M×N×K＋各层循环固定开销）”。
- **置信度**：高（两种口径的数字均已实测核对）

#### 2. “llvmlite 22.1.0”的版本号标注不准确（llvmlite 是 0.50.0，22.1.0 是其内嵌 LLVM 版本）
- **原文**：“（llvmlite 22.1.0 JIT 执行 GEMM 与参考逐位一致）”
- **依据**：本机实测 llvmlite 的版本号为 0.50.0（llvm_version_info＝(22, 1, 0)），README 前置准备、报告头、图 3 环境行也都正确写成“llvmlite 0.50.0（LLVM 22.1.0）”；“llvmlite 22.1.0”这一版本并不存在。images/01-overview.svg 中同样写了“llvmlite 22.1.0：parse+verify+MCJIT”。建议统一为“llvmlite 0.50.0（LLVM 22.1.0）”。
- **置信度**：高

#### 3. 模式条数口径不一致：README 说“9 条”，图 1 与 outputs/design-doc.md 说“10 条”
- **原文**：“9 条 Pattern（F1／R1／A1~A3／C1／M1~M3）列清每类源 op 的目标 op 序列”
- **依据**：枚举 F1、R1、A1~A3（4 条）、C1、M1~M3（3 条）＝9 条，与代码 PATTERNS 中的 9 条实现模式一致（另加 mini.*／vector.* 两行“无模式”拒绝行，共 11 行）。但 images/01-overview.svg 的产出卡片写“10 条模式 F1/R1/A1~A3/C1/M1~M3”，outputs/design-doc.md 也写“共 10 条”——同一份清单在图和设计文档里被数成 10，读者对照会困惑。不影响概念正确性；建议统一为 9（或写明“9 条模式＋2 行拒绝行”）。
- **置信度**：高（逐条清点核对）

#### 4. gen_images.py 与冻结的 01-overview.svg 不同步：重跑会改动冻结图的一处文字
- **原文**：“生成 3 张图（固定随机种子）”
- **依据**：用固定种子在临时目录重跑 gen_images.py：02-mechanism.svg、03-example.svg 与仓库冻结文件逐字节一致；01-overview.svg 有一处标签不同——脚本现在生成“D12~D84 建成＋优化 ✓”，冻结图是“D12~D84 图优化 ✓”，说明脚本在图冻结之后被改过一行。按 README 的“一键复现”思路重跑该脚本会覆盖冻结图并改变这处文字。建议把脚本与冻结图改回一致（本报告未改动任何文件）。
- **置信度**：高（diff 已核对）
