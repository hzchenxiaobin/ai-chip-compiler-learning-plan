# 第 116 天技术校对报告

审阅范围：README.md、code/（op_lowering.py、add/relu/step/gemm_ir.mlir、run_all.sh、gen_images.py）、outputs/ 全部冻结产物、images/ 三张 SVG。核实方式：在临时目录完整复跑 `./run_all.sh`（复现 9/9 PASS＋10/10 PASS，全部产物与冻结文件逐字节一致，仅报告时间戳不同，实测 1.3 秒）；对 P1 双坐标/双射、142 op 分解、`arith.subf` 未登记行为、numpy NaN/-0.0 语义等做了独立数值实验；对涉及真实 MLIR/LLVM 行为的论断查证了 llvm-project 当前 main 的源码与官方文档（LLVMOps.td、LLVMTypeConverter、FuncToLLVM.cpp、Dialects/LLVM.md），对 LLVM 报错信息用本机 llvmlite 0.50.0（LLVM 22.1.0）实际触发核对；D114/D115 的交叉引用（工单 10 条、胶水 8 条、实验 A 14/18、gcc x8 证据、TP8）逐项对账。以下意见只写入本报告，不改动教程原文、代码或冻结输出。

## 【错误】

#### 1. “`addf/mulf` 是 MLIR LLVM 方言的印刷名”不成立——真实 LLVM 方言的操作是 llvm.fadd/llvm.fmul，与 LLVM IR 指令同名；addf/mulf 是 arith 方言的名字
- **原文**：“两处词汇表/语法错位——`addf/mulf` 是 MLIR LLVM 方言的印刷名，LLVM IR 的指令叫 `fadd/fmul`”
- **依据**：MLIR 官方文档 Dialects/LLVM 的操作列表明确为 llvm.fadd（LLVM::FAddOp）、llvm.fmul（LLVM::FMulOp），并写明设计规则“*The mnemonic of an operation is that used in LLVM IR prefixed with 'llvm.'*”；llvm-project main 的 mlir/include/mlir/Dialect/LLVMIR/LLVMOps.td 第 245/247 行为 `def LLVM_FAddOp : LLVM_FloatArithmeticOp<"fadd", "FAdd">;`、`def LLVM_FMulOp : LLVM_FloatArithmeticOp<"fmul", "FMul">;`，全文件不存在 addf/mulf 助记符。`addf/mulf` 是 **arith 方言**（arith.addf/arith.mulf）的名字。D114 自己的 PATTERNS（final_lowering.py 的 A3 行）写的也是“llvm.fmul / llvm.fadd”。受影响处：§3.2“注意方言印刷名是 `llvm.addf`”（与 §6 第 4 条同一处错）、op_lowering.py PATTERNS 的 A3 doc、图 2 右中栏“A3  arith.addf/mulf : f32  → llvm.addf/mulf”、add-target.mlir 里 4 行 `llvm.addf`。需要说明：本机无 MLIR，教学仿真自造 `llvm.addf` 印刷名本身可以视为“印刷约定”，错的是把它断言为真实 MLIR 的名字并据此讲“两个词汇表”——对浮点指令这个对比不成立（llvm.fadd 与 LLVM IR 的 fadd 同名，真正的词汇差异发生在 arith.addf → llvm.fadd 这一步）。
- **置信度**：高——官方文档与上游源码双重核实（2026-11 查证 main 分支；该命名多年稳定）。

#### 2. “`bl add` 之前包装用 3 条 stp/str 把入参复制上栈”——3 条里有 1 条是保存 LR/x19 的函数序言，真正复制入参的只有 2 条，且只有 48B 上栈
- **原文**：“实测（`outputs/ciface-disasm.s`，aarch64）`bl add` 之前包装用 3 条 stp/str 把入参复制上栈”
- **依据**：ciface-disasm.s 的 `_mlir_ciface_add` 中 `bl add` 之前的 stp/str 共 3 条：`stp x30, x19, [sp, #48]` 是函数序言（保存返回地址 LR 和被调用者保存寄存器 x19，与入参无关）；`stp q0, q1, [sp]` 和 `stp x10, x11, [sp, #32]` 这 2 条才复制参数数据，合计 48B＝b 描述符的 aligned/offset/sizes×2/strides×2 六个 8 字节块。其余 8 个 8 字节块（a 的 7 个字段＋b 的 allocated）经 ldp/ldr/mov 装入 x0..x7，根本不上栈。disasm_evidence() 的计数用 `t.startswith(("stp","str"))` 过滤，把序言 push 一并计成“入参复制”。受影响处：§5.3 引用的冻结报告行“3 条 stp/str 把按值入参复制上栈/寄存器”、图 2（“bl add 前用 3 条 stp/str 把 2×56B 入参复制上栈”）、图 3（“bl add 之前：3 条 stp/str 把按值入参复制上栈”）。句末“2×56B＝14 个 8 字节，8 个可用寄存器装不下”本身成立（所以 6 块才上栈），但“3 条……把入参复制上栈”与汇编事实不符。
- **置信度**：高——逐条核对 ciface-disasm.s（本机复跑产物与冻结文件逐字节一致）。

#### 3. “27 条指令”是行数不是指令数——其中 4 行是 .cfi 伪指令，真实指令 23 条
- **原文**：“汇编证据（真机 aarch64，27 条指令）：`bl add` 前用 3 条 stp/str 把按值入参复制上栈/寄存器”
- **依据**：统计 ciface-disasm.s 的 `_mlir_ciface_add` 函数体（从函数标签到 .cfi_endproc）共 27 行，其中 `.cfi_startproc`、`.cfi_def_cfa_offset 64`、`.cfi_offset w19, -8`、`.cfi_offset w30, -16` 四行是 CFI 伪指令（unwind 元数据，不生成机器指令），实际 aarch64 指令 23 条。disasm_evidence() 用 len(body) 计数把伪指令也计入。图 3 同样写“_mlir_ciface_add 共 27 条指令”。
- **置信度**：高——逐行核对汇编文件。

#### 4. “142 op”的分项加总为 147——M3 的 15 条里含 6 条常量，与“常量 8 条”重复计数
- **原文**：“（8 load＋4 store 各带 10 条序列、M3 15 条、A3 4 条、常量 8 条）”
- **依据**：临时目录复跑 Emitter 实测：@add 2×2 目标 142 op＝12 条访存×10＋M3 15＋A3 4＋return 1；其中 M3 的 15 条＝6 条常量（字节数 16、offset 0、sizes 2/2、strides 2/1）＋malloc＋undef＋7 次 insertvalue，而“常量 8 条”＝2 条下标常量＋M3 的这 6 条。按引文分项求和 12×10＋15＋4＋8＝147≠142（M3 的 6 条常量被数了两次，return 1 条又未列出）；正确分解是 120＋M3 非常量 9 条＋4＋8＋1＝142。总数 142 与冻结报告一致，错的只是括号内的分解账。
- **置信度**：高——程序化复算（Counter 分类：const 8、call 1、undef 1、insert 7、extract 48、ibin 48、gep 12、load 8、store 4、fbin 4、ret 1）。

#### 5. “ctypes（libffi 实现 C ABI）只认指针和标量”为假——ctypes/libffi 可以按值传聚合，D115 的 TP8（本教程自己引用的证据）就是这么调的
- **原文**：“ctypes（libffi 实现 C ABI）只认指针和标量，所以包装签名是三个 `ptr`”
- **依据**：libffi 的调用规约实现平台 C ABI 的聚合参数规则，ctypes 的 CFUNCTYPE 完全接受 Structure 按值传参。D115 的 TP8——§3.4 自己引用为“byval/直接聚合配 ctypes 全部读错地方”——正是用 `ctypes.CFUNCTYPE(ctypes.c_int64, Desc)` 按值传 56B 描述符成功调用了 getoff_byval/getoff_agg（func_lowering.py 第 780~781、787~788 行），调用发生了、只是读到错值。所以“只认指针和标量”与被自己引用的实验矛盾；包装用三指针的真正原因是函数本体走 LLVM 字面结构体拆分约定（x0..x7＋栈），与 libffi 实现的 C ABI 聚合规则不一致——指针签名是两种合同里唯一无歧义的交集。图 2 右下“C 边界只信指针和标量”同错。
- **置信度**：高——D115 源码与冻结报告为直接证据。

#### 6. 图 1 SVG 写“D114 写下 10 行”，与正文“D114 写下 9 行……并新增第 10 行（A4）”直接矛盾
- **原文**：“D114 写下 9 行，D115 实现 3 行（F1/R1/A1），今天再实现 5 行（M1/M2/M3/A2/A3）并新增第 10 行（A4，cmpf/select——Relu 进管道时清单暴露的第一个缺口）”
- **依据**：images/01-overview.svg 的中排标题写“模式清单施工进度：D114 写下 10 行，今天再点亮 5 行并新增 A4”——若 D114 已写 10 行，A4 就无从“新增”，与引文及 §5.2“D114 的 9 行＋今天新增 A4”自相矛盾。D114 的 PATTERNS（final_lowering.py）确为 9 个模式行（F1/R1/A1/A2/A3/C1/M1/M2/M3），mini.*/vector.* 是无模式号的补充行。SVG 画 10 个格子本身没错（9＋A4），错在“D114 写下 10 行”这个数字。
- **置信度**：高——SVG 与正文、D114 源码三方对照。

#### 7. 图 2 SVG 的 A2 行注“index 位宽＝指针宽度”——真实 MLIR 的 index 位宽来自 DataLayout/dlti，与指针宽度是两个独立来源
- **原文**：“右边是词汇映射三行（A2/A3/A4）和 A4 的来源（Relu 带来的清单第 10 行）”
- **依据**：图 2 右中栏第一行写“A2  arith.addi/muli : index → add/mul i64（index 位宽＝指针宽度）”，op_lowering.py 第 195/971 行注释与冻结报告 TP6 行（“index 位宽就是目标指针宽度”）同源。llvm-project main 的 LLVMTypeConverter::getIndexType() 返回 IntegerType::get(ctx, getIndexTypeBitwidth())，位宽来自 LowerToLLVMOptions::indexBitwidth（由 DataLayout/dlti 推导或显式覆盖）；指针宽度是另一个独立函数 getPointerBitwidth()（options.dataLayout.getPointerSizeInBits）——两者在 64 位目标上恰好都是 64，但机制上并无派生关系。D115 的技术校对报告第 2 条已把同一说法列为机制归因错误，本天的 SVG/代码/报告又复现了它。正文 README 本身没有这句话，需要修的是 SVG 标签与代码注释。
- **置信度**：高——上游源码核实；数值层面（64 位目标上 index＝64）无争议，错的只是“＝指针宽度”的机制表述。

#### 8. 诚实声明把“LLVM 方言文本”也说成“由真 LLVM parse＋verify”——方言文本从未（也无法）交给 LLVM 解析
- **原文**：“发射的 LLVM 方言文本与 LLVM IR 文本由**真 LLVM 22.1.0** parse＋verify”
- **依据**：代码只对导出的 .ll 调 lv.parse_assembly（tp3_translate）；LLVM 方言文本走的是自制正则静态检查 check_dialect（TP2 日志自称“目标图静态检查（LLVM 方言文本）”）。且 `llvm.func @add(%a: !llvm.struct<...>)` 是 MLIR 语法，LLVM 的解析器不认——用本机 llvmlite 试 parse 方言文本必然报错。本文“前置准备”和 op_lowering.py 文件头的正确表述都是“发射出的 LLVM IR 文本交给真 LLVM parse、verify”，唯独这句把方言文本一并算进“真 LLVM parse＋verify”。若按“从方言文本到 IR 文本的产出链”宽读尚可自圆，但字面读法（A 与 B 都被 parse+verify）与实际行为不符——出现在诚实声明里，宜改精确。
- **置信度**：中——字面读法明确为假（代码行为可查）；存在“链条式”宽读的可能，但与同文另外两处的表述不一致。

## 【存疑】

#### 1. “调用双方由同一个后端编译”作为内部合同安全的前提——既不必要也不充分，真正的条件是“同一套 IR 级签名/聚合拆分规则”
- **原文**：“技术上这依赖一个前提——**调用双方由同一个后端编译**”
- **依据**：今天的汇编证明：字面结构体签名（%desc）在 LLVM 后端被拆成 x0..x7＋栈的标量块（返回拆 x0..x6），而 gcc 为 C 源的 >16B 聚合按 AAPCS64 发 sret（返回走 x8，D115 证据）——两边都由“LLVM 系”编译时形态仍可能不同：clang 前端会先把 C 聚合降级成 sret/byval 的 IR 形态，改的是 IR 签名的形状，不是后端。决定机器形态的是“IR 签名长什么样（字面聚合 vs byval 指针 vs 展开标量列）”，“后端是否同一个”只是伴随条件——同后端＋不同签名形态照样不一致（这正是“两份合同”的成因）。对本教程场景（同一模块、同一后端、同一签名形态）结论不受影响，但作为一般性前提过于绝对，宜表述为“调用双方使用同一份 IR 级签名（同一套聚合拆分规则）”。
- **置信度**：中——今天与 gcc 两份汇编是实测证据；“clang sret vs 手写 IR 字面聚合同为 LLVM 后端却形态不同”的构造型反例未在本机复现，由 D115 的 gcc/clang 侧证据与 AAPCS64 规则推断。

## 【建议】

#### 1. “见常见错误 3”指向错误坑位；代码注释“见常见错误 4”同理错位；两处“4 个坑”的枚举集合也不一致
- **原文**：“（A3，注意方言印刷名是 `llvm.addf`，LLVM IR 指令名是 `fadd`——两个词汇表，见常见错误 3）”
- **依据**：§6 四条依次是 ①np.maximum ②P1 三层 ③%desc 与字面 struct ④addf/fadd＋noinline——引文说的 addf/fadd 应引“常见错误 4”；op_lowering.py 第 557 行注释“（见常见错误 4）”指向的 struct 问题按 §6 顺序是第 3 条，两处恰好互换。另外“今日目标”枚举的 4 坑（np.maximum、命名结构体、方言名、函数属性）与 §6/§8 的 4 条（含“三层验证缺一不可”、合并“方言名＋函数属性”）集合不一致。纯交叉引用问题，不影响技术内容。
- **置信度**：高

#### 2. 冻结报告里 @relu 段落缺“[TP5]”标题行，§5.4 引用“TP5 的点数”在报告里按标签定位不到
- **原文**：“类型文本（strides [3,1]）、TP5 的点数（4/4→6/6）”
- **依据**：op-report.txt / op-report-s23.txt 中 @relu 的两层验证数字以缩进形式直接出现在 TP4 汇编证据之后，没有 [TP5] 头（tp5_relu 未 log 标题行，TP1~TP9 其余各项都有），汇总行却列“TP5: PASS”。数字本身（2×2 主输入/边界输入 4/4、2×3 为 6/6）与冻结报告一致，只是标签缺失使 §5.4 的引用无法按图索骥。
- **置信度**：高

#### 3. §5.2 的 _emit_mem 片段省略了 rank/stem 的定义行，照抄不可运行
- **原文**：“def _emit_mem(self, res, mem, idx, mty, is_store, val=None):”
- **依据**：引文的下一行就是 `dty = desc_type_text(rank)`，而源文件（op_lowering.py 第 434~437 行）在此之前还有 `rank = parse_memref(mty)["rank"]` 与 `stem = (res or f"{val}_dst")[1:]` 两行；片段里的 `%{stem}_al` 等也依赖 stem。作为节选可以接受，但缺省略号标记，初学者照抄会 NameError。
- **置信度**：高

#### 4. “M3 共 15 条（字节常量＋malloc＋undef＋7 次 insertvalue）”——实际是 6 条常量，按加法读会得 10≠15
- **原文**：“M3 共 15 条（字节常量＋malloc＋undef＋7 次 insertvalue）”
- **依据**：实测 M3 发射 15 op＝6 条常量（16/0/2/2/2/1）＋malloc＋undef＋7 次 insertvalue；“字节常量”（单数）只点名了字节数那一条，严格求和 1＋1＋1＋7＝10。图 2 的 M3 面板把 7 次 insertvalue 填的字段值都画了出来（值正来自那 6 条常量），括号宜写“6 条常量（字节数/offset/sizes×2/strides×2）”。
- **置信度**：高

#### 5. 练习 1 提示“没登记的 op 在账本里是什么下场”隐含答案是“进残账”——实际是被 census 静默忽略、账本假 SUCCESS
- **原文**：“（提示：`OP_KINDS` 里 `arith\.(addf|mulf)` 这一行能匹配 `arith.subf` 吗？没登记的 op 在账本里是什么下场）”
- **依据**：临时目录实测：把 @add 的 addf 换成 subf 后，OP_KINDS 的 14 个正则无一命中 subf 行（census 的匹配循环没有 else 分支，未命中行不进 ops），账本报 17/17、残账 0、full SUCCESS——比“进残账”更危险的是“根本不在账上”；错误要到 Emitter 才以“无法解析的源行：%s00 = arith.subf %a00, %b00 : f32”暴露。只有显式登记 pattern=None 的 mini.* 才进残账。练习不妨把这条真实行为写明（“不在账上、账本假 SUCCESS”恰是更深刻的一课：未登记 op 绕过了两道闸的账本层）。
- **置信度**：高——已运行验证。

#### 6. “（NaN 与 0 比较返回 NaN）”措辞不准——np.maximum 是取大运算，NaN 传播的机制是“任一操作数为 NaN 则结果为 NaN”
- **原文**：“numpy 的 `maximum` 传播 NaN（NaN 与 0 比较返回 NaN）”
- **依据**：np.maximum 不执行“比较并返回 NaN”的动作——按 numpy 文档，任一输入为 NaN 时输出即为 NaN（NaN propagates）。括注容易让读者误以为存在一条“比较返回 NaN”的规则。正文的结论本身正确（maximum 在 NaN 上返回 NaN、where 版才与 cmpf+select 逐位对齐），仅括注措辞问题。
- **置信度**：高
