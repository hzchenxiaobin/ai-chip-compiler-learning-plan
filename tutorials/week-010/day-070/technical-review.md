# 第 70 天技术校对报告

校对对象：`tutorials/week-010/day-070/`（README.md、`code/` 全部代码与冻结输出、4 张 SVG）。
方法：在本机完整复跑主实验 `counterexample_lab.py`（39/39）、验收测试 `test_counterexamples.py`（33/33）、5 个 MLIR 探针（LLVM 18.1.8）与本周 7 套测试（286/286，均在临时目录核对、未覆盖冻结产物），并对照学习计划与 week-008/009/011 已有教程核验交叉引用。以下所有实测均指本次复跑结果，与 `code/outputs/` 冻结文件逐行一致。

## 【错误】

#### 1. R3 写集合漂移的 buffer 编号写错：应为 buf0 → buf-1，不是「buf1 变 buf0」

- **原文**：“写集合从 buf1 变 buf0”
- **依据**：按本教程自己的约定（`run_trace`：外部输入 buffer 取负数编号、中间分配从 0 起），R3 图里只有两块 buffer——外部输入 `buf-1` 和 copy 分配的中间缓冲 `buf0`，**图中不存在 buf1**。复跑事件日志：保留 copy 时 relu 原地写 `buf0`（`%3 relu 原地写 buf0`）；消除 copy 后 relu 原地写 `buf-1`（`%3 relu 原地写 buf-1 ... ← 写进了外部输入！`）。即写集合漂移方向是 **buf0 → buf-1**，且被污染的外部输入是 buf-1 而非 buf0。README §3.2 与 §5.3 自己写的是正确口径（「消除后 relu 写进 buf-1（外部输入）」「输入被写=[-1]」），与本句自相矛盾。错误源头是 `counterexample_lab.py` 里 R3c 的 check 名「写集合漂移：buf1 → buf0（外部输入）」——其断言条件本身正确、打印的细节「[] -> [-1]」也与标签矛盾——该错误编号又被 `counterexamples.md`（「写集合从 buf1 漂移到 buf0」）和 `images/01-overview.svg`、`images/03-counterexamples.svg`（「实测：写集合 buf1→buf0」）原样复述。
- **置信度**：高。已用复跑日志逐行核实；不修改任何文件，仅指出错误及传播面。

#### 2. 「第 11 周要做的常量折叠、死代码消除」与学习计划不符

- **原文**：“第 11 周要做的常量折叠、死代码消除、Cost Model 全都要先过今天这一关”
- **依据**：学习计划（`AI芯片编译器学习计划.md`）第 11 周（第 71–77 天）的主题是「融合收益与代价模型」：计算量与访存量、融合减少的流量、融合的资源代价、合法性与收益性分离、构造不融合案例、简单 Cost Model 集成、复盘；已生成的 `tutorials/week-011/` 七篇教程标题也全部是融合／Cost Model 主题，**没有常量折叠和死代码消除**。计划中常量折叠在第 4 周（第 23 天）和第 7 周（第 47 天），死代码消除在第 4 周（第 25 天）——都是本周（第 10 周）之前已完成的内容，不是「第 11 周要做的」。三项里只有 Cost Model 属于第 11 周。
- **置信度**：高。已逐条核对计划原文与 week-011 七篇教程标题。

#### 3. 「第 57 周公式」是不存在的周次引用

- **原文**：“它是第 57 周公式里 strides 取负值的视图”
- **依据**：整个学习计划共 168 天／24 周，不存在「第 57 周」。偏移公式出自**第 9 周的第 57 天**（README 前文自己也写「第 9 周的偏移公式 `物理偏移 = offset + Σ idx×stride`（Day 57）」，`tutorials/week-009/day-057/` 标题即「逻辑 Shape 与物理布局」，其中明确讨论了 stride 取 0／负值的情况）。应改为「第 9 周（Day 57）的公式」。该练习的其余技术结论经 numpy 复核均成立：`A[:, ::-1]` 不是 transpose；`flip(flip(x))` 值等价且仍共享存储（可消除，但受 R6 同款多使用者约束）；2 维负 stride 视图上的 `reshape(6,)` 无法做成单一 stride 的视图、numpy 返回拷贝。
- **置信度**：高。周次错误确凿；为交叉引用错误，不影响该练习其余内容。

## 【存疑】

#### 1. 「transpose/reshape 是 0 字节的记账戏法」过于绝对，与本教程自己的 R5 数据冲突

- **原文**：“在「视图世界」（框架前端，transpose/reshape 是 0 字节的记账戏法）”
- **依据**：本教程自己的模型与实测并非如此：`run_trace` 的 view 模式中 **reshape 仅在输入 C-连续时才是 0 字节**（`test_counterexamples.py` A4：「非连续输入上的 reshape 是拷贝（48B）」），而 R5 的「视图世界」traffic=96B 恰恰来自两个 reshape 各拷 48B——若 reshape 在视图世界恒为 0 字节，R5 的 2×2 就只剩一格了。真实框架同理：numpy／PyTorch 的 `reshape` 在无法做成视图时返回拷贝（只有 `view` 会报错）。该括注作为「视图世界」的一般定义过于绝对，且与后文 R5 的实测数字表面冲突；对 4-op 链本身（48B/1）数字无误，因为该链上 reshape 的输入恰为连续。建议限定为「transpose 恒为视图；reshape 在输入连续时为视图」——这也是 `run_trace` 文档字符串里已写对的口径。
- **置信度**：高（不一致现象确凿；因教程后文有正确口径、本句是对特定链的概括，归为存疑而非错误）。

#### 2. 「先跑 Verifier（shape 对不上当场报错）」对本条所引的 R7 现场并不成立

- **原文**：“先跑 Verifier（shape 对不上当场报错）”
- **依据**：错误 4 的现象是 R7（reduce 传播后 shape (3,1)→(1,2)）。但复跑与代码核实：R7 诱人改写后的图 `arg(2,3)→T(1,0)→reduce_sum(axis=0)` **自身完全合法、mini Verifier 零报错**——主实验 R7a 的断言条件本身就是 `len(g2.infer_shapes()[1]) == 0`，靠的是「与原式 return shape 对拍」才发现 (1,2)≠(3,1)；同一条 PASS 的 check 名却写着「Verifier 拦截」（冻结输出 `outputs/counterexample_lab.txt` 第 235 行），名实自相矛盾。R2 型错误（错误 3 的 `[V1]`，perm 对 rank 不合法）确实被 Verifier 当场拦下，R6 型则根本没有 shape 问题。真实 MLIR 中因函数签名带返回类型，这类改写会被 verifier 以类型不匹配拦下——所以该建议在真实编译器语境下成立，但在本教程 mini IR 的 R7 现场抓不到。建议把 R7a 的 check 名改掉，并把定位建议写成「R2 型 Verifier 当场拦；R7 型要和原函数签名/输出 shape 对拍」。
- **置信度**：中。已核实 mini 侧行为与断言条件（确定）；「真实 MLIR 会拦」基于函数签名类型检查的通用机制，未在本机单独构造完整复现。

#### 3. 「in-place 逐元素 kernel 正是 bufferization 之后的世界」与 one-shot-bufferize 默认行为不完全一致

- **原文**：“这正是 bufferization 之后的世界”
- **依据**：本机 LLVM 18.1.8 实测：对「tensor 输入的元素级 `linalg.generic`」跑 `mlir-opt --one-shot-bufferize`（默认参数，及加 `bufferize-function-boundaries`），结果是**新分配输出缓冲、out-of-place 写**（`%alloc = memref.alloc()` 后 `linalg.generic ... outs(%alloc)`），并不会把元素级算子写进输入 buffer。MLIR 的 bufferization 决定的是「张量世界→缓冲世界」及别名／in-place 与否（由冲突分析决定，何时允许 in-place 有明确条件），「逐元素算子原地写输入」更像后端 kernel 调度（或带别名分析的 buffer 复用决策）的结果，不是 bufferization 的默认必然形态。教程后文 R3 守卫清单里「bufferization 里 `bufferizesToMemoryWrite` 分析做的就是别名判断」的说法是对的，与本句的笼统表述有出入。仅在本机验证了上述单例（outs 为 `tensor.empty` 的元素级 generic），one-shot 在 outs 可复用时确可 in-place，故不建议按「错误」处理，建议措辞收紧为「bufferization 之后，in-place 与否要靠别名分析决定」。
- **置信度**：中。已实测默认参数单例；one-shot-bufferize 其他配置下的行为未逐一验证。

## 【建议】

#### 1. 「主实验约 1100 行」与实际行数不符

- **原文**：“主实验约 1100 行”
- **依据**：`wc -l code/counterexample_lab.py` 实测 1397 行（含文档字符串与注释），「约 1100 行」偏差约 27%。属计量性小错，不影响技术内容，建议改为「约 1400 行」或删去行数。
- **置信度**：高。

#### 2. R1 处宜补一句「f16 往返丢位是值相关的」，避免误读为必然

- **原文**：“roundtrip 与原值逐位相等的元素：0/6（f16 只有 10 位尾数）”
- **依据**：「0/6」是随机输入（`standard_normal×3`）的实测事实，无误；但丢位并非对一切值成立——恰能被 f16 精确表示的值（0.5、1.0、2 的幂、小整数等）往返不丢位，验收测试 B1 写「12 元素几乎全变（≥10/12）」也默认了这一点。初学者若把「f32→f16→f32 必然变值」当成普适规律，换一组含整数的输入会对不上。建议补一句「丢位是值相关的；守卫 src==dst 防的是『可能丢位』，不是『必然丢位』」。这不影响 R1 反例与守卫本身的正确性。
- **置信度**：高（f16 可精确表示的值往返不变是 IEEE 754 半精度的确定性质）。
