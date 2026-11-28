# 第 129 天技术校对报告

审阅范围：README.md、code/specialize.py、code/dyn_shape.py、code/e3_verify.py、code/run_all.sh、code/outputs/（report.txt 与 spec-4x6x3、spec-8x8x8、e2-dynamic 冻结产物）、images/01-overview.svg、02-mechanism.svg、03-example.svg。核对方法：逐项比对冻结产物中的指令与计数、在本机 LLVM 18 上复跑 opt 实验（macOS/LLVM 23.1.5 产物无法在本 Linux 环境重建，涉及项已注明）、核对 PyTorch 官方文档与学习计划原文、对照 D124/D125/D127/D128 的冻结产物。

## 【错误】

#### 1. “O2 展开重排乘加序”的机制解释与冻结产物相反
- **原文**：“展开把 k 序乘加重排成树形/并行序，浮点结果与 k 序不完全一致”
- **依据**：冻结的 outputs/spec-4x6x3/out-O2.ll（第 54–75 行）显示 k 归约是严格串行的 fadd 链：`%23 = fadd float %22, 0.0`、`%27 = fadd float %23, %26`、`%31 = fadd float %27, %30`……每次一条 fmul 一条 fadd，完全保持源码 k 序；全文无 vector 指令、无 fmadd、无多累加器。LLVM 在无 fast-math 标志（reassoc/contract）时不会重排浮点归约，unroll 本身保持累加序。同一仓库 D125 的 golden 正是按 k 序逐次舍入计算的（e2e.py golden_numpy 的注释写明“kernel 按 k 序累加……numpy 的 @ 用分块/向量序——两者可能差 1ulp”），而 D125 的 -O2 版本（variant D）以 bitwise 12/12 通过——若 O2 展开真会重排序，对 k 序 golden 的 bitwise 不可能全过。本机实测（Linux/numpy）也确认：k 序串行累加与 numpy `@` 确有 ULP 级差（bitwise 不等、allclose(1e-5) 通过），但差异来自参照系（BLAS 自己的分块/向量化/FMA），不是 kernel 端。因此“特化+O2 要用 allclose”的结论正确，但归因错误；“IEEE 允许”重排也不成立——IEEE-754 不允许未经许可的重结合，默认语义下编译器必须保持源表达式的求值序（“编译器的合同是‘数值等价’不是‘逐位一致’”仅适用于 fast-math 或参照系自身重排的情形）。第 6 节错误 1（“O2 展开合法地重排了乘加序（k 序→树形序）”）与验收清单第 4 项同错。
- **置信度**：高（依据是当天冻结的 out-O2.ll 逐行可查，并有 D125 同仓库反证）。

#### 2. 图 1 把“动态层”描述为 O2 产物，实际部署的动态兜底库编译自未优化的 out.ll
- **原文**：“O2 保守 fmul=2/phi=10、141 行、一份 .ll 吃任意 shape——D128 的成果直接复用”
- **依据**：specialize.py 第 184–188 行构建 dyn_so 时用的是 `r["ll"]`，即 run_pipeline 返回的 e2-dynamic/out.ll（未过 opt，实测 fmul=1、phi=4、非空行 105），而非 E1 测量生成的 e2-dynamic/out-O2.ll（fmul=2、phi=10、141 行）。也就是说 E2 分发器实际加载的动态兜底 kernel 是未优化版；“fmul=2/phi=10/141 行”是 E1 的测量产物特性，被图 1（README 第 18 行与 images/01-overview.svg 的动态层框，该框同时写着“产物：e2-dynamic/libdyn.dylib”）标成了部署产物的特性。若按宽容读法（“引用 E1 测量值佐证动态层保守”）可视为表述问题，但图注与 SVG 把测量指标与产物路径并置在同一框内，读者会得出“兜底走的是 141 行 O2 版”的错误结论。修复方向：要么让 dyn_so 也走 O2，要么在图/文中明确“测量用 out-O2.ll、部署用 out.ll”。
- **置信度**：高（代码路径与冻结产物计数均可直接核对）。

#### 3. 动态版 fmul=2 被解释为“部分展开”，实际成因是包装函数内联导致的整份复制
- **原文**：“O2 只敢部分展开 fmul=2”
- **依据**：冻结的 e2-dynamic/out-O2.ll 中 fmul=2 的真实来源是：`@kernel_dynamic`（第 8 行 define）的循环体被完整内联进 `_mlir_ciface_kernel_dynamic`（第 72 行 define，块名带 `.i` 后缀），两份循环体各有 1 条 fmul，全文没有任何对 `@kernel_dynamic` 的 call。k 循环 `.lr.ph` 完全未展开（体内单条 fmul、单次迭代一条）；phi=10 同样来自复制＋循环旋转/守卫插入。即“O2 后 fmul=2”是真的，但“部分展开”的机制解读是错的——动态版是“零展开＋内联翻倍”，不是“展开了一半”。images/02-mechanism.svg 的“fmul × 2（只敢部分展开）”同错。该说法承自 D128，但 D129 正文（第 1 节）与图 2 重复了它。核心论断（动态边界未知→不敢全展开）不受影响。
- **置信度**：高（依据当天冻结的 e2-dynamic/out-O2.ll 结构，define/call/块名均可直接核对）。

#### 4. “PyTorch 2.x：同 shape 出现 N 次后自动 compile”不符合 PyTorch 实际行为
- **原文**：“真实系统按阈值触发（PyTorch 2.x：同 shape 出现 N 次后自动 compile）”
- **依据**：PyTorch 官方文档（docs.pytorch.org，torch.compile 页）说明：对进入编译区域的每个 frame“首次执行即尝试编译并把结果缓存在 code object 上”，之后靠 guard 失败触发重编译（`torch._dynamo.config.recompile_limit` 默认 8，超限回退 eager）；文档没有“同 shape 出现 N 次才编译”的频率阈值机制。“按调用频率阈值触发编译”是 JVM HotSpot 分层 JIT、V8 等虚拟机的做法，不是 PyTorch 2.x 的做法。PyTorch 与 shape 相关的实际机制是：默认按静态 shape 特化（dynamic=None 时检测到 shape 变化后在重编译时生成更动态的 kernel）。第 5 节练习 5 让读者去查 `torch._dynamo` 的触发时机，与该句自相矛盾。images/03-example.svg 与 README 第 63 行（图 3 图注“真实系统按调用频率阈值触发特化”）同样传播了这句。
- **置信度**：高（以 PyTorch 官方文档为准；未在本地跑 torch 复验，但文档表述明确）。

#### 5. README 引用的“真机输出”与冻结的 outputs/report.txt 不一致
- **原文**：“第 129 天：静态 Shape 特化——真机报告 2026-11-14 22:40”
- **依据**：outputs/report.txt 第 1 行实际是“2026-11-14 22:15”，与 README 引用相差 25 分钟，说明引用并非取自该文件（或取自另一次未冻结的运行）。此外引文还做了未声明的编辑：TP2 的四条 PASS 被合并改写为一行“特化层命中执行正确／第二特化命中正确／未注册 shape 动态兜底正确／分发统计正确”（实际 report.txt 为四行独立 [PASS]，末条为“分发统计正确（2 hit + 1 miss）”）；“（代码大小记录）”实际为“（代码大小记录——计划条目要求）”；[PASS] 行的实际位置在“全链结论”之后而非各节标题之下。README 明言“`./run_all.sh` 的真机输出（outputs/report.txt……）”，按本仓库“不伪造执行结果”的底线，引文应与冻结文件逐字一致或明确注明摘编。
- **置信度**：高（逐字 diff 可验，时间戳 22:15 vs 22:40 是硬差异）。

#### 6. D136 被引用为“Pass 观测数据（调用频率统计）”，与学习计划第 136 天的实际内容不符
- **原文**：“D136 的 Pass 观测数据（调用频率统计）是特化决策的输入”
- **依据**：《AI 芯片编译器学习计划.md》第 136 天条目是“Pass 二分定位”（学习：通过阶段 IR 和 Pass 开关定位最早错误点；实践：逐个关闭 Pass 的调试流程），与“调用频率统计/热点观测”无关；检索全计划也没有任何一天以“调用频率统计”为主题（最接近的 D135 是“随机 Shape 正确性测试”、D123 是“IR Dump 与可观测性”）。README 第 63 行（图 3 图注“D136 观测数据是输入”）与 images/03-example.svg 的“D136 的观测数据是输入”同样引用错误。该引用是特化决策判据一节的关键支撑，指向不存在的内容会误导读者按计划预习。
- **置信度**：高（计划原文可直接核对）。

#### 7. 实验 B 给出的关闭展开命令 `-loop-unroll=false` 不是有效 opt 旗标，按文操作会直接报错
- **原文**：“`opt -O1` 重新编译特化版（disable loop unroll：`-loop-unroll=false`）——fmul 回到 1~2？”
- **依据**：在本机 LLVM 18 实测 `opt -O1 -loop-unroll=false -S x.ll` 报错：“Optimizations available (use ‘-passes=’ for the new pass manager) option: does not allow a value! ‘false’ specified.”——`-loop-unroll` 是“添加该 pass”的旗标，不接受布尔值。关闭展开的有效旗标是 `--disable-loop-unrolling`（opt --help 可查）。另外实测 -O1（LLVM 18）对同一份静态 IR 仍然全展开（fmul=18、phi=1），即“换 -O1 让 fmul 回到 1~2”的预期也不成立——要压回 fmul≈1 需 `--disable-loop-unrolling` 或降低优化级别并验证。教程环境是 LLVM 23.1.5，本机用 18 验证，但该旗标类别（pass 添加旗标不带布尔值）自新 PM 以来未变，23 突然支持 `-loop-unroll=false` 的可能性极低。
- **置信度**：高（LLVM 18 实测报错；未能在 LLVM 23.1.5 上直接复验，附版本说明）。

## 【存疑】

#### 1. 标题“特化拿性能（fmul 2→18）”把指令数当作性能结论，当日无计时且 D125 在同 shape 上实测反向
- **原文**：“特化拿性能（fmul 2→18）、动态兜正确”
- **依据**：当日 8 项测试没有任何 kernel 级计时（E1 只统计 fmul/phi/行数），fmul 2→18 是“优化空间”证据而非性能证据。同仓库 D125 在同样 4×6×3 规模上做过 kernel 级计时（同进程 20000 次均值）：-O2 展开版 0.032µs 反而比 -O0 循环版 0.019µs 慢约 60%（原因：kernel 太小、acc 链串行依赖、i-cache 代价）。images/01-overview.svg 进一步标注“150 行 .ll（膨胀但快）”与“141 行 .ll（紧凑但慢）”，方向恰与 D125 实测相反。“特化在大规模/热点上拿性能”作为架构叙事成立，但在本教学规模下，快慢方向未被测量且已有反例。建议标注“未计时、D125 反例见前”，或补一次 kernel 级计时。第 5.3 节①虽引用了“D125 反例的同一杆秤”，但只解释了启发式为何选择展开，没有提示展开在本规模可能更慢。
- **置信度**：中（“快/慢”是图内标签与标题的引申，README 正文未直接断言实测更快；D125 反例针对的是含 bias/relu 的同规模 kernel，机制可迁移但非同一代码）。

#### 2. “动态 pad 到最近的特化 shape——TVM 的做法之一”未能核实
- **原文**：“shape 分桶、动态 pad 到最近的特化 shape——TVM 的做法之一”
- **依据**：未能在 TVM 官方文档/源码中找到“pad 到最近特化 shape”作为 TVM 内建策略的依据；TVM 对动态 shape 的官方路线以符号 shape（Relax/symbolic integer）与动态 kernel 为主。分桶/补齐（bucketing/padding）更常见于服务栈与 XLA/TensorRT 类系统。无法完全排除某些 TVM 应用或 BYOC 集成这样做，但归因于“TVM 的做法”缺乏出处，建议改为泛指（“部分推理栈的做法”）或补 TVM 文档出处。
- **置信度**：低（不确定点：TVM 生态庞大，未做穷尽检索；仅确认官方文档主线不是该策略）。

#### 3. “TVM 的磁盘 cache dir”作为跨进程编译产物缓存的例证未能核实
- **原文**：“跨进程复用——TVM 的磁盘 cache dir”
- **依据**：TVM 确有磁盘上的调优记录库（AutoTVM 日志、MetaSchedule Database，默认在 ~/.tvm 下），但我未能在 TVM 官方文档中确认“按 shape 缓存编译产物 .so/.dylib、跨进程复用”是 TVM 的内建功能；当前 TVM main 的 python/tvm/support.py 已无 cache dir 相关接口。若指调优记录缓存，与“编译产物缓存”是两回事，类比会误导初学者。建议核对 TVM 文档后保留或换成更贴切的例证（如 PyTorch Inductor 的 FX graph/autotune cache 目录，有明确文档）。
- **置信度**：低（不确定点：TVM 历史版本与子模块较多，未穷尽检索；仅确认当前 main 的 support.py 无此接口）。

## 【建议】

#### 1. “今日产出”宣称 outputs 含 libkernel.dylib，但该文件被 .gitignore 排除、不在仓库中
- **原文**：“两份特化产物：input.mlir→七 pass→out.ll→out-O2.ll→libkernel.dylib”
- **依据**：仓库 .gitignore 含 `*.dylib`，outputs/spec-4x6x3/ 与 spec-8x8x8/ 实际只有 input.mlir、s0–s7.mlir、out.ll、out-O2.ll。clone 后读者看不到 libkernel.dylib（E3 的“产物大小 50000 B”也因此无法离线复核，需重跑 run_all.sh 才能生成）。另外 5.1 的文件树未列出实际存在的 code/e3_verify.py（它是 D128 的遗留文件，run_all.sh 不运行它、正文也不引用，属孤儿文件），树中还把 e2-dynamic 标注为“D128 产物复制”而实际是 specialize.py 触发 dyn_shape.run_pipeline 重建的（内容确定性一致，但表述与机制不符）。建议注明“libkernel.dylib 由 run_all.sh 生成、不入库”，并修正文件树。
- **置信度**：高（文件清单与 .gitignore 可直接核对）。

#### 2. “唯一差异是签名”掩盖了 stride/offset 也被一并特化
- **原文**：“唯一差异是签名（静态 `memref<4x6>` vs 动态 `memref<?x?x>`）”
- **依据**：两版 IR 的差异不止 shape：静态版类型带 `strided<[6,1]>/<[3,1]>`（stride 编译期常量，out-O2.ll 里地址是 `%18, 24` 这类常量偏移），动态版 `memref<?x?xf32>` 连 stride 都从描述符运行期读（out.ll/out-O2.ll 里是 `mul nsw i64 %20, %5`）；输出分配也随 shape 动静态化。这些都源于 memref 类型（广义“签名”），“唯一差异是签名”字面上说得通，但读者容易以为对照只隔离了 shape 一个变量。fmul/phi 的主因（循环边界可证）不受影响，建议补一句“stride/offset 一并进了类型”。
- **置信度**：高（两版 IR 与产物可直接比对）。

#### 3. “外层 i/j 值得部分展开”与冻结产物不符：j 被完全展开、i 完全没展开
- **原文**：“而外层 i/j 值得部分展开”
- **依据**：spec-4x6x3/out-O2.ll 显示：j 循环（N=3）被完全展开（循环体内 3 组独立累加、18 条 fmul＝3×6），i 循环（M=4）保留为循环（唯一 phi %18、退出条件 `icmp samesign ult i64 %18, 3`）。“部分展开”通常指展开因子小于迭代次数，这里实际是“j 全展开、i 不展开”；图 2 的“fmul × 18（K 循环展开＋部分展开）”同此。顺带可解释“为什么是 18 而不是 72”：72 MAC＝i(4)×j(3)×k(6)，i 留在循环里所以体内只有 3×6=18 条 fmul——正文①已提出该问题但未给出这个分解，补上会更清楚。
- **置信度**：高（冻结 out-O2.ll 结构逐行可查）。

#### 4. 关键坑演示缺失：非连续（转置/切片）输入在命中路径会被静态 kernel 静默算错
- **原文**：“真实系统还要加 dtype/layout 进 key（f32 与 f16 的 kernel 不同）”
- **依据**：错误 2 一节讲了 key 的 shape 三维完备性并在“教训”里点到 dtype/layout，但没有演示最常见、最隐蔽的坑：静态签名的 `strided<[6,1]>` 假定输入按行连续，ciface 包装不做任何校验；若调用方传入 `A.T`、切片视图等非连续数组（make_desc 会如实填 st，但静态 kernel 根本不读描述符的 st/sh），key=(4,6,3) 仍命中、kernel 按假定的连续布局寻址，结果是静默错数而非崩溃。动态层反而因为从描述符读 stride 而天然兼容。这是 shape 特化在真实系统里必须把 layout 纳入 key 的根本原因，建议作为“错误 5”或实验补一个可复现的最小反例。
- **置信度**：高（由 gen_static_ir 的 strided 静态类型与 ciface 包装不校验可直接推出；未在本机实际运行 macOS 产物，属代码级推理）。

#### 5. 跨日数字 6→18 的成因未解释，读者会对不上账
- **原文**：“D125 的 -O2 展开分析（fmul 1→6 的机制今天放大到 2→18）”
- **依据**：D125 的 fmul=6 出自带 bias/relu 的融合 kernel（k=6 全展开、j 不展开），D129 的 18 出自无 bias/relu 的纯 matmul（k、j 都全展开＝3×6）。同为 4×6×3、同为 opt -O2，数字不同是因为 IR 不同（D129 的 spec-4x6x3/out.ll 与 D128 的 e1-static/out.ll 逐字一致、仅函数名不同，说明 D128 引用的“静态版 6”实际是 D125 那份不同 IR 的数字）。正文只说“放大”，读者无法解释为何同 shape 同优化器会出现 6 与 18 两个数。建议补一句成因（bias/relu 有无与展开深度），顺带弥合 D128 的旧数字。
- **置信度**：高（D125/D128/D129 三处冻结产物均已比对）。

## 附注（配图审阅结论）

现有 3 张图（01 架构、02 机制对照、03 进度与成本账）已覆盖两层分发、展开安全性证明、成本账三大难点。本审阅评估过的候选新增图——“k 归约的三段 IR 演化（scf.for→LLVM 循环→展开后的直线代码）”与“18=3×6×4 的展开分解”——均需要与正文“外层 i/j 值得部分展开”“展开把 k 序乘加重排成树形/并行序”等表述保持一致，而这些表述与冻结产物不符（见错误 1、建议 3）：按真实产物画会与正文矛盾、按正文画会与产物矛盾，故本次不新增图片；待相关表述修正后可再评估。

---
审阅环境说明：本机为 Linux（无法复用 macOS/Homebrew LLVM 23.1.5 产物）；凡涉及“在本机运行”的验证（numpy 数值实验、opt 旗标行为）均已在 /tmp 临时目录完成，未改动仓库冻结产物。
