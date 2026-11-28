# 第 130 天技术校对报告

审阅对象：`tutorials/week-019/day-130/README.md`、`code/`（fallback.py、run_all.sh、specialize.py、dyn_shape.py、gen_images.py）、`code/outputs/`（report.txt 与冻结产物）、`images/`（3 张 SVG）。核对方式：在临时目录用 mock 动态／特化库复跑 fallback.py 的完整 Python 控制流（E301×4／回退／miss／E303 路径及 stats、events、stderr 行为均与冻结 report.txt 逐字一致）；逐字比对 README 输出块与 report.txt；逐元素解析 3 张 SVG 的坐标与文字；对照本机 torch 2.7.1 源码、TVM v0.17.0 与 2026-11 主线源码；跨天核对 D118／D120／D122／D127／D128／D129（积分卡 5/5、8/8、9/9 与"fmul 2→18（9 倍）"均与各日冻结产物一致，本日"动态版慢 9 倍 fmul 视角"经 out-O2.ll 实数 18/2=9 核实无误）。以下"行号"指 README.md 的行号，"fallback.py:N"指该文件第 N 行。

## 【错误】

#### 1. "FallbackDetector" 不是 PyTorch 的真实组件
- **原文**：“PyTorch 2.x：compile 失败→eager 解释器＋FallbackDetector 计数”
- **依据**：对本机 torch 2.7.1（/opt/buildtools/Python-3.11.4/lib/python3.11/site-packages/torch）整个包 grep "FallbackDetector" 零命中；grep.app 公共代码搜索该词的全部命中（headroom 压缩库、sentry 前端、gradle 插件等）无一来自 pytorch。PyTorch 真实存在且可对号的机制是：torch._dynamo.utils.counters（本机已验证存在，graph break／frames 计数）、TORCH_LOGS=graph_breaks 日志、Inductor 的 FallbackKernel／extern kernel（torch/_inductor/ir.py:6438，torch/_inductor/lowering.py 的 fallback_handler）。同一错误还出现在 3.3 节第 49 行（"PyTorch 的 eager（底）＋FallbackDetector（可见）＋异常传播（出口）"）、第 8 节验收项以及 images/03-example.svg 的"FallbackDetector 计数"文字——修正需同时改正文与该 SVG。
- **置信度**：高（torch 2.7.1 已实测；未能逐一核查所有 2.x 小版本，但未发现任何该名称曾存在的证据，特征符合虚构 API 名）。

#### 2. "真机输出"块与冻结 report.txt 不一致，且含当前代码不可能产生的行
- **原文**：“3D 输入: 拒收 ✓（E301: A.ndim=3, B=2（只支持 2D））”
- **依据**：fallback.py:81 的模板固定为 f"A.ndim={A.ndim}, B.ndim={B.ndim}（只支持 2D）"，永远输出 "B.ndim=2"；冻结 report.txt 第 12 行为 "A.ndim=3, B.ndim=2（只支持 2D）"；在临时目录 mock 复跑同样得到 "A.ndim=3, B.ndim=2"。README 第 120 行声称这是 "`./run_all.sh` 的真机输出"，但 "B=2" 形态不可能由当前代码产生，属转写错误。另外第 123 行时间戳 "2026-11-14 22:55" 与冻结 report.txt 的 "22:16" 不一致（可能是另一轮运行，但与唯一存档的产物不符）。
- **置信度**：高（三种途径交叉验证）。

#### 3. 目录树声称 outputs 内含 libdyn.dylib，但仓库实际没有（*.dylib 被 .gitignore）
- **原文**：“├── e2-dynamic/           # 动态版（含 libdyn.dylib）”
- **依据**：ls 与 git ls-files 均显示 outputs/e2-dynamic、outputs/spec-4x6x3 只含 .mlir/.ll/.s 文件，无任何 .dylib/.so/.o；仓库根 .gitignore 明确忽略 *.dylib、*.so、*.o。因此 5.1 的"产物复用／D129 的两份产物"在克隆仓库后不成立——首次运行必然走 fallback.py 的重建分支（依赖 /opt/homebrew/opt/llvm/bin，仅 macOS Homebrew 环境可用，Linux 读者无法复现）。另外实际存在目录树未列出的多余已入库目录 code/outputs/outputs/e2-dynamic/（错误工作目录下运行的残留产物），同样与"准备文件"的树不符。修复只需改树注（如"含 libdyn.dylib（首次运行自动重建，仓库不保存二进制）"）并清理多余目录。
- **置信度**：高（仓库状态直接核实）。

#### 4. 图 1 的箭头路由与图注声称的主链不符
- **原文**：“→异常（红箭头下跳）→③动态兜底（E302 回退/W301 警告）→失败→④上抛（E303）”
- **依据**：逐元素解析 images/01-overview.svg：顶部主链只有 ①→② 与 ②→③（miss）两条黑箭头（path 起点 285→327、565→609），③"动态兜底"（x 624~844）与④"上抛"（x 870~1020）之间没有任何箭头，图注声称的 "③→失败→④上抛" 这条边在图中不存在；两条红色下落箭头的落点也整体偏左一级——②的"异常"箭头（终点 x≈454）落在"特化执行"详情卡（x 305~530，描述正常路径的卡）上方，③的"失败"箭头（终点 x≈736）落在"E302/W301 回退"卡（x 550~775）而非"E303 上抛"卡（x 795~1020）。按图读链会得出"②的异常流向特化执行卡、③的失败流向 E302 卡"的错误流向。需重新生成图 1（补 ③→④ 边并把红箭头落到 E302 卡与 E303 卡）。
- **置信度**：高（SVG path 坐标逐项核对）。

#### 5. stats 的 rejected 计数在 Runtime 内从未自增，"四个计数是健康指标"与代码不符
- **原文**：“stats 的四个计数（hit/miss/fallback/rejected）是健康指标”
- **依据**：fallback.py 全文只有两处涉及 rejected——第 66 行初始化 stats 键、第 197 行打印 "rejected={n_reject}"；_validate（79~87 行）与 run()（89~123 行）都没有 stats["rejected"] += 1，E301 拒收路径只 raise。在临时目录 mock 复跑确认：同一 Runtime 实例连续拒收 2 次后 rt.stats 仍为 {'rejected': 0}；report.txt 里 E2 段的 "rejected=4" 来自 main() 的局部变量 n_reject（fallback.py:188~196，调用方统计），不是 stats。因此"监控的 hook 从 stats 接"对 rejected 不成立——按图索骥会得到永远为 0 的指标。修复任选其一：在 _validate 拒收前加 self.stats["rejected"] += 1，或把正文改为"rejected 由调用方统计"。
- **置信度**：高（代码路径与实测双重验证）。

## 【存疑】

#### 6. "compile 失败随时回 eager" 对 torch.compile 默认行为的表述过于绝对
- **原文**：“PyTorch 2.x 能在生产环境用 torch.compile 的底气就是"compile 失败随时回 eager"”
- **依据**：torch 2.7.1 的 torch/_dynamo/config.py:180：suppress_errors 默认 False，注释原文 "Suppress errors in torch._dynamo.optimize, instead forcing a fallback to eager"——即"出错回 eager"需显式开启（TORCHDYNAMO_SUPPRESS_ERRORS）；torch/_dynamo/convert_frame.py:1236-1266：只有 Unsupported（能力缺口→graph break）是 soft fail 自动回 eager，其余异常在 not config.suppress_errors and not soft_fail 时直接 raise。即自动回退默认只覆盖"不支持的结构"（graph break）与算子级 fallback（Inductor extern/FallbackKernel），真正的编译错误默认上抛。建议改为"不支持的结构自动断图回 eager；硬错误默认上抛（可选抑制后回退）"。
- **置信度**：高（对 2.7.1 源码逐行核实）；不同 2.x 小版本细节可能调整。

#### 7. TVM 的回退描述是"经典 TVM"，且个别术语查无出处
- **原文**：“TVM：OOM→自动降 tile 重试或 fallback schedule”
- **依据**：已核实 TVM v0.17.0 存在 autotvm 的 FallbackContext（python/tvm/autotvm/task/dispatcher.py:372，无调优记录时提供 fallback 配置——"fallback schedule"有据）与 tuner 失败试验后继续搜索的机制（python/tvm/autotvm/tuner/tuner.py:53，error_ct_threshold=150——"失败换配置重试"有据）；但 2026-11 的 TVM 主线（tags 至 v0.27.0/v0.28.dev0，python/tvm 目录下已无 autotvm 与 meta_schedule）已移除该体系，描述需注明版本语境。"OOM→自动降 tile 重试"是对"失败试验标记无效、搜索换配置"的演绎而非文档化机制名；图 3 中"（Ansor 的约束收缩）"在 Ansor 论文与 TVM 文档中均查不到对应术语。建议改为"调优试验失败换配置重试＋无调优记录时用 fallback 配置（经典 AutoTVM；主线已重构）"。
- **置信度**：中（FallbackContext 与 error_ct 机制已核实；"降 tile""约束收缩"两处措辞未找到出处，疑为不准确转述，无法进一步验证）。

#### 8. "kernel 内的检查发生在越界访问之后（或每循环都查）" 作为一般规律有反例
- **原文**：“kernel 内的检查发生在**越界访问之后**（或需要额外指令每个循环都查——性能灾难）”
- **依据**：反例：BLAS 家族（OpenBLAS/MKL）恰在 kernel 入口做一次 O(1) 维度检查并经 xerbla 报错返回——既不晚于越界访问、也不在每个循环里，是生产数值库的标准做法且代价可忽略。该论断在 minic 的具体架构下成立（MLIR 生成的 kernel 不含检查、经 ctypes 调用时 C 层段错误 Python 接不住，所以必须在 Python 调用边界 fail-fast——这一结论正确），但写成普适因果（"kernel 内检查必然太晚或太慢"）会误导。建议限定语境或改述为"本教学 kernel 没有入口检查，越界即段错误且 Python 接不住"。
- **置信度**：高（对一般性论断有明确反例；minic 场景下的结论无误）。

## 【建议】

#### 9. W301 警告默认被 quiet=True 静音，实测证据里没有 W301
- **原文**：“③**E302/W301 回退**：特化 kernel 执行异常→动态版重试→结果正确＋性能降级警告——实测注入坏 kernel 后回退 PASS”
- **依据**：fallback.py:125 类属性 quiet = True，run() 第 109 行 if not self.quiet 才打印 W301；冻结 report.txt 的 E3 段没有 W301 行；在临时目录 mock 复跑同样确认 quiet=True 时 stderr 为空、quiet=False 时才打印 "[W301] 回退发生（性能降级）：(4, 6, 3) 特化异常→动态重试"。E302 事件与 stats.fallback 的可观测性无误，但"性能降级警告"这一项在默认配置与实测记录中都不出现（run_all.sh 的 "[PASS] E3 回退路径（E302→W301 降级重试）" 标签也随之言过其实）。建议 E3 用例设 rt2.quiet = False 或在正文说明默认静音。
- **置信度**：高（代码路径与实测双重验证）。

#### 10. "零维"术语与 numpy 的 0-d array 概念冲突
- **原文**：“内维不匹配/dtype 非 f32/3D 输入/零维，四种实测全部拒收”
- **依据**：测试用例 np.zeros((0,6)) 的 ndim=2，是"含零尺寸维度（空矩阵）"；numpy 语境的"零维数组"专指 shape ()、ndim=0 的对象——真的传 0-d 标量会被 fallback.py:80 的第一条 ndim 检查拦下并报 "A.ndim=0"。术语混用会让初学者把 (0,6) 误当成 0-d 数组；建议改称"零尺寸维度／空矩阵"。不影响代码行为与拒收结论。
- **置信度**：高。

#### 11. E4 标签"两层全崩"与实测路径不符
- **原文**：“E303 上抛（两层全崩→结构化 RtError——E4 实测）”
- **依据**：fallback.py 的 E4 用例 rt3 是全新 RuntimeWithFallback 且未注册任何特化 kernel，run() 直接落入③动态层失败→E303，特化层从未执行；实测覆盖的是"动态层失败→结构化上抛"，不是"特化层先崩、动态层再崩"的完整两级路径。E303 语义（动态失败上抛）本身演示无误，标签易让读者以为测了两级连续失败。
- **置信度**：高。

#### 12. "动态版 kernel 与特化版同时编译"与事实有出入
- **原文**：“动态版 kernel 与特化版**同时编译**——运行期没有"现场编一个底"的余裕”
- **依据**：minic 里两者分别在 D128 与 D129 编译（本日 outputs/e2-dynamic 与 spec-4x6x3 正是两个批次的产物，并非"同时"编译）；PyTorch 的底（eager 解释器）也不是编译产物。作为跨系统共性，更稳妥的表述是"底必须在运行前就已存在（预编译或预置实现）"。方向性结论（运行期没有现编一个底的余裕）不变。
- **置信度**：高。
