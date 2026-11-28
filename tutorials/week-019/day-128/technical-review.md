# 第 128 天技术校对报告

> 审阅视角：AI 芯片编译器工程师（十年）。方法：通读 README、`code/`（dyn_shape.py / e3_verify.py / run_all.sh / gen_images.py）、全部冻结产物（outputs/report.txt，e1-static/ 与 e2-dynamic/ 的 input.mlir→s4-00~07→out.ll/out.s）与 3 张 SVG；跨天核对总计划第 19 周第 128 天条目与 D114/D115/D118/D124/D125/D127 的原文；并在隔离临时目录用本机 LLVM 18.1.8 完整重跑双版七 pass 管道（mlir-opt→mlir-translate→llc）、对冻结 .ll（剥离 LLVM 18 无法解析的 gep `nuw` 后）与本地再生成 .ll 跑 `opt -O2` 计 fmul/phi、把动态 .ll 编成共享库用 ctypes 复跑 E3 三组 shape＋随机 64×64 对照、实测 §6 三个语法坑的报错文本。本机为 Linux aarch64＋Ubuntu LLVM 18.1.8＋gcc＋Python 3.11.4＋numpy 1.26.4；冻结 .ll 为作者 Homebrew LLVM 23.1.5（macOS arm64）产物（out.s 是 arm64 macOS 汇编、含 `getelementptr inbounds nuw` 新语法，内部自洽）。E1/E2 指标计数、E3 三组数值（24.5/6.0/58.0）、三个语法坑报错文本、随机大矩阵 bitwise 失败均本地复核通过；涉及作者环境（LLVM 23.1.5）的数字无法本地复测的，已在置信度中注明。

## 【错误】

#### 1. “+6 处 extractvalue”的分解“3 个 dim 各读 2 处”不成立——三个 dim 各读一次，另外 3 处是循环体内的 stride 读回
- **原文**：“extractvalue +6（3 个 dim 各读 2 处）”
- **依据**：冻结 e2-dynamic/out.ll 中读 sizes 字段（下标 3,x）的 extractvalue 只有 3 处且全在函数头部：L21 `%29 = extractvalue … %28, 3, 0`（A.sizes[0]=M）、L22 `%30 = … %28, 3, 1`（A.sizes[1]=K）、L23 `%31 = … %21, 3, 1`（B.sizes[1]=N）——每个 dim 恰好读一次，与 §3.1 自己写的“三个 dim（M/K/N）各读一次”一致。其余 3 处增量是读 strides 字段（下标 4,0）：L61（k 循环体内）、L67（k 循环体内）、L79（j 循环收尾）。“3 个 dim 各读 2 处”（=6）把 stride 读回误记成 dim 读回。根源是 E2 用裸 `memref<?x?xf32>`（不带 strided），stride 与 shape 一起变成运行期值。README §5.3 引用块“extractvalue：17 → 23（+6——3 个 dim 各读 2 处）”（源自 run_all.sh 第 50 行的硬编码文案）与 03-example.svg“每个用 shape 的地方都要从描述符读（+6 处）”传播同一错误。
- **置信度**：高（冻结 .ll 逐行核对，extractvalue 的字段下标可直接判读）。

#### 2. “+6 处 extractvalue 全在函数头部”不成立——6 处中 3 处在循环体内
- **原文**：“今天 .ll 的 +6 处 extractvalue 全在函数头部，循环体零差异的原因”
- **依据**：冻结 e2-dynamic/out.ll 的 6 处增量 extractvalue 中只有 3 处（L21~L23，dim 读回）在函数头部，另外 3 处在循环体内：L61 `%57 = extractvalue … %28, 4, 0`（k 循环体 bb"55:"内）、L67 `%63 = extractvalue … %21, 4, 0`（k 循环体内）、L79 `%73 = extractvalue … %42, 4, 0`（j 循环收尾 bb"71:"内）——都随每圈迭代执行。“全在头部”与产物直接矛盾；今日目标里“extractvalue 17→23＋6 处——**全是头部开销**”同错。
- **置信度**：高（行号与所属基本块可直接核对）。

#### 3. “核心循环体完全不变／逐指令相同”不成立——循环体的边界与地址计算指令实际不同（phi/fmul 只是计数相同）
- **原文**：“而**核心循环体完全不变**（phi 4/4、fmul 1/1）”
- **依据**：两版冻结 .ll 循环体逐指令比对至少三处不同：①循环边界：静态 `%39 = icmp slt i64 %38, 4`／`%43 … 3`／`%48 … 6`（常量，L33/L41/L50）vs 动态 `%45 = icmp slt i64 %44, %29`／`%49 … %31`／`%54 … %30`（SSA 值，L39/L47/L56）——这正是教程自己的“翻转铁证”，而循环边界指令就在循环体里，“逐指令相同”与教程的核心论断自相矛盾；②地址计算：静态 `mul nuw nsw i64 %38, 6`（stride 常量内联，L55/L60/L71）vs 动态先 `extractvalue … 4, 0` 再 `mul nsw i64 %44, %57`（stride 运行期读回，L61~62 等）；③标志位：静态 `mul nuw nsw`／`getelementptr inbounds nuw` vs 动态 `mul nsw`／`getelementptr inbounds`。成立的说法只有弱得多的“phi/fmul 指令计数不变”。§3.2 的“循环体（bb 循环块）逐指令相同”、图 1 图注“phi/fmul 不变（核心循环体零差异——绿行强调）”、01-overview.svg“不变！核心循环体零差异”、§9“（+9% 全头部、循环体零差异）”均传播同一过强论断。
- **置信度**：高（两版 .ll 逐行 diff：9 行差异中 3 行落在循环体内）。

#### 4. “9 行差异全在头部＋（dim +6／alloc 尺寸 +2／返回描述符 +1）”的行数分解与产物不符
- **原文**：“104−95=9 行全在头部：三个 dim 的 extractvalue（+6）、动态 alloc 的尺寸参数（+2）、返回描述符构建（+1）”
- **依据**：冻结产物的实际分布：函数头部 +6 行＝3 条 dim extractvalue（L21~23）＋malloc 尺寸计算的 `mul`/`getelementptr`/`ptrtoint` 共 3 条（L24~26，不是 +2）；循环体 +3 行＝3 条 stride extractvalue（L61/L67/L79）。“返回描述符构建”是零行差——两版都恰有 7 条 insertvalue（静态 L22~28、动态 L28~34），+1 无从谈起。真实账目是 9=6（头部）+3（循环体），既非“全在头部”，也不是 6+2+1。TP4 的“代价量化入档（+9 行、+6 extractvalue、循环体不变）”摘要在引用块内同带“循环体不变”的过强结论。
- **置信度**：高（两版 .ll 分段清点：头部 9→15 行、循环体 51→54 行）。

#### 5. 引用块内“多 23 次描述符读回（静态版 0）”两个数字都不实
- **原文**：“—— 动态版代价：多 23 次描述符读回（静态版 0）”
- **依据**：静态版 .ll 共 17 处 extractvalue（kernel 内 3 处：L54/L59/L70 读 aligned 字段；ciface 内 14 处），“静态版 0”在任何口径下都不成立；“多 23 次”把动态版总数（23）当成了增量，实际增量是 6（kernel 内 9−3）。该行由 dyn_shape.py 第 157 行 `print(f"  —— 动态版代价：多 {r['extractvalue']} 次描述符读回（静态版 0）")` 生成——打印的是动态版自己的 extractvalue 总数，“静态版 0”是硬编码。静态版并非不读描述符，只是不读 sizes/strides 字段。
- **置信度**：高（两版 .ll 计数直接复核：总数 17 与 23、kernel 内 3 与 9）。

#### 6. §5.3 以“真机输出（outputs/report.txt）”名义引用的报告块与冻结文件不符（时间戳、段落归属、多出与缺失的行）
- **原文**：“`./run_all.sh` 的真机输出（outputs/report.txt，5 PASS / 0 FAIL）：”
- **依据**：冻结 outputs/report.txt 与该引用块逐项不符：①时间戳“2026-11-14 22:06” vs 引用块“22:30”；②report.txt 里“== E2 动态签名…ok=True｜.ll 104 行…多 23 次描述符读回”三行打印在 [TP1] 段内（dyn_shape.py 一次调用先后打印 E1 与 E2，经 TP1 的 tee 入档），引用块把它们挪到 [TP2] 名下；③引用块多出一行“静态 icmp: 常量 4｜动态 icmp: 描述符字段 %29——shape 语义翻转的铁证”——该行由 run_all.sh 第 36 行的 python 打印，但该调用没有 `| tee -a "$R"`（只到 stdout），冻结 report.txt 中不存在此行；④8×8 行的“（对角×2 缩放，”被删。引用块既不等于 report.txt 也不等于终端原样输出，属拼接改写；SKILL 质量底线要求“不伪造……执行结果”。
- **置信度**：高（冻结文件与引用块逐字 diff，四处差异均可直接复核）。

#### 7. 今日产出与 §5.1 文件树声称 `code/outputs/e3/`（动态共享库）存在——仓库中该目录不存在
- **原文**：“└── e3/                   # 动态共享库（dyn.o + libdyn.dylib）”
- **依据**：outputs/ 下实际只有 e1-static/、e2-dynamic/、report.txt 三项（目录列举与 git ls-files 双重核对）；e3_verify.py 确会生成 outputs/e3/dyn.o＋libdyn.dylib，但仓库 .gitignore 排除 `*.o`/`*.so`/`*.dylib`，二进制从未入库，克隆出的仓库里没有这个目录。今日产出的“`code/outputs/e3/`（动态共享库）”同病。读者按 §5.1 文件树找 e3/ 会落空——与 e1/e2 冻结产物可对照的口径不一致（E3 证据只剩 report.txt 的三行 PASS）。内容本身真实：本机用 LLVM 18 再生成动态 .ll 并复跑 E3 逻辑，三组数值 24.5/6.0/58.0 全部 bitwise PASS。
- **置信度**：高（目录与 git 跟踪清单直查；E3 数值本地复现通过）。

#### 8. §6 错误 3 把拒收报错定位到 finalize-memref-to-llvm——实际是 memref.alloc 的 op verifier 在解析/验证期就报错，与该 pass 无关
- **原文**：“定位：finalize-memref-to-llvm 的报错文本”
- **依据**：本机 LLVM 18 实测：`%c = memref.alloc() : memref<?x?xf32>` 在 mlir-opt **不带任何 pass**、以及只带 `--canonicalize` 时，都在加载/验证阶段报同一错误：`'memref.alloc' op dimension operand count does not equal memref dynamic dimension count`——这是 op verifier 的约束（动态维度的 alloc 必须提供 shape 操作数），根本轮不到管道第 3 站的 finalize-memref-to-llvm，报错文本也与它无关。“现象／原因／修复”三段本身正确，仅定位张冠李戴。
- **置信度**：高（三种调用方式实测一致，错误文本直读）。

## 【存疑】

#### 1. “静态版 O2 后 fmul=6、phi=1”是作者环境（LLVM 23.1.5＋SLP 向量化）的数字，LLVM 18 对同一冻结 .ll 实测 fmul=18、phi=1
- **原文**：“动态版 `opt -O2` 后 fmul=2、phi=10（vs 静态版 O2 后 fmul=6、phi=1）”
- **依据**：本机 LLVM 18 对冻结 e1-static/out.ll（剥离其无法解析的 gep `nuw` 后）跑 `opt -O2`：fmul=18、phi=1——j(3)×k(6) 全部标量展开、无向量化；同一实验在动态版得 fmul=2、phi=10，与教程数字完全一致。作者侧的“6”与 D125 冻结的 variant-D/stage-5-O2.ll 吻合（该文件恰有 6 条 `fmul <4 x float>`＋6 条 `llvm.vector.reduce.fadd.v4f32`、phi=1）——即 LLVM 23 把展开后的乘法 SLP 向量化成 6 条 4-lane 向量指令，“6”数的是向量指令条数而非标量乘法次数。方向性结论（静态敢展开、动态不敢、phi 4→10 反涨）跨版本成立且对比悬殊（18/1 vs 2/10 或 6/1 vs 2/10），但具体“6”绑定版本与机器且未注明口径；读者在 LLVM 18 上做 §7 必做 3 会得到 18 而非 6（§5.4 实验 B 也未提示）。
- **置信度**：高（本机实测＋D125 冻结产物直读；不质疑作者机器上“6”的真实性——D125 同环境独立测得同值）。

#### 2. 头条代价指标（95→104 行、extractvalue 17→23、+6 处）绑定 LLVM 23 的描述符式 Lowering 形态，LLVM 18 同管道复跑为 92→95 行、extractvalue 14→14（kernel 内 0 处）
- **原文**：“TP4 实测：.ll 95→104 行＋9%、extractvalue 17→23＋6 处”
- **依据**：本机 LLVM 18.1.8 对同一两份 input.mlir 跑同一串七 pass＋translate：静态 92 行/extractvalue 14、动态 95 行/extractvalue 14——kernel 体里零 extractvalue（该版本的参数拆包形态不同：描述符字段以裸标量参数直达循环体，地址计算直接用参数值），"+6 处 extractvalue”现象在该版本完全消失，行差只剩 +3（动态 malloc 尺寸计算）。教程在“前置准备”诚实标注了环境（Homebrew LLVM 23.1.5、macOS arm64；冻结 out.s 亦为 arm64 macOS 汇编，内部自洽），但把 extractvalue 计数当作“动态化代价”的一般度量讲授、未提示该指标随 LLVM 版本剧烈变化——读者换版本复现时 TP2/TP4 的关键数字（95/104/17/23/+6）都对不上。建议在指标处补一句版本口径。
- **置信度**：高（本机全链路复跑＋两版 .ll 逐行比对；不质疑作者环境数字的真实性——冻结产物计数与教程一致）。

#### 3. 诚实声明称 golden“与 kernel 都是 k 序”——与 D124 已确立的“numpy 的 @ 用分块/向量序”相矛盾，且与本句自己的“教学数据的巧合”自相矛盾
- **原文**：“（与 kernel 都是 k 序且数据规模小、bitwise 一致——教学数据的巧合而非口径设计，随机大矩阵需按 D124 的 k 序口径重写）”
- **依据**：若 golden 与 kernel 真是同一求和序，bitwise 一致就是构造性保证而非“巧合”——句内自相矛盾。D124（同仓库）明确写“numpy 的 `@` 用分块/向量序、kernel 用 k 序，顺序不同舍入不同”；numpy 的 f32 matmul 实际派发 BLAS sgemm，求和序实现相关、不可由用户指定。本机复跑验证了后半句的判断：三组教学数据 numpy `A@B` 与 kernel 逐位一致（作者环境与本机两套环境均过——数据巧合），随机 64×64 矩阵 2826/4096 个元素不等（最大差约 5.7e-6，约 1~2 ULP），证实 §6 错误 4 的“随机大矩阵需按 k 序口径重写”。但“都是 k 序”这一机制性归因无法验证且与 D124 矛盾；更稳妥的表述是“kernel 是 k 序、numpy 的序未指明，教学数据下两者恰好逐位一致”。
- **置信度**：中（bitwise 结果与随机失败均为本机实测；numpy 内部求和序不可直接观测，只能依据 D124 与 BLAS 常识否定“都是 k 序”的确定性表述）。

## 【建议】

#### 1. §3.3 把 i 循环的常量 4 当作 k 循环次数 6 的证据——引错了循环
- **原文**：“（`icmp slt %38, 4` 的 4 是常量——unroll pass 能证明循环恰好 6 次）”
- **依据**：`%39 = icmp slt i64 %38, 4`（out.ll L33）是 i 循环（M=4）的边界；k 循环恰 6 次的证据应是 `%48 = icmp slt i64 %46, 6`（L50）。论断本身成立，换成 k 循环那条 icmp 即可。
- **置信度**：高。

#### 2. §5.2 “只差 shape 相关的六处，其余逐行相同”与实际 diff 规模不符
- **原文**：“两个 IR 模板（STATIC_IR/DYNAMIC_IR）只差 shape 相关的六处（签名/dim/alloc），其余逐行相同”
- **依据**：对两模板做逐行 diff：共 14 对差异行（签名 3 行、alloc 1 行、3 条 arith.constant 删除、3 条 memref.dim 新增＋2 行注释、3 个循环边界操作数、3 条 load 类型注、store 类型注、return 类型注）——全部 shape 相关（“变量隔离到 IR 文本”的方法论成立），但“六处”少计近半，且 load/store/return 的类型注也改了，“其余逐行相同”字面不成立。建议改为“差异全部 shape 相关、共 14 行”。
- **置信度**：高（difflib 逐行比对）。

#### 3. 实验 A 的操作对象不明——E2 本就没有 strided，其 gep 前已经出现 extractvalue st
- **原文**：“（删掉签名里的 strided 让 MLIR 用默认动态 stride）——观察 .ll 的 gep 前是不是多了 extractvalue st 字段”
- **依据**：DYNAMIC_IR 的签名是裸 `memref<?x?xf32>`（无 strided 可删），其 out.ll 的 gep 前已存在 extractvalue st（L61/L67/L79）——“观察是不是多了”的现象在 E2 里已经发生。若实验意图是“静态 shape＋动态 stride”的独立对照，基线应是 E1（删 `strided<[6,1]>` 得 `memref<4x6xf32>`）；若意图是与 E2 对比，则该变化已包含在 E2 中。建议写明以哪份 IR 为基线，否则读者会以为 E2 的 gep 前还是常量 stride。
- **置信度**：高（两版 input.mlir 与 out.ll 直读）。

#### 4. “一键复现”实际只在 macOS＋Homebrew LLVM 环境成立
- **原文**：“cd tutorials/week-019/day-128/code && ./run_all.sh    # 5 项，约 20 秒”
- **依据**：dyn_shape.py 第 27 行/e3_verify.py 第 10 行/run_all.sh 第 17 行硬编码 `/opt/homebrew/opt/llvm/bin`；run_all.sh 第 16 行在 `export LLVM_BIN`（第 17 行）之前就引用 `$LLVM_BIN`（`set -u` 下干净 shell 会向 stderr 报 unbound variable，实测确认）；e3_verify.py 使用 macOS 专属链接旗标 `-undefined dynamic_lookup` 与 `libdyn.dylib` 命名（Linux 的 gcc/clang 不接受该旗标）。环境在“前置准备”里如实声明，但“一键复现”处未注明仅限同款环境。
- **置信度**：高（脚本逐行直读＋本机 set -u 行为实测）。

#### 5. “E1 静态基线（D124 原版语义）”的“原版”易误导——E1 同样没有 bias/relu，诚实声明只点名了 E2
- **原文**：“== E1 静态基线（D124 原版语义）==”
- **依据**：D124 的 kernel 语义是 matmul+bias+relu（bias 融 k=0、cmpf/select 收尾）；E1 与 E2 都是纯 matmul（dyn_shape.py 第 29 行注释自认“简化到最小可对照”）。§5.1 诚实声明只说“E2 的动态版没有 bias/relu”，未覆盖 E1；“D124 原版语义”宜加“（shape 相关部分）”之类的限定，避免读者以为 E1 复刻了 D124 的完整语义。
- **置信度**：高（D124 README 与 STATIC_IR 直读）。
