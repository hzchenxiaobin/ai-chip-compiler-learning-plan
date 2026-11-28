# 第 123 天技术校对报告

审阅对象：`tutorials/week-018/day-123/README.md`、`code/`（observability.py、run_all.sh、minic.py、loop_lower.py、graph_passes.py、main.graph、gen_images.py）、`code/outputs/`（report.txt、timeline.txt、level-matrix.json、obs-*）与 `images/` 的 SVG（原有 01~03 三张；配图审阅后按本报告结论补充 04-file-policy.svg，正文 5.2 已插入图 4）。审阅环境：Linux，Python 3.11.4，本机无 mlir-opt（无法重跑 S4/S5 管道；所有与管道相关的结论均以冻结产物＋纯 Python 可复现部分为依据，已逐条注明）。已实测：gen_loop_ir 两种 tile 的计数对比、op_distribution/diff_dist 对 "add→or" 的行为、minic CLI 对 `--dump-ir=off` 的实际响应、S1 闸1 的节点数。LLVM 23.1.5 已对照 llvm/llvm-project 官方 release 列表核实存在（23.1.6 发布于 2026-11-17，晚于教程日期 2026-11-14），环境声明可信。

## 【错误】

#### 1. 引用的"真机输出"与冻结的 outputs/report.txt 不一致，且包含一行在该脚本下不可能出现的输出
- **原文**：“第 123 天：IR Dump 与可观测性——真机报告 2026-11-14 21:45”
- **依据**：冻结的 outputs/report.txt 首行是"2026-11-14 21:32"。5.3 节声称该块是“真机输出（outputs/report.txt，12 PASS / 0 FAIL）”，但逐行对照：引用块中"计时点 11 个，管道总耗时 ≈ 394 ms"实为"≈ 390 ms"；"[S2] S2 循环生成: 3.7 ms"实为"4.6 ms"；"[S4] pass canonicalize+csi: 42.7 ms"实为"45.7 ms"。更硬的问题：引用块 TP4 中的"    最慢：pass convert-func-to-llvm: 44.4 ms"这一行在 report.txt 中根本不存在——run_all.sh TP4 的 Python 代码 `print(f"    最慢：{slowest['note']}")` 的输出没有 tee 进报告文件（只 `&& ok "..." | tee -a`），该行只会出现在终端 stdout，永远不会进 report.txt。TP4 的 [PASS] 文案也不一致（实际为"「哪条 pass 最贵」→ 时间线可查（教学量级 ~40-55ms/条）"）。时间数值随运行波动可以理解，但把与冻结产物不符、且含结构上不可能出现的行的文本标注为“真机输出（outputs/report.txt）”属于引用失实。
- **置信度**：高（逐字符 diff 冻结文件与引用块；TP4 输出路径由 run_all.sh 源码直接可证）。

#### 2. 3.4 的 timeline"当天实测证据"与冻结的 timeline.txt 全面不符，"<15%"结论在本仓库数据上不成立
- **原文**：“**当天实测证据**：timeline.txt——S2 3.7ms、八条 pass 38.8~44.4ms、translate 42.0ms、llc 30.2ms、总 ≈394ms；最慢是 convert-func-to-llvm 44.4ms（与最慢 pass 差距 <15%——量级被进程启动抹平的证明）。”
- **依据**：冻结 timeline.txt 的 11 个计时点为：S2 4.6ms、八条 pass 37.7~45.7ms、mlir-translate 39.7ms、llc 22.5ms，合计 389.5≈390ms；最慢的是 canonicalize+csi 45.7ms（不是 convert-func-to-llvm 43.7ms）。按本仓库数据，最快/最慢 pass 差为 (45.7−37.7)/37.7≈21%，不满足"<15%"；"llc 30.2ms"实为 22.5ms、"translate 42.0ms"实为 39.7ms。images/03-example.svg 同样嵌入这组与 timeline.txt 不符的数字并自称"管道时间线（timeline.txt，实测一次）"。另有笔误级自相矛盾："与最慢 pass 差距 <15%"按字面是自我比较（差为 0），对照 5.3 的"最慢 pass（func→llvm 44.4ms）与最快（scf→cf 38.8ms）差 <15%"可知本意是"最快"。这组数字可能来自另一次运行，但既然 3.4 明确标注证据来源是 timeline.txt，就应与该文件一致（或重新冻结产物）。
- **置信度**：高（数值比对是机械事实；“来自另一台次运行”只能解释差异，不能解释把它标注为 timeline.txt 的实测证据）。

#### 3. "full 级再加 diff 统计"未实现：full 与 passes 在代码中行为完全相同
- **原文**：“→ full 级再加 diff 统计（"为什么长这样"）”
- **依据**：observability.py 中没有任何 full 独有的逻辑：`rewrite()` 对 passes/full 同样记录（只有 off/stages 被跳过，第 112 行）；`dump()` 与 `run_s45_observed` 的 `keep_files = obs_level in ("passes", "full")` 对两者同样处理。教程自己的实测证据 level-matrix.json 里 passes 与 full 两行完全相同（files=11, dumps=11, rewrites=8），冻结的 outputs/obs-passes/ 与 outputs/obs-full/ 十一个文件逐一相同（文件名与字节数都一致）。"full 再加 diff/时间线"与 TP1 输出（"full: files=11 dumps=11 rewrites=8"，与 passes 行相同）自相矛盾，也与 3.1 的"passes/full 落盘全部"矛盾——四层语义在实现里实际是三层（off/stages/【passes≡full】）。
- **置信度**：高（代码路径穷举＋冻结矩阵逐行比对）。

#### 4. "八条 pass 里三条记录结构无变化"是误数：实际是四条
- **原文**：“八条 pass 里三条记录"结构无变化"（cf/arith/index 转换）”
- **依据**：README 自己引用的 TP2 输出（与冻结 report.txt 一致）中有四行"结构无变化"：convert-scf-to-cf 3→3、convert-cf-to-llvm 48→48、convert-arith-to-llvm 48→48、convert-index-to-llvm 48→48。convert-scf-to-cf 的无变化同样符合 3.3 的解释——canonicalize 删光了 scf.for，它没有输入残留可转（3.3 正文"前面的 pass 已把本图的对应残留清光"对它同样成立）。"三条"的说法还出现在今日目标、3.3 标题、图 2/图 3 说明（图 2 底部甚至写作"五条 convert 里三条"）、5.3③、验收清单和总结，初学者按图索骥数出来的必然是 4。
- **置信度**：高（对冻结 report.txt 逐行数"结构无变化"出现次数：4）。

#### 5. "九个 index 常量＋四个循环壳／砍掉 13 个 op"误读了自家 diff 产物：实际是 8 个 index 常量＋1 个 f32 常量＋3 个循环，真正删掉 12 个 op
- **原文**：“九个 index 常量＋四个循环壳”
- **依据**：冻结的 obs-full/stage-2-loop.mlir 只有 3 个 scf.for（%i0/%j0/%k0）。"scf.for -4"的第 4 个计数来自文件头注释“// minic S2 生成：图 IR → 循环 IR（scf.for 三重循环）”——op_distribution 是全文文本匹配，注释也被计入（本机实测：该文件 scf.for 文本出现 4 次，其中 3 次是真 op）。被删的 9 个 arith.constant 中 8 个是 index 常量（%c0/%cM/%cN/%cK/%cTM/%cTN/%cTK/%c1），第 9 个是 %zero（f32），"九个 index 常量"不准确。"func.return -1"也不是删除：return op 仍在（stage-4-03 第 4 行的裸 `return %alloc : memref<4x3xf32>` 就是 func.return 的短打印形式，D117 的 census.py 文档字符串明言"MLIR 打印自定义语法里 return 是 func.return 的短印法，计数时归一化"），count_ops 的启发式漏计了不带前缀的 return 行。因此真正被删除的是 12 个 op（9 常量＋3 循环），"16→3 砍掉 13 个 op"里的第 13 个是计数伪影；按 op 语义应是 16→4。
- **置信度**：高（两处计数均已用当日代码实测；mlir-opt 本机不可用，但 stage-4-03 是冻结事实）。

#### 6. "S2 的 3.7ms 是唯一'真活'（纯 Python 字符串生成）"——计时区间里根本没有字符串生成
- **原文**：“S2 的 3.7ms 是唯一"真活"（纯 Python 字符串生成）”
- **依据**：gen_loop_ir 在调用方执行（run_all.sh 先 `loop_ir = gen_loop_ir(...)` 再调 run_s45_observed），不在计时区间内。run_s45_observed 里 t0 到 `obs.timing("S2", "S2 循环生成", ...)` 之间只有：`import tempfile`、`tempfile.mkdtemp()`、写 stage-2-loop.mlir、`obs.dump`（passes/full 级还会把同一文件再写一遍）。该计时点量的是模块导入＋临时目录创建＋文件 I/O，与"纯 Python 字符串生成"无关；标签"S2 循环生成"本身也名不副实（实际是"S2 落盘"）。后文"它就是 in-process PassManager 未来能把其它 40ms 压到的量级参照"建立在这个错误解读上。
- **置信度**：高（observability.py 第 177~186 行的计时区间逐行可核）。

#### 7. "进 manifest"系列声称全部未实现：manifest_section() 从未被调用，outputs/ 里没有任何 manifest
- **原文**：“3. **时间线**：perf_counter 包住每个 subprocess——11 点进 manifest；”
- **依据**：全天代码（observability.py、run_all.sh）没有任何地方调用 `manifest_section()`（grep 全仓可证，它只是定义从未被引用的死代码）；outputs/ 下的产物只有 report.txt、level-matrix.json、timeline.txt 和 obs-*，没有 manifest.json。时间线实际是 run_all.sh TP3 用 `json.dump(tl, ...)` 写进 timeline.txt 的，与 manifest 无关。同族失实声称还有："off 零文件只留 manifest（CI 常规跑）"（off 级实际什么都不产出，冻结产物里连 outputs/obs-off/ 目录都不存在）；"manifest 的 `timeline_ms` 字段按 what 聚合"（字段存在于从未被调用的函数里）；"机器可读的 delta 列表进 manifest，人话进 stages 日志"（manifest_section 的 rewrites 字段只收 note 字符串，delta 列表从不导出；也不存在承载改写记录的"stages 日志"——它们只被 TP2 打印到 stdout）。observability.py 模块 docstring 也写着"3. 时间线：……进 manifest"，与实现同样不符。
- **置信度**：高（函数调用点穷举＋outputs/ 目录清点）。

#### 8. minic 集成声称不实：--dump-ir 四级 CLI 不存在，minic.py 也没有"观测层外挂"
- **原文**：“├── minic.py                  # minic 0.3.0（D122 同款；观测层外挂）”
- **依据**：三项都可验证：（a）day-123 与 day-122 的 minic.py 里 VERSION 均为 "minic 0.2.0 (day-121: S1 graph passes)"，`./minic.py --version` 实测输出该串，"minic 0.3.0"与文件自报版本不符（D122 的 README 也声称 0.3.0，版本号从未在代码里升级）；（b）minic.py 通篇没有 import observability，"观测层外挂"无从谈起——观测只存在于独立调用的 run_s45_observed；（c）minic 的 `--dump-ir` 是 `action="store_true"` 布尔开关，实测 `python3 minic.py main.graph --dump-ir=off` 直接报错 "argument --dump-ir: ignored explicit argument 'off'"（退出码 2），即 `--dump-ir=off/stages/passes/full` 这一 CLI 形态不存在。TP5 标题"[TP5] minic 集成：--dump-ir=off/stages/passes/full"名不副实——实际测试内容只断言 `Observability.LEVELS` 元组存在（run_all.sh 注释也自承"修改版 minic 今天先用环境观察方式"）。第 6 节错误 1 的现象描述"`--dump-ir=off` 跑完目录里还有 11 个 stage 文件"同样预设了这个不存在的 CLI 形态。
- **置信度**：高（三项均在本机实测或源码穷举）。

#### 9. 错误 2 的反例与工具实际行为相反："把 add 换成 or"会被 delta 如实显示
- **原文**：“数量相同的重写（如把 add 换成 or）记录显示"无变化"”
- **依据**：用 observability.py 自己的 count_ops/op_distribution/diff_dist 实测：把两处 arith.addf 换成 arith.ori，得到的记录是"X: 7→7 op（arith.ori +2, arith.addf -2）"——op 名变了就出现在 delta 里，不会显示"结构无变化"。本工具真正探测不到的语义改写是名字与计数都不变的那类：实测把 `arith.constant 1.0` 改成 `2.0`、或交换操作数顺序，记录才是"（结构无变化）"。3.2 自己承诺"一句话记录的承诺是'有变化必可感知'"，改名重写恰恰是可感知的。反例应换成"改常量值/换操作数"才成立。
- **置信度**：高（已用当天代码直接实测两种情形）。

#### 10. 实验 A／练习 1 的前提不成立：两种 tile 生成的 IR 结构完全相同，改写记录不会变
- **原文**：“观察 canonicalize 的记录从"16→3"变成什么（钳制后的常量更少、折叠更少——改写记录对输入敏感）”
- **依据**：gen_loop_ir 对 tile=(2,3,6) 与 (8,8,8)（钳制为 4,3,6）生成的 IR 结构逐项相同——实测两者 count_ops=16、op_distribution 中 arith.constant=9、scf.for=4、func.return=1，唯一差异是 %cTM 的值（2 与 4）。tile 只改常量值不改常量数量，"钳制后的常量更少、折叠更少"与练习 1 的提示"canonicalize 的折叠量随常量数量变化"都被输入侧事实否定。循环体为空（点循环是注释），canonicalize 删除空循环与死常量的结果与常量取值无关，两份改写记录应一字不差——"diff 两份改写记录——哪几条记录变了？"的答案是"一条都不变"。要让改写记录变化，需要改图结构（例如去掉 bias 会改变 convert-func 阶段描述符/extractvalue/load 的计数），而不是改 tile。
- **置信度**：高（输入结构已实测相同）；"canonicalize 输出亦相同"由输入同构＋冻结 stage-4-03 的行为推断，本机无 mlir-opt 未直接运行验证——这是本条唯一的不确定点，但它不影响"前提（常量数量变化）为假"这一结论。

#### 11. "跑完即焚"不实：tempfile.mkdtemp() 创建的临时目录从不删除
- **原文**：“off 全部临时目录（跑完即焚）、stages 只回写阶段文件、passes/full 落盘全部。”
- **依据**：run_s45_observed 用 `tempfile.mkdtemp(prefix="minic-obs-")` 创建临时目录，之后没有任何清理——没有 shutil.rmtree、没有 TemporaryDirectory 上下文管理器，全天代码 grep 可证。Python 官方文档明确 mkdtemp 创建的目录"由调用者负责删除"，这些文件会留在系统临时目录直到系统级清理。也就是说 off 级每次运行都在 /tmp 新建一个 minic-obs-* 目录并永不删除——这恰恰复现了第 6 节错误 1 要防的问题（"off 级留着文件等于 CI 每次跑都在积累垃圾"），垃圾只是从 out_dir 挪到了 /tmp。第 6 节错误 1 修复描述"off/stages 级的 pass 链走临时目录（跑完即焚）"同病。"out_dir 不留痕"是真的，"即焚"是假的。
- **置信度**：高（mkdtemp 语义是 Python 标准库文档行为；清理代码不存在由 grep 证实）。

#### 12. 3.3 的"convert-scf-to-cf 已生成 llvm 块结构"与自家 TP2 记录直接矛盾
- **原文**：“cf 层无 cf.br 残留（convert-scf-to-cf 已生成 llvm 块结构）”
- **依据**：TP2 记录明示"convert-scf-to-cf: 3→3 op（结构无变化）"——这条 pass 本次什么也没生成；cf 无残留的真正原因是 canonicalize 把三个空循环删光了，convert-scf-to-cf 没有输入可转（这正是 3.3 第一句"前面的 pass 已把本图的对应残留清光"的正确表述，括号里的"技术对应"把它推翻了）。此外该 pass 的功能是把 scf.for 转成 cf.br/cf.cond_br 控制流，也不叫"llvm 块结构"。同句"index 已被 finalize-memref 带走"的因果归属同样可疑：8 个 index 常量是被 canonicalize 删掉的（对应 arith.constant -9），finalize-memref 反而新建了 4 个 llvm.mlir.constant（4/3/1/12，源值标注 index、结果直接定型 i64）——不是"带走残留"而是"以 i64 形态新建"。
- **置信度**：高（对"已生成 llvm 块结构"的否定——与冻结记录逐字冲突）；中（对"index 已被 finalize-memref 带走"的评价——宽松解读下可争辩，但因果方向确实说反了）。

#### 13. "op_distribution() 正则统计方言 op（D117 census 口径）"不成立：两者口径差异正是当天多处记录伪影的来源
- **原文**：“`op_distribution()` 正则统计方言 op（D117 census 口径）”
- **依据**：D117 的 census.py 是行锚定计数（`OP_RE = ^\s+(?:%[\w.]+\s*=\s*)?([a-zA-Z_][\w.]*)`，只取行首 op 名），并且有 ALIASES 把短打印归一化（return→func.return、br→cf.br、cond_br→cf.cond_br）。D123 的 op_distribution 是全文无锚正则 `\b((?:memref|arith|scf|func|cf|llvm|index)\.[\w.]+)\b`，注释、类型串、属性名一律计入：scf.for -4 中有 1 个来自注释（见错误 5）、"llvm.struct +9"与"llvm.ptr +6"全部是类型串（stage-4-05 中 9 处 llvm.struct 均出现在 `!llvm.struct<(ptr,...)>` 类型位置，没有一个是 llvm.struct op）、"llvm.func/llvm.emit_c_interface"这类名字也会被数。TP2 标题把 delta 称作"op 增删"、TP4 把"llvm.struct +9"读作"描述符进场"的证据——按 op 口径这些数字都不成立，按文本匹配口径它们才成立。教程从未披露这个口径差异，初学者会把类型计数当 op 计数。
- **置信度**：高（两种正则行为差异已实测；D117 census.py 源码在仓内可直接比对）。

## 【存疑】

#### 1. "真实 MLIR 的 in-process PassManager 会压到 µs 级"作为定量断言无法在本环境核实
- **原文**：“真实 MLIR 的 in-process PassManager 会压到 µs 级”
- **依据**：本机没有 mlir-opt，无法用 `--mlir-timing`/`--mlir-time-passes` 实测（练习 5 正是这个核实路径，设计是对的）。就常识而言，对本图这种 3~48 op 的小模块，进程内单条 pass 的耗时通常在 µs 到亚 ms 量级，方向上说得通；但"会压到 µs 级"作为无限定语的一般性论断依赖 IR 规模与 pass 类型，LICM/CSE 在大模块上可以到 ms 级以上。教程在 3.4 和图 3 里把它当作确定事实陈述，建议限定为"对本图规模"或等练习 5 实测后再定性。
- **置信度**：中（方向合理、量级断言过强；本环境无法直接验证，不确定点是真实 mlir-opt 在该小模块上的实测值）。

## 【建议】

#### 1. pass 名"canonicalize+csi"疑为"canonicalize+cse"笔误，沿用了 D122 的 PASSES 表
- **原文**：“canonicalize+csi: 16→3 op（arith.constant -9, scf.for -4, func.return -1）”
- **依据**：loop_lower.py（D122 同款）中该条目的 flags 是 `["--canonicalize", "--cse"]`——CSE（Common Subexpression Elimination）才是与 --canonicalize 并列的第二个开关，"csi"不是任何 MLIR pass 的缩写。当天的记录、图 2 与正文十余处使用"canonicalize+csi"，初学者拿这个名字去 mlir-opt --help 里搜索会落空。建议后续日修正 PASSES 表或当 README 首次出现处注一句"csi=cse 笔误（合成名）"。
- **置信度**：高。

#### 2. 文件树声称的 obs-{off,...} 四个产物目录中 obs-off 在冻结产物里不存在
- **原文**：“obs-{off,stages,passes,full}/  # 四级实际产物目录”
- **依据**：outputs/ 下只有 obs-stages/、obs-passes/、obs-full/ 三个目录。off 级零文件、目录为空，空目录不被 git 跟踪，所以 obs-off/ 实际不在仓库里。这不影响正确性（与"off=0 文件"自洽），但按文件树逐项核对的学习者会找不到第四个目录；建议在树注里写明"obs-off 为空目录（零文件，不入库）"。
- **置信度**：高。

#### 3. "两个 strided memref 签名拆成 14 个裸参数"漏了第三个 memref 的 5 个参数
- **原文**：“两个 strided memref 签名拆成 14 个裸参数＋重打包”
- **依据**：stage-4-06 里 @main_kernel 的 LLVM 签名实际有 19 个参数：%arg0~%arg6（%a，2D，7 个）、%arg7~%arg13（%b，2D，7 个）、%arg14~%arg18（%bias，1D，5 个）。"两个 strided memref → 14 个裸参数"就两个 2D 参数而言是对的，但 %bias 同样是 strided<[1]> 描述符且同样被拆包，不补这 5 个，读者对着 IR 数参数会对不上（19≠14）。
- **置信度**：高。

#### 4. observability.py 模块 docstring 的四级语义与实现（及 README 3.1）不符，建议同步
- **原文**：“文件策略跟着走（off 全临时目录、stages 只回写阶段文件、passes/full 落盘全部）”
- **依据**：README 这句与实现一致（stages=2 文件），但 observability.py 顶部 docstring 写的是"stages 每阶段末尾一份（D122 行为：11 个文件）""passes 每条 pass 一份（D122 的 stage-4-NN 已是；再加 S1 审计）"——按实现，stages 是 2 个文件（stage-5.ll/.s），passes 是 11 个文件（含 stage-2 与两个 S5 产物），且 S1 审计从未接入（run_s45_observed 不做 S1 侧 rewrite）。docstring 描述的是一个未实现的旧设计，读代码的人会被误导；建议下次触碰该文件时同步。README 本身的这句技术对应是正确的，故列为建议。
- **置信度**：高。
