# 第 58 天技术校对报告

校对方式：完整阅读当天 README、`code/` 下全部代码与 `code/outputs/` 全部冻结输出；在本机（与教程声明环境一致：Python 3.11.4 / numpy 1.26.4 / torch 2.7.1+cpu / Ubuntu LLVM 18.1.8 / aarch64）临时目录复跑 `run_all.sh` 全流程（默认 PATH 下 20/20＋20/20 全部通过、cpu-runner 输出两个 23、Verifier 拒绝 bad_layout.mlir），并针对存疑论断单独做了最小复现实验。未修改任何教程原文、代码或冻结输出。

## 【错误】

#### 1. “错误 1”的 torch 修复建议用在转置视图上会静默得到第三种布局

- **原文**：“- **修复**：需要物理连续就显式 `np.ascontiguousarray`（或 torch 的 `.contiguous(memory_format=torch.channels_last)`），把隐式行为变成显式语句；写编译 Pass 时，把"插入 transpose"和"插入真实重排"当成两档不同代价的决策。”
- **依据**：`contiguous(memory_format=torch.channels_last)` 总是按“当前张量第 1 维是 C”来排布。对原始 (N,C,H,W) 张量调用确实得到物理 NHWC（实测 strides (32,1,16,4)，正确）；但“错误 1”的场景是手里已拿着转置视图，对逻辑维已是 (N,H,W,C) 的视图调用它，实测（torch 2.7.1+cpu，本机）得到 strides (32,1,8,2)，物理顺序为 0,4,8,12,16,20,24,28,1,5,…——既不是 NCHW 也不是 NHWC 的第三种摆法；且 `torch.equal` 返回 True，错误完全静默。正确做法是对视图用普通 `.contiguous()`（实测 strides (32,16,4,1)，物理顺序 0,8,16,24,1,9,… 与教程 `nhwc` 一致），或对原始 NCHW 张量用 `x.to(memory_format=torch.channels_last)`。句中未注明调用对象，按“错误 1”场景字面执行会得到错误结果。
- **置信度**：高（语义在本机 torch 2.7.1 上实测复现；唯一保留是对“句意本就指对原始 NCHW 张量调用”的善意解读，但教程未写明，初学者极易踩中）。

#### 2. run_all.sh 在 mlir 工具已加入 PATH 的机器上第 5 步失败且被“exit=0”掩盖

- **原文**：“`run_all.sh` 先打印环境（本机实测：Python 3.11.4、numpy 1.26.4、Ubuntu LLVM 18.1.8 的 `mlir-opt` 与 `mlir-cpu-runner`、Linux aarch64），再依次跑 Python 实验、验收测试、MLIR 解析与折叠、LLVM 降级加真实执行、错误注入。没有 `mlir-opt` 也能跑前两步。”
- **依据**：脚本第 13–24 行：`MLIR_RUNNER` 缺省为裸名 `mlir-cpu-runner`，`command -v` 找到时不替换成完整路径，于是 `LLVM_LIB="$(dirname "$MLIR_RUNNER")/../lib"` 变成相对当前目录的 `../lib`，`--shared-libs` 指向不存在的路径。本机复现（`PATH=/usr/lib/llvm-18/bin:$PATH`，即 MLIR 用户常见的自装 LLVM 场景）：第 5 步输出 `Failed to create MemoryBuffer for: ..././../lib/libmlir_runner_utils.so`、`JIT session error: Symbols not found: [ printF32, printNewline ]`，`layout_orders_exec.txt` 为空，但随后仍打印 `exit=0`——因为 `"$MLIR_RUNNER" ... | tee ...` 后取的 `$?` 是管道末尾 `tee` 的退出码（脚本只有 `set -u` 没有 `pipefail`）。即读者看到的“真实执行”环节实际失败却被报告成功。修复：`command -v` 命中时用其输出替换 `MLIR_RUNNER`（或统一 `command -v mlir-cpu-runner || fallback` 后取绝对路径），并加 `set -o pipefail`。注：按教程文档的默认 PATH（mlir 工具不在 PATH、走 fallback 分支）本机复跑全部通过，冻结输出真实可信，此错误仅在“mlir 工具已在 PATH”的环境触发。
- **置信度**：高（两种 PATH 场景均在本机复现，失败与掩盖行为均直接观察）。

#### 3. 必做练习第 4 步的预期结果与实际行为不符

- **原文**：“4. 运行验证：给 `test_layout.py` 加两三条断言，预期产出新的 `[PASS]`，总数从 20/20 涨上去。”
- **依据**：按练习字面执行（只把第 69 行 `build(1, 4, 2, 4)` 改成 `build(1, 8, 2, 3)`、再新增断言），本机实测 `test_layout: 12/20 checks passed`，8 条旧断言 FAIL（A 组两条 strides、P1-NHWC、P2-NCHW、P3 两条、缓存行、NHWC 平铺全部因硬编码期望值失效）；另有若干条旧断言“侥幸通过”——例如 P1 检查用 `range(4)` 构造下标，W=3 时 w=3 已越界，但 `formula_offsets` 只做算术不访问内存，仍算出 [0,1,2,3] 判 PASS。要得到“总数涨上去且全绿”，必须同步改写约 8 条旧断言的期望值，而练习只说“加两三条断言”。应改为提示“原有期望值需按手算结果同步更新”，或把期望值参数化。
- **置信度**：高（已在本机按字面复现，12/20、8 FAIL）。

## 【存疑】

#### 1. “TensorFlow、GPU Tensor Core 和昇腾算子偏好 NHWC”三类并列过于简化

- **原文**：“2. **今天进入第一场实战**：NCHW 与 NHWC 是工业界真实存在的两种 4D 摆法——PyTorch / ONNX 传统默认 NCHW，TensorFlow、GPU Tensor Core 和昇腾算子偏好 NHWC（PyTorch 里叫 `channels_last`）。词汇表终于要用来回答工程问题了。”
- **依据**：TensorFlow 默认 NHWC 属实；但“Tensor Core 偏好 NHWC”严格说是 cuDNN/框架软件栈在 Tensor Core 上的选择而非硬件单元本身的属性；昇腾侧，Cube 单元实际消费的是分形格式（如 NC1HWC0，C0=16），NHWC 是框架/主机侧的输入口径——3.3 节自己也写了“Cube 矩阵单元按矩阵（分形）方式取数”，与本句并列表述存在张力。尝试访问 hiascend.com 官方 CANN 文档核实“偏好”程度，但该站点需 JavaScript/登录，本环境无法完成在线核实；无法验证的部分明确说明：未能确认 CANN 各版本卷积类算子对 NHWC 相对 NCHW 的具体支持差异。教程 3.3 已用“常以……为更快路径（本机无 NPU，未实测，仅作事实背景）”hedging，建议第 2 节这句与 3.3 的口径对齐（例如注明“NHWC 是框架侧口径，设备侧另有分形格式”）。
- **置信度**：中（分形格式为公开常识性事实；“偏好”的具体程度未能在本环境核实官方文档）。

## 【建议】

#### 1. “向量/SIMD 单元一次读 128 位”作为通用论断偏绝对，且与代码“必要条件”口径不一致

- **原文**：“- **向量化**：向量/SIMD 单元一次读 128 位（4 个连续 f32）。NCHW 沿 W 打包、NHWC 沿 C 打包——**"沿哪维连续"直接决定"沿哪维能向量化"**。”
- **依据**：128 位是 SSE/NEON 基线（本机 aarch64 NEON 正是 128 位，叙事成立）；但 x86 AVX2/AVX-512 为 256/512 位，aarch64 SVE 是可变向量宽，“SIMD 单元一次读 128 位”作为无限定的事实句偏绝对，建议限定为“典型 128 位 SIMD（如 NEON/SSE）”。另外 `layout_lab.py` 中 `vec4_possible` 的 docstring 写的是“必要条件”，而 5.2 正文把“连续段 ≥ 4”称为“机械可判的口径”、输出打印“可以/不行”——严格说还需满足地址对齐与维长不小于向量宽度（练习第 3 题的 W=3 恰好演示了长度不足），两处口径可统一为“必要条件”。
- **置信度**：高（事实层面）；对是否必须修改属措辞限定，为低。

#### 2. test_layout.py 的 build() docstring 公式记号混用维度尺寸与下标

- **原文**：“    ├── test_layout.py         # 独立验收测试（20 个测试点，含 N=2 一般化）”
- **依据**：`test_layout.py` 第 43 行 docstring 写作 `v(n,c,h,w) = c*(h*w) + h*w + w`，其中 `h`、`w` 在第一项被当作维度尺寸（应为 c·(H·W)），第二项“h*w”实为 h·W（下标 × 尺寸），末项又是下标——同一符号两种含义，与 `layout_lab.py` 第 105 行的明确写法 `c*{H*W} + h*{W} + w` 不一致。初学者照 docstring 抄手算容易算错（例：c=1,h=1,w=2 时正确值 14，按字面歧义解读可得 6）。不影响程序行为（构造代码本身正确），建议统一为 layout_lab.py 的写法。
- **置信度**：高。

#### 3. phys_offsets 对带非零 Storage Offset 的视图不满足 docstring 承诺

- **原文**：“    """地址反查：每个逻辑下标落在 a 自身底层缓冲的第几格（元素）。"""”
- **依据**：函数用 `a.ctypes.data`（视图首元素地址）作 base，`addr - base` 实际是“相对视图首元素的格号”。对 storage offset 为 0 的视图（当天全部对象）与 docstring 一致；但对非零偏移视图（第 57 天刚教过 `x[1:]` 这类切片）会差一个常量：本机实测 `a[0,1]`（偏移 8 格）上取第一个下标返回 0 而非底层缓冲真实位置 8。当天实验未触发该情形、所有数字不受影响，但这是从第 57 天直接沿用的口径，读者复用到偏移视图时会对不上账，建议在 docstring 或 5.2 正文补一句限定（“当天所有视图 offset 均为 0”）。
- **置信度**：高（行为已实测）。

#### 4. 遗漏 numpy/torch 转置 API 参数个数差异这一初学者常见坑

- **原文**：“第一反应可能是"转置一下不就行了"：`x.transpose(0, 2, 3, 1)`，逻辑顺序立刻变成 NHWC。但昨天（Day 57）刚学过——转置只是换登记表，**一格数据都不动**。也就是说：算子从此要按 `(n, h, w, c)` 给下标了（索引习惯变了），可"一个像素的 4 个通道"在物理内存里**还是隔着 8 格**（访存序列一点没变）。要真的让它们挨着，必须把数据搬一次家。”
- **依据**：`x.transpose(0, 2, 3, 1)` 是 numpy 语法；torch 的 `Tensor.transpose` 只接受两个维度（本机实测对四参数调用抛 `TypeError: transpose() received an invalid combination of arguments`），等价写法是 `permute(0, 2, 3, 1)`。本节叙事框架中立（“框架递过来的 Tensor”），5.3 又同时出现 numpy 与 torch，初学者很容易把这句直接搬到 torch 里报错。建议在此处或“常见错误”里加一行提示。属补充性建议，不影响当天已有内容的正确性。
- **置信度**：高（API 行为本机实测）。
