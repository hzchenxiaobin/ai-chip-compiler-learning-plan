# 第 122 天技术校对报告

> 审阅视角：AI 芯片编译器工程师（十年）。方法：通读 README、`code/`（minic.py / loop_lower.py / graph_passes.py / run_all.sh / main.graph / gen_images.py）、全部冻结产物（outputs/）与 3 张 SVG；在隔离临时目录（未触碰仓库冻结文件）用本机 LLVM 18.1.8（Linux aarch64，Python 3.11.4）完整重跑 `run_all.sh`，结果 25 PASS / 0 FAIL；对存疑论断另做了单项实验：反序 pass 管道、删 reconcile 后导出、`vector.reduce`/`vector.reduction` 对照、`--llvm-bin` 指空目录、E202 有无 `--dump-ir`。跨天引用核对了 D114/D115/D117/D118/D119/D121/D124 与 D85~D90。

## 【错误】

#### 1. 图 3 称 stage-5.ll 含“三重循环体”——三重 scf.for 在第一条 pass 就被删除，stage-5.ll/.s 里没有任何循环

- **原文**：“三重循环体（tile 壳＋点循环）”
- **依据**：冻结产物自证：`outputs/main/stage-4-03-canonicalize+csi.mlir`（第一条 pass 之后）只剩 `memref.alloc`＋`func.return`，三重 scf.for 全部消失（空循环体且无结果的 scf.for 是死代码，canonicalize 直接删除）；`stage-5.ll` 无任何分支或循环（只有 malloc＋8 条 insertvalue＋ret），`stage-5.s` 亦无循环结构。我用 LLVM 18.1.8 重跑同样如此。点循环是注释（5.1 诚实声明已交代），但“tile 壳”也没活过第一条 pass——图 3 把“三重循环体（tile 壳＋点循环）”列为 stage-5.ll 的解剖项是事实错误；03-example.svg 同样画着“三重循环体（scf→cf→llvm 落地）”。若本意是“stage-2-loop.mlir 有循环壳”，应改写指明是哪个文件。
- **置信度**：高（冻结文件直接可查，无需运行）。

#### 2. E204 成因被表述为“vector 残账被 pass 拒收”——实际是解析期就失败的过时算子名 `vector.reduce`，pass 根本没有执行

- **原文**：“vector.reduce 残账被 pass 拒收（D114 暂不支持清单第 4 条）”
- **依据**：`custom op 'vector.reduce' is unknown` 是 MLIR 解析器诊断——mlir-opt 读入文件即失败，任何 pass 逻辑都没有运行（pipeline-error.txt 里“失败的 pass：canonicalize+csi”只因为它是第一条命令）。根因是算子名过时：本机 LLVM 18.1.8 实测 `vector.reduce` 同样 unknown，而 `vector.reduction <add>, %v : vector<4xf32> into f32` 可正常解析（改名发生在 LLVM 18 之前，教程环境 23.1.5 报同一错误，冻结文本可证）。关键反例：把坏 IR 改成正确的 `vector.reduction` 后，八条 pass（含 reconcile）全部通过——这些 convert 是 partial conversion，不拒收 vector op——残账一路活到 mlir-translate 才报 `Dialect 'vector' not found for custom op 'vector.reduction'`，即走 E205 而非 E204。“被 pass 拒收”既错判了已存档的失败（解析错误），也错判了假想情形（真有 vector 残账时失败在 translate）。D114 清单第 4 条确为 vector.*（该引用本身无误）。
- **置信度**：高（LLVM 18 实测＋冻结文本判读；23.1.5 的行为由冻结输出直接佐证）。

#### 3. 图 1 目录树列出 stage-1-graph-opt.graph——该文件在主线上从不落盘（被 run_s45 的“陈旧清理”删掉）

- **原文**：“**中部**是 out/ 目录树：manifest.json（机器合同）＋stage-1-graph-opt.graph（S1 终图）＋stage-2-loop.mlir（S2 循环 IR）＋stage-4-03~10（八条 pass 逐条落盘）＋stage-5.ll/.s（LLVM IR＋汇编）”
- **依据**：冻结 `outputs/main/` 恰好 11 个 stage 文件、没有 stage-1-graph-opt.graph。机制：minic.py 在 S1 段写出该文件（仅 `--dump-ir` 时，minic.py 267~269 行），随后 run_s45 开头的清理把所有 `stage-*` 一律删除（loop_lower.py 179~184 行），刚写好的 S1 产物被当“陈旧文件”清掉；实测 `--tile 8,8,8 --dump-ir` 后目录同样无 stage-1。01-overview.svg 画了同样的树，且同一张图底部写“11 个 stage 文件”，与树上 12 个条目自相矛盾。这同时暴露一个真实代码缺陷：S1 的 dump 被自家清理毁掉，直接削弱 D123 可观测性地基（正文宣称的卖点）。
- **置信度**：高（冻结目录＋代码路径＋复现三重证据）。

#### 4. E202“图原样落盘”与图 2“stage-1 终图落盘（可复查）”不成立——存档的 t-e202 现场只有 manifest.json

- **原文**：“E202 S2 不支持算子：带节点 id＋支持集，图原样落盘”
- **依据**：图落盘受 `--dump-ir` 门控（minic.py 267 行），而 TP4 存档运行没带该参数（run_all.sh 62 行），冻结 `outputs/t-e202/` 只有 manifest.json、无任何图文件——该无条件声明被教程自己的现场反驳；02-mechanism.svg 的“现场：stage-1 终图落盘（可复查）”同理。实测带 `--dump-ir` 时 E202 路径确实保留 stage-1-graph-opt.graph（LowerError 在 run_s45 清理之前抛出），但正文与图把条件性行为写成了无条件承诺；loop_lower.py docstring 的“图原样落盘（可复查）”同样仅在该开关下成立。
- **置信度**：高。

#### 5. 练习 1 的 E205 复现方法（把 --llvm-bin 指向空目录）触发不了 E205

- **原文**：“E205（把 --llvm-bin 指向空目录）”
- **依据**：find_tool 的查找顺序是 llvm_bin → PATH → 硬编码常见位置（含 `/opt/homebrew/opt/llvm/bin`——恰是本教程 Homebrew LLVM 的安装位，以及 `/usr/lib/llvm-18/bin` 等，loop_lower.py 145~159 行）。实测 `minic main.graph --llvm-bin <空目录>` 退出码 0、全管道照常跑完（工具经回退路径找到）。E205 只在机器上任何位置都找不到 mlir-opt 时触发——而那种机器上本教程其余内容全都跑不动，练习无法完成。另外 E205 也用于 mlir-opt（S4 工具）缺失，与“E205 S5 工具失败”的分层语义不符。建议改为真实可触发的做法（例如临时注入指向不存在工具的绝对路径并屏蔽回退）。
- **置信度**：高（代码逻辑＋直接复现）。

#### 6. 错误 4 声称修复后 stages 序号单调——冻结 manifest 本身不单调（S2 落在 S3 后、胶水清点落在 S5 后）

- **原文**：“定位：读 manifest 的 stages 数组，序号应单调（S0→S1→S2→S3→S4×8→S5×2）。”
- **依据**：冻结 `outputs/main/manifest.json` 的 stages 实际为 S0→S1→S2（循环生成）→S3（Tiling）→S2（循环 IR 落盘）→S4×8→S5×2→S4（胶水清点）→S6：“S2 循环 IR 落盘”排在 S3 之后、“S4 胶水清点”排在 S5 之后，按本条自己给出的判据即不单调。原因是 minic 先记 S2/S3 概要日志、后调 run_s45 追加内部条目；时间线诚实，但与“真实执行段的追加顺序与阶段序号严格对齐”的修复声明矛盾。读者按本条方法核对会发现教程自身不过关。
- **置信度**：高（manifest 逐条可数）。

#### 7. §3.3 把约定顺序写成硬依赖“scf→cf 必须在 memref 转换前”——实测反序后全管道照样成功

- **原文**：“编译管道的 pass 之间有**数据依赖**（scf→cf 必须在 memref 转换前、reconcile 必须最后）”
- **依据**：在 LLVM 18.1.8 上把顺序换成 finalize-memref-to-llvm 先于 convert-scf-to-cf，分别在当天主线 stage-2-loop.mlir 与 D117 的 gemm.mlir（带真实 load/mulf/addf 循环体）上跑完其余全部 pass＋reconcile＋mlir-translate，全部成功。D117 真正被证实的硬约束是 errors-4 的“func 先于 scf/memref 会失败”；“scf→cf 最前”是 lower.sh 的书写惯例而非必须。把惯例表述成数据依赖会误导初学者对 conversion pass 合法性作用域的理解（每条 pass 只对自己的方言族负责——这正是第 2 条里 vector 残账能溜过全部 pass 的原因）。
- **置信度**：高（反例已实测复现；未在 23.1.5 上验证，但该结论取决于 pass 合法性机制，与 LLVM 小版本无关）。

#### 8. “S4 七 pass 管道”“七 pass 全过”与实际执行的 8 组 pass 矛盾（同文又写“八组/八条”）

- **原文**：“S3 tile 进步长→S4 七 pass 管道→S5 translate 出 .ll＋llc 出 .s”
- **依据**：PASSES 表共 8 条（canonicalize＋csi、scf→cf、5 条转换、reconcile，loop_lower.py 133~142 行），manifest 记录 8 条 pass（stage-4-03..10），README §2 自己写“八组 pass”、§3.3 写“八次调用”，run_all.sh 的 ok 消息却写“七 pass 全过”。若“七”沿用 D117 的“七条转换 pass”（不含 canonicalize＋cse）口径，本文从未定义；初学者数表会得到 8，同一篇内两种说法无解释并存。建议统一为 8，或明确写“1 条优化＋7 条转换/清胶水＝8 组”。
- **置信度**：高（计数可直接核对；“七”存在 D117 术语血统的辩护，但本文未定义）。

#### 9. minic 版本号：README 称 0.3.0，代码与冻结 manifest 均为 0.2.0（day-121）

- **原文**：“`code/minic.py`（0.3.0：S2~S5 接入＋E202/E204/E205 分层失败处理＋失败时 manifest 照常落盘）”
- **依据**：minic.py 29 行 `VERSION = "minic 0.2.0 (day-121: S1 graph passes)"`；冻结 outputs/main/manifest.json 与 outputs/t-e202/manifest.json 的 version 字段同为此值。0.3.0 只存在于 README（今日目标“把 minic 升级到 0.3.0”）与 01-overview.svg 标题——升级动作没有落到代码。配套陈旧痕迹：minic.py 模块 docstring 仍写“第 120 天核心脚本……今天只做「设计＋合同」”。
- **置信度**：高。

#### 10. 03-example.svg 的 stage-5.ll 解剖数字与正文及真实产物矛盾（14 个裸参数、3×7 字段、三指针）

- **原文**：“**右框**今天主线产物 stage-5.ll 的解剖：`define @main_kernel(...)` 19 个裸参数（a/b 各 7 字段＋bias rank1 的 5 字段——D115 ABI 的三份合同同时在场）”
- **依据**：03-example.svg 实际印着“14 个裸参数”“3 memref × 7 字段拆包（D115 ABI）”“sret 三指针包装（D116/117 合同）(ptr, ptr, ptr) C 合同：out, a, b(+bias)”。真实 stage-5.ll：@main_kernel 共 19 个参数（a/b 各 7、bias 是 rank1 只有 5 字段，7＋7＋5＝19——“3×7＝21”的口径本身也错）；`_mlir_ciface_main_kernel` 是四指针 `(ptr, ptr, ptr, ptr)`（out/a/b/bias，与正文 §5.3 引文及 .ll 一致）。三指针/14 参数疑似沿用 D117 gemm（3 个 memref、三指针）的旧数字、未随 bias 扩展更新。图与正文互相矛盾，读者对照 .ll 即可发现。
- **置信度**：高。

## 【存疑】

#### 1. “D85~D90 的循环任务单（bias 融 k=0 的语义出处）”——D85~D90 全部内容里查不到 bias 语义

- **原文**：“D85~D90 的循环任务单（bias 融 k=0 的语义出处）”
- **依据**：对 week-013（D85~D91）全部文件检索 “bias／偏置／fused” 均无命中；D85 的三张任务清单写的是累加器 iter_args “从常量 0.0 起步”，没有任何 bias 语义。bias 进累加初值的语义出处更接近计划 D050（定义 fused_matmul_bias_relu）与 D121 的融合合同（到 D124 才落地为 iter_args 初值）。若作者本意是“任务单定义了 iter_args 初值机制、bias 只是替换初值”，出处表述宜改准确；D124 前置准备重复了同一出处，建议一并核实。
- **置信度**：中（仓库内查无出处是事实；不排除作者另有所本，但本系列其他跨天引用均可在仓内核实）。

## 【建议】

#### 1. §5.3 引用的 report 与冻结文件有两处小出入（时间戳、引用位置）

- **原文**：“第 122 天：minic S2~S5 循环＋LLVM Lowering——真机报告 2026-11-14 21:35”
- **依据**：冻结 outputs/report.txt 首行是“2026-11-14 21:25”，正文引成 21:35；另外 §3.2 与 §5.3 ② 称引文是“pipeline-error.txt 首行”，实际它是 stderr 段的第一行（文件第 4 行，文件真正的首行是“失败的 pass：canonicalize+csi（--canonicalize --cse）”）。不影响技术结论，但既是“真机输出”引用宜逐字对齐。
- **置信度**：高。

#### 2. 两处小节交叉引用指错（“见 6.3”应为 6.1；“6.3 详述”应为 6.2）

- **原文**：“4. **陈旧清理**：二次运行前清旧 stage 文件——现场只属于本次（今天踩的真坑，见 6.3）；”
- **依据**：陈旧清理的真坑是 §6 错误 1（6.1），6.3 是 E202 套娃；§5.3 ③“有趣插曲（6.3 详述）”讲假毒测试，对应错误 2（6.2）。两处都指到错误的小节。
- **置信度**：高。

#### 3. “TP1 主线 7 项”与报告里 TP1 的 8 条 PASS 不一致

- **原文**：“复现 **25 项测试**（TP1 主线 7 项、TP2 阶段序列、TP3 tile 生效、TP4/5/6 失败路径 7 项、TP7 合同回归、TP8 **跨天对账**”
- **依据**：report.txt 的 TP1 有 8 行 [PASS]（退出码／stage-2 落盘／scf.for／emit_c_interface／.ll／.s／ciface／胶水），总数 25 只有在 TP1＝8 时才加得平（8＋1＋2＋2＋3＋2＋6＋1）；“7 项”只有把 .ll/.s 合并成一项才说得通，与报告自身的计数口径不一致。
- **置信度**：高。

#### 4. §5.1 文件树列出的 t-d117/ 不在冻结产物中（实际存在的 help.txt 反而未列）

- **原文**：“└── t-d117/               # 跨天对账（D117 gemm.mlir 走 minic S4）”
- **依据**：冻结 outputs/ 下没有 t-d117/（它只在运行 run_all.sh TP8 时生成且未存档），而实际冻结的 outputs/help.txt 未列入树。另外 TP8 的内嵌脚本硬编码 llvm_bin="/opt/homebrew/opt/llvm/bin" 并以相对路径读 ../../day-117/code/gemm.mlir，复现依赖 D117 目录在位与 PATH 回退，读者按树找不到文件时无从判断原因。
- **置信度**：高。

#### 5. “D117 的 lower.sh 把五条 pass 写在一个 mlir-opt 命令里”——那条命令实际有 6 个 pass 旗标

- **原文**：“D117 的 lower.sh 把五条 pass 写在一个 mlir-opt 命令里（快）”
- **依据**：lower.sh 阶段 2 的单条命令含 6 个 pass：--convert-scf-to-cf、--finalize-memref-to-llvm、--convert-func-to-llvm、--convert-cf-to-llvm、--convert-arith-to-llvm、--convert-index-to-llvm。“五条”沿袭了 D117 自己“五个转换 pass”的口径（其脚本注释同样写“五个”却列 6 个旗标），按旗标数是差一。
- **置信度**：高。

#### 6. 01-overview.svg 的 S0 框印“38 行计数”——真实输入是 15 行

- **原文**：“**顶部**是命令与六阶段流（S0 读入 ✓ → S1 图优化 11→5 ✓（D121）”
- **依据**：main.graph 共 15 行，manifest 的 S0 日志为“读入 main.graph：15 行、约 14 条 op”；SVG 却印“38 行计数”，与任何真实产物都对不上（图注正文未提行数，属 SVG 独有错值）。
- **置信度**：高。

#### 7. “min(TM,M) 钳制接边界”易被读成已处理尾 tile——实际只钳步长，尾块钳制只存在于注释

- **原文**：“tile 直接进循环步长 `scf.for %i0 = 0 to M step TM`——min(TM,M) 钳制接边界”
- **依据**：生成期 `tm = min(tm, M)`（loop_lower.py 82 行）只覆盖 TM≥M 的情形（实验 A 的 8→4，实测 %cTM 确为 4）；M%TM≠0 时（如 M=5、TM=2，i0 取 0/2/4，末块 [4,6) 越界）靠的是点循环注释里的逐点 `min(i0+TM,M)`（loop_lower.py 95 行），未落地为 IR。5.1 的诚实声明已声明点循环是注释，但日目标这句概括仍容易让初学者以为边界处理已真实生成。
- **置信度**：高。

#### 8. 当日代码两处陈旧文案与“今天接入 S4”的事实冲突（E203 修复建议、.mlir 分支日志）

- **原文**：“**实验 A（tile 边界）**：`--tile 8,8,8`（tile 大于 shape）——观察 stage-2-loop.mlir 里 `min(TM,M)` 的钳制（TM=8 被 M=4 钳成 4）”
- **依据**：实验 A 行为属实，但 minic.py 的 E203 模板写“tile 每维必须 ≤ 对应维度；边界 tile 由 min 钳制处理”——与本教程“tile 大于 shape 不报错、直接钳制”的行为及 W101 文案自相矛盾；另外 .mlir 输入分支的 S4 日志仍写“骨架（……minic 接入排 D123）”，与今日 S4 已真实接入（.graph 输入路径）矛盾，初学者做实验 B 会误以为 S4 未接。均不影响行为，属代码文案清理。
- **置信度**：高。
