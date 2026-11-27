# 第 4 天技术校对报告

审阅对象：`tutorials/week-001/day-004/`（README.md、`examples/tensor-desc/` 全部源码、5.3/5.4/第 6 节全部真实输出、images/01～03 三张 SVG）。
核实方式：在本机（与教程标称完全一致的环境：Linux aarch64 · Ubuntu 20.04 · g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0 · NumPy 1.26.4）重新构建并运行观察程序、ctest、5.4 实验、三个错误复现；对 PyTorch 2.5.0 与 MLIR 官方文档/源码核对涉及外部框架的论断。运行均在临时目录完成，未触碰仓库内冻结的 build 产物。

## 【错误】

#### 1. “50 条断言”与实际数量不符：测试文件里是 51 条 assert
- **原文**：“4. 写出 `TensorDesc`，用 50 条断言和三个视图的运行证据验收。”
- **依据**：`tests/test_tensor_desc.cpp` 实际含 **51** 条 `assert(` 语句（本机 `grep -c "assert("` 与逐条清点均为 51），行内圆圈编号 ①～㊿ 共 50 个编号但 ㊾ 被用了两次（第 117、121 行），即编号本身也错位；程序末尾的 "all 50 assertions passed" 是硬编码字符串，与真实断言数不符。同一“50 条”口径还出现在 README 第 6 行（今日产出）、第 289 行（“按概念分组写了 50 条断言”）、第 387 行（输出文本）、第 548、552 行。修正方式二选一：删掉多余的一条断言（如第 10 组中重复编号的那条），或把所有“50”改为 51 并同步改打印文案。已实跑确认：构建 6 步、ctest 通过、输出与 README 逐行一致，唯独计数不实。
- **置信度**：高（在同一环境重新构建、运行并逐条清点核实）

#### 2. “负 stride 在 PyTorch 里是合法的”不成立（用户可达接口全部拒绝）
- **原文**：“本类暂不支持负 stride（构造函数会拒绝），PyTorch 里它是合法的。”
- **依据**：核对 PyTorch 2.5.0 源码：① `aten/src/ATen/native/Resize.h` 的 `setStrided()` 明确 `TORCH_CHECK(val >= 0, "as_strided: Negative strides are not supported at the moment, …")`——`torch.as_strided` 传负 stride 直接抛错；② `aten/src/ATen/TensorIndexing.h` 的 `applySlice()` 要求 `step > 0`（"step must be greater than zero"，旁注 TODO: implement negative step），即 `x[::-1]` 抛错；③ 官方文档明确 “torch.flip makes a copy of input's data. This is different from NumPy's np.flip, which returns a view”。真正允许负 stride 的是 **NumPy**：本机验证 `np.arange(6,dtype=np.int32)[::-1].strides == (-4,)` 且为视图。PyTorch 的 TensorImpl 内部表示可以存负值（个别 C++ 内部路径），但所有用户可达 API 都拒绝构造。建议把对比对象改成 NumPy，例如：“NumPy 里它是合法的（`a[::-1]` 得到负 stride 视图）；PyTorch 的用户接口同样拒绝负 stride——这是两大框架少见的分歧点。”
- **置信度**：高（PyTorch 2.5.0 源码与官方文档逐条核对，NumPy 本机实测；不确定点：极早期 PyTorch 版本未逐一考证，但该 as_strided 检查长期存在）

#### 3. 练习预期答案错误：按练习自给的 slice 语义，`slice(0,1,2)` 与 E 不是“完全一致”
- **原文**：“`permute({1,0})` 应当与 B 完全一致，`slice(0,1,2)` 应当与 E 完全一致。”
- **依据**：按练习第 2 条自己给出的语义（`shape[dim]=end-start`、`storage_offset += start×strides[dim]`、strides 不变），`A.slice(0,1,2)` 得到 **shape=(1,3) strides=(3,1) offset=3**（已用教程源码实现并运行确认）；而 E 是 **(3,)/(1,)/offset=3**（第 1 节表格、5.2 测试注释、5.3 真实输出三处一致）。两者访问同一批元素（`(0,j)` 与 `E(j)` 同落 3、4、5），但 shape、strides 都不同，`to_string()` 不相等——读者若照“完全一致”写 `assert(s.to_string() == e.to_string())` 必然失败。这对应 NumPy/PyTorch 里 `A[1:2,:]`（保留长度 1 的维）与 `A[1,:]`（去维）的差别。`permute({1,0})` 半句是对的（得 (3,2)/(1,3)/0，与 B 逐字段相同）。建议改为：“`slice(0,1,2)` 覆盖的元素与 E 相同——它等于给 E 再套一个长度 1 的第 0 维（(1,3)/(3,1)）”，或改对照对象为 `A[1:2,:]`。
- **置信度**：高（用教程自己的公式实现 slice 并与 E 逐一比对，`identical? no`）

#### 4. 错误一的“定位”启发式在自家复现输出上对不上数
- **原文**：“- 定位：打印 desc 和存储大小，第一个越界点的位置除以 itemsize 约等于你想要的步长，就是单位错了。”
- **依据**：按 6.1 的真实输出，第一个越界点是 `wrong(0,2)` → 元素 8；8 ÷ itemsize(4) = 2，而“想要的步长”是 (3,1) 里的 3 或 1，2 与谁都约不上。真正成立的两个诊断是：① 越界位置 ÷ 本该访问的位置 = itemsize：8 = 2×4，且 (1,0)→12 = 3×4、(1,1)→16 = 4×4、(1,2)→20 = 5×4，全部吻合；② 把误传的（字节）stride 除以 itemsize：12/4=3、4/4=1，恰好还原想要的元素步长 (3,1)。建议把被除数从“第一个越界点的位置”改成“你传进来的 stride”，或改述为“越界位置除以本该访问的位置≈itemsize，就是单位错了”。
- **置信度**：高（对教程自身输出逐点核算；不确定点：若作者本意即①或②，则只是“步长”一词指代错了对象，结论方向没错）

## 【存疑】

#### 1. “不连续 ⇒ 通用寻址循环或 materialize”是穷举式表述，漏掉了常量跨步 DMA 这条常见出路
- **原文**：“**不连续 ⇒ Lowering 要么生成带通用寻址的循环（慢），要么先 materialize（把数据真地拷成连续，花时间和空间）**”
- **依据**：对 CPU 后端这一归纳基本成立，但本课程面向 AI 芯片编译器：常量 stride 的非连续数据可以由支持跨步搬运的 DMA 一次完成、无需 materialize。MLIR 自己就建模了这件事——官方 Dialects/MemRef 文档中 `memref.dma_start` 可选地接受 `stride` 与 `num_elements_per_stride` 操作数，按固定步长分块搬运；主流加速器 DMA 普遍支持 2D/跨步传输。作为第 4 天的简化可以接受，但“要么…要么…”的表述与第 94 天 Tiling 将遇到的跨步搬运相抵触，建议补半句“若硬件 DMA 支持常量跨步，也可以直接跨步搬运而不必拷成连续”。
- **置信度**：中（`memref.dma_start` 的跨步语义已核对 MLIR 官方文档；各加速器 DMA 能力不一，未逐一验证具体硬件）

## 【建议】

#### 1. 在教程标称的 aarch64 环境下，示例工程构建会报 5 条 -Wformat 警告
- **原文**：“构建脚本和前三天同款（C++17、`-Wall -Wextra -Wpedantic`、`enable_testing`），只有目标名不同（完整文件在 `tutorials/week-001/day-004/examples/tensor-desc/`）。”
- **依据**：在本机（aarch64、g++ 9.4.0，与第 5 节标称环境一致）全新构建：`src/main.cpp:23` 的 `dump_2d` 把 `int64_t`（aarch64 上是 long）直接传给 `%lld`，产生 5 条 `-Wformat` 警告。构建仍是 6 步、运行输出与 README 逐行一致，README 也没有“零警告”的表述，故不算错误；但 `main.cpp` 其他调用点都写了 `static_cast<long long>`，唯独此处漏了，跟着敲一遍的读者会看到教程没提的警告。建议补 cast，或在正文提一句“aarch64 上会有 5 条无害的格式警告”。
- **置信度**：高（本机复现，警告行号与条数已核对）

#### 2. `is_contiguous` 与 PyTorch 在 numel==0 上有边界差异，宜加半句说明
- **原文**：“**尺寸为 1 的维度跳过**（走一步也走不出它，步长是多少都无所谓——PyTorch 的规则）”
- **依据**：size-1 跳过、offset 不参与，均与 PyTorch 2.5.0 `c10/core/Contiguity.h` 的 `_compute_contiguous` 逐行一致（已核对源码）。但 PyTorch 还有一条前置短路：`numel == 0` 时无条件返回 contiguous；本类没有这条。例如 shape=(2,0)、strides=(5,1)：PyTorch 判“连续”，本类判“不连续”。当天所有示例都不含 0 尺寸维度，不影响本日正确性；但头文件注释与正文都宣称“PyTorch 规则/语义”，第 57 天要拿 PyTorch 对照，届时会撞上这个差异。建议在 3.3 或头文件注释里补半句“PyTorch 对空张量（numel==0）一律视为连续，本类未实现这条特例”。
- **置信度**：高（PyTorch 2.5.0 源码已核对）

#### 3. 值得补一句：非连续视图真正需要的存储可以大于 `nbytes()`
- **原文**：“这两个函数是第 6 天 `Buffer` 分配内存、第 99～101 天内存规划的直接输入。”
- **依据**：`nbytes = numel × itemsize` 只在连续布局下等于“实际占用”。对 (2,3)/(4,1)/offset=0 的切片，触达的最大元素是 `1×4 + 2×1 = 6`，即底层需要 7 个元素（28 字节），而 `nbytes()` 只报 24；把 `nbytes()` 当作“这块视图要多少存储”会算小。PyTorch 专门用 `computeStorageNbytes`（按 sizes+strides 求所需存储，见 `aten/src/ATen/native/TensorShape.cpp` 的 `set_` 路径）区别于 `numel × itemsize`。既然教程把 `nbytes()` 定位为内存规划的输入，建议补一句“非连续视图真正跨越的存储 = 最大触达偏移 + 1，可大于 nbytes()”——这也是错误一里“nbytes() 对 stride 毫无感知”的另一面。
- **置信度**：高（算术核算 + PyTorch 源码佐证）

#### 4. stride=0／重叠视图的写侧风险只字未提
- **原文**：“它可以是 0（广播视图，同一格读多遍）”
- **依据**：3.2 节提到 stride 可为 0，但只讲了读语义。写侧的风险是：多个下标映射到同一格（重叠视图）时，原地操作是未定义行为——PyTorch `as_strided` 官方文档原话：“If the generated view is ‘overlapped’ … the behavior of inplace operations on this view is undefined (and might not throw runtime errors)”。当天代码只读不写，可以不展开；但第 6 天 `Tensor` 一旦支持写入就会踩到。建议在类比边界处加一句“读是免费的，写要小心：重叠视图（含 stride=0）上的原地写是未定义行为，第 6 天会再遇到”。
- **置信度**：高（PyTorch 官方文档原文引用）

#### 5. “（维数一致、无非负数）”按字面读与构造函数行为相反
- **原文**：“（维数一致、无非负数）”
- **依据**：构造函数实际检查的是 shape 各维、strides、storage_offset 均不允许**负**值（`TensorDesc.cpp` 第 41～53 行），即“无负数”。“无非负数”的字面意思是“没有非负数”（全是负数），与代码本意相反，疑为漏字的笔误。一字之改即可，但按字面较真的初学者会读反。
- **置信度**：高（对照 `TensorDesc.cpp` 构造函数逐条核对）
