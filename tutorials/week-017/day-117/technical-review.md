# 第 117 天技术校对报告

校对方法：在与冻结输出同构的环境上完整复跑（aarch64 Linux、Ubuntu LLVM 18.1.8 位于 `/usr/lib/llvm-18/bin`、Python 3.11.4、llvmlite 0.50.0/LLVM 22.1.0）。`./lower.sh` 对 gemm.mlir/gemm_tight.mlir 的全部 12 个产物与冻结文件**逐字节一致**；四个 `errors-*.txt` 用 run_all.sh TP10 的原命令复现，stderr 逐字节一致；`census.py` 各计数、`grep` 各口径（62 SSA/4 phi/1 fmul/18 fmul/18 fadd/67 数字名 SSA/119 全部赋值）逐一复核；对 pass 链做了逐站分跑与乱序实验；存疑点查了 MLIR 18.1.8 官方源码（FuncToLLVM.cpp、IndexToLLVM.cpp、ReconcileUnrealizedCasts.cpp）。以下所有行号均指仓库内冻结文件。

## 【错误】

#### 1. §3.2 struct→memref 胶水的机制叙述与实际 IR 不符（load/store 早已不是 memref 类型，cast 也没有在"缝合"任何东西）
- **原文**："但函数体里的 memref.load/store 还认 memref 类型，于是 cast 缝合"
- **依据**：lower.sh 的顺序是 `--finalize-memref-to-llvm` 在 `--convert-func-to-llvm` **之前**；逐站分跑证实第 2 站之后所有 load/store 已是 `llvm.load/llvm.extractvalue/llvm.getelementptr`，到 func 转换时函数体里已没有任何 `memref.load/store`（`gemm-2-llvm-dialect-noreconcile.mlir` 的 census 里 memref.* 为 0）。3 条 struct→memref cast（%8/%17/%41，第 12/21/45 行）在文件里各只出现一次（定义处），**没有任何使用者**——不是"缝合"，是残留。真实过程：finalize-memref 为 load 物化 memref→struct cast；func-to-llvm 转签名时物化反向 struct→memref cast，两者成对；`--convert-index-to-llvm` 折掉 cast 链后这些 cast 成为无使用者的死代码，最后由 reconcile 删除。教程引用的行号、条数、两族类型本身全部正确，错在"还认 memref 类型／缝合"这句因果。
- **置信度**：高（冻结文件直接可查：grep 三个 %值各仅一处出现；分步复跑可重放全过程）。

#### 2. §3.2 i64→index 胶水的机制叙述与实际 IR 不符（最终文件中归纳变量的消费者全是 i64 运算，cast 无使用者）
- **原文**："index→i64 转换先动了类型，三个循环头上的归纳变量还是 index 消费者，cast 顶上"
- **依据**：在它所描述的 `gemm-2-llvm-dialect-noreconcile.mlir` 里，3 条 i64→index cast（%43/%46/%50，第 48/54/60 行）各只出现一次（定义处）、无使用者；循环头归纳变量（%48/%45/%42）实际直接喂给 `llvm.icmp`/`llvm.add`（i64）。逐站分跑显示这族 cast 诞生在第 3 站（func-to-llvm 把块参数 index→i64 时物化），其使用者只是上一站 finalize-memref 物化的 index→i64 cast（喂地址计算），随后被 index 站折掉——"归纳变量还是 index 消费者、cast 顶上"在本管道的任何阶段都不成立。
- **置信度**：高（同上，文件与分步复跑双重证据）。

#### 3. §6 错误 4 的原因写"签名里的 index 已经换成 i64"——函数签名里根本没有 index
- **原文**："func 先转，签名里的 index 已经换成 i64"
- **依据**：gemm.mlir 第 10~11 行签名为 `(memref<4x6xf32, strided<[6, 1]>>, memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32>`，全签名无 index 类型。errors-4 报错对象是 `%lb = arith.subi %c6, %c6 : index`（第 18 行，循环下界，函数体内值）。仅跑 `--convert-func-to-llvm` 的中间文件显示：该站把函数体内的 arith 常量/运算换成了 i64，而 scf.for 的边界/归纳变量仍是 index，这才物化 i64→index cast——错位发生在"函数体的值 vs 循环边界"，与签名无关。
- **置信度**：高（签名逐字可查；仅跑第一站的中间文件已复现 cast 的真实来源）。

#### 4. §6 错误 4"中途已翻车"不成立——六个转换站全部成功，报错的正是最后一站 reconcile 自己
- **原文**："没人（reconcile 在最后，但中途已翻车）能救"
- **依据**：按 errors-4 的七条 pass 对 gemm.mlir 逐站分跑：func→memref→scf→cf→arith→index 六站**全部成功**（cast 数依次 9→13→13→13→19→18），第七站 `--reconcile-unrealized-casts` 报错，错误文本与冻结的 errors-4-order.txt 逐字节一致。MLIR 18 的 ReconcileUnrealizedCasts.cpp 中 `target.addIllegalOp<UnrealizedConversionCastOp>()`——报错里的"explicitly marked illegal"正是 reconcile 自己的判定：它遇到无法折叠成 no-op 的**活跃** cast（本例是喂给循环的 i64→index）才失败。所以不是"reconcile 救不了中途的翻车"，而是"reconcile 是报错者"。§7 选做挑战的提示"（提示：翻车发生在中途的哪个 pass 里）"（§7 原文）会引导读者寻找一个不存在的中途翻车站。errors-1 同理：分跑到第七站 reconcile 才报错。§3.1 的"胶水卡在中途没人清"同属此误。
- **置信度**：高（逐站复跑 + 源码双重验证）。

#### 5. `_mlir_ciface_gemm` 包装的生成者是 `--convert-func-to-llvm`，不是 mlir-translate
- **原文**："mlir-translate 把纯 LLVM 方言变成 .ll 并顺手生成 `_mlir_ciface_gemm` 包装"
- **依据**：冻结的 `gemm-2-llvm-dialect.mlir` 第 86 行已含完整的 `llvm.func @_mlir_ciface_gemm(...)` 函数体（noreconcile 版第 95 行同样有）——它在 mlir-translate 运行**之前**就已存在于 LLVM 方言 IR 里。仅跑 `--convert-func-to-llvm` 的中间文件里该包装即已生成。MLIR 18.1.8 FuncToLLVM.cpp 的 `FuncOpConversion` 在函数带 `llvm.emit_c_interface` 时调用 `wrapForExternalCallers` 生成 `_mlir_ciface_<name>`；mlir-translate 只负责把这个既有的 llvm.func 翻译成 .ll 里的 define。§3.3 的"让 mlir-translate 自动生成 `_mlir_ciface_gemm` 包装（D116 手写包装的真工具版）"（§3.3 原文）与图 2 图注/SVG（"llvm.emit_c_interface 让 mlir-translate 自动生成 define void @_mlir_ciface_gemm..."）方向都反了。
- **置信度**：高（冻结文件 + 分步复跑 + 官方源码三重验证）。

#### 6. "O2 后 SSA 62→67"的计数口径失真：gemm-O2.ll 实际有 119 条 SSA 赋值
- **原文**："opt -O2 之后 SSA 62→67、fmul 1→18（LLVM 展开循环）"
- **依据**：`grep -cE "^\s+%[A-Za-z0-9._]+ =" gemm-O2.ll` 得 **119** 条赋值；"67"来自 run_all.sh TP8 的 `grep -cE "^\s+%[0-9]+ ="`——只匹配数字名 `%N`。gemm-3.ll 全部是数字名（两种口径同为 62），而 opt -O2 把大多数值改成了 `%gep.2.phi.trans.insert`/`%.pre` 之类的命名值，52 条不被该模式计数。"指令变多"的方向正确，但 62 与 67 不是同一把尺子：62 是真总数，67 是漏数后的值。§5.4 实验 3 要求学生预测"SSA 总数"，按文件实际清点会得到 119 而不是 67；图 4（原图 3，因新增 reconcile 对照图顺延）的"SSA 62 → 67 条"同源。fmul 1→18、fadd 1→18、phi 4→1 均复核无误。
- **置信度**：高（计数可直接复现）。说明：若作者本意就是"数字名 SSA 指令数"，需在正文明确口径；按通常理解"SSA 指令数"，67 是错的。

#### 7. 图 2（images/02-mechanism.svg）把 phi 对的行号写成"第 46~47 行"，与真实输出和正文都不一致
- **原文**："导出后（gemm-3.ll 第 48~49 行原文）"
- **依据**：README 正文两处（§4 图 2 图注、§5.3 组 3）都写 48~49，且 `grep -n "phi" gemm-3.ll` 确认 `%46 = phi i64`、`%47 = phi float` 位于第 48、49 行；但 SVG（及生成它的 code/gen_images.py 第 246 行）写的是"gemm-3.ll 第 46~47 行"——第 46~47 行实际是空行与块标签行。图、正文、真实输出三方冲突，应统一为 48~49。
- **置信度**：高（三方对照即可判定）。

## 【存疑】

#### 1. "scf→cf 在转换链最前"作为硬约束过于绝对（实证：memref 打头结果逐字节一致）
- **原文**："**`--convert-scf-to-cf` 在转换链最前**（先把结构化循环拆成 cf 块，块参数直接变成后面的 phi 前身）"
- **依据**：把阶段 2 的顺序换成 `--finalize-memref-to-llvm` 打头（scf 第二）、其余不动，最终 `gemm-2-llvm-dialect.mlir` 与冻结产物**逐字节一致**（diff 为空）。教程实际只实测过 func 打头（errors-4）会失败；"最前"是稳妥的推荐写法，但"顺序本身就是合同／错一步中途翻车"（§3.1）对这一条并不成立。括号里"块参数直接变成 phi 前身"的说法本身正确。
- **置信度**：高（乱序实验复现）。判定为存疑而非错误：推荐顺序本身无害，只是"约束"的强度与证据不匹配。

#### 2. "finalize-memref-to-llvm 在 convert-func-to-llvm 之前"同样不是硬约束，且括号里的理由不成立
- **原文**："**`--finalize-memref-to-llvm` 在 `--convert-func-to-llvm` 之前**（memref 类型先换掉，func 转签名时才不需要为它造胶水）"
- **依据**：顺序换成 scf→**func→memref**→cf→arith→index→reconcile（func 在 memref 之前），产物同样**逐字节一致**。理由也不对：func 先跑照样造胶水——仅跑 func-to-llvm 的中间文件里已有 8 条 cast（含为 memref 参数物化的 struct↔memref 对），只是这些 cast 能被后续折叠/清算。真正实测会翻车的是 func 排在 **scf** 之前（errors-4）；"memref 先换掉才不需要造胶水"把"造出的胶水可折叠"误说成"不造胶水"。
- **置信度**：高（乱序实验 + 中间文件 cast 计数）。

#### 3. "七条各管一层／每条 pass 接管一层"与本管道实测分工不符：cf、arith 两条 pass 是空转，func 一站干了三层
- **原文**："是七条各管一层的 pass 按依赖关系排成的流水线"
- **依据**：逐站分跑（同输入 gemm-0-optimized.mlir）：第 3 站 `--convert-func-to-llvm` 之后 cf.br/arith 已全部变成 `llvm.br/llvm.*`（108 op、非 llvm 残账 0），第 4、5 站 `--convert-cf-to-llvm`、`--convert-arith-to-llvm` 的输出与第 3 站**完全相同**（空转）。MLIR 18.1.8 的 FuncToLLVM.cpp 显式加入了 arith 与 cf 的转换模式，源码注释即 TODO llvm#70982"Remove these in favor of their dedicated conversion passes"。图 1 下排的"convert-arith-to-llvm←A2/A3"等接管映射、§5.1 引用的注释清单都暗示五条 pass 各干各的活，与实测不符（干活的还有 3 条 pass 时结果已经纯 LLVM 方言）。因该行为依 MLIR 版本而异（TODO 计划移除），列为存疑。
- **置信度**：高（逐站 diff + 官方源码）。不确定点：若换 MLIR 版本（func pass 不再附带 arith/cf 模式），分工叙述会重新成立。

## 【建议】

#### 1. lower.sh 注释与 README 引文中对 `--convert-index-to-llvm` 的描述与实测效果不符
- **原文**："index -> i64（清 i64<->index 胶水的前半）"
- **依据**：输入 IR 里没有任何 `index.*` 方言 op（该 pass 的职责是"Lower the `index` dialect to the `llvm` dialect"，对本输入无模式可配）。它的实际贡献是触发转换框架的 cast 链折叠：去掉它，中间态从 6 条变 11 条 cast；带着它折掉 5 条——其中 3 条是 i64↔index 对，**2 条是 struct↔memref 对**。"清 i64<->index 胶水"只对了 3/5，"index -> i64"对本输入没有对应物。建议改述为"参与折叠 index 相关 cast 链（实测 11→6）"。
- **置信度**：高（有/无该 pass 的对照实验）。

#### 2. "错误在发生的站暴露"的表述与冻结证据不符——报错的站都是最后一站
- **原文**："每一站的残账都能当场盘点（census.py），错误在发生的站暴露，而不是攒到最后"
- **依据**：单条 mlir-opt 命令里七个 pass 依次执行，errors-1 与 errors-4 的报错都由最后的 reconcile 打出（逐站分跑证实）；"发生的站"（finalize-memref 漏掉 strided alloc／func-to-llvm 造出活跃 cast）本身并不报错。真正兑现"当场暴露"的是 lower.sh 的分阶段落盘＋census（对中间文件点名 `memref.alloc x1` 残账，README §6 错误 2 的定位一节就是这么做的）。建议把主语从"错误"改成"残账"，与实测对齐。
- **置信度**：高。

#### 3. 图 2 ① 把 body 与 latch 画成两个块，实际输出里两者合并在同一块
- **原文**："body 块干活＋自增、latch 块把新值送回 header"
- **依据**：`gemm-1-scf-to-cf.mlir` 中 k 循环只有 ^bb4(init)/^bb5(header)/**^bb6(body＋自增＋回跳)**/^bb7(出口)——图里"latch（回跳）"框贴的 `cf.br ^bb5(%11, %10 : index, f32)` 其实是 ^bb6 的最后一行；j 循环同理（store＋addi＋回跳同在 ^bb7）。三个循环合计 9 块（§3.1 的"9 个带标签块"正确），"拆四块"是概念模型而非文件的块结构。建议在图注注明"body 与 latch 在实际输出里合并在同一块"，避免读者按图数块对不上 9。
- **置信度**：高（文件结构可查）。

#### 4. "从 cast 后的 struct 里取 aligned 指针"的措辞不准确
- **原文**："load 不再从 cast 后的 struct 里取 aligned 指针，直接用 `%arg1`/`%arg8`"
- **依据**：`%52 = llvm.extractvalue %7[1]` 读的 %7 是 7 次 insertvalue 打包出来的 struct 本身（它是 cast %8 的**操作数**，不是"cast 后"的产物）；reconcile 一步之内把它拉直成 `%arg1`，靠的是 extractvalue(insertvalue(...)) 折叠（对两份冻结文件跑 `--canonicalize` 也发生同样的 17→14 与 gep 操作数 %52→%arg1 变化，可佐证与 cast 删除无关的通用折叠）。数值结论（17→14、103→94、gep 从 %52 到 %arg1）全部复核无误，仅建议把"cast 后的 struct"改成"重建的描述符 struct"。
- **置信度**：中高（折叠机制由 canonicalize 对照实验佐证；"cast 后"也可解读为笔误式的模糊指代）。
