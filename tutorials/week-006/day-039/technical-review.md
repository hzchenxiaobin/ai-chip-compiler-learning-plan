# 第 39 天技术校对报告

校对环境：Ubuntu 20.04 · LLVM/MLIR 18.1.8（mlir-18-tools）· cmake 3.20.5 + Ninja，与教程声明一致。已在独立临时目录全新构建本日工程并重放全部 13 个测试（退出码与 5.3 节表格逐项一致），另复现了 3.2 节静默失败实验、5.4 节哨兵值实验（修复前后）、第 6 节错误 1/2/3 对应场景、Day 38 工程对照（matmul_inner_dim.mlir rc=0）及“一条 IR 两个独立坏 op 只报第一个”实验；涉及 MLIR API/常量的论断均已对照 /usr/lib/llvm-18/include 头文件原文核实。以下意见仅写入本报告；除按配图审阅要求在 5.4 节为已有图片 images/04-sentinel-debug.svg 补插链接与图注外，未改动教程正文、代码与冻结输出。

## 【错误】

#### 1. `ShapedType::kDynamicSize` 在本教程锁定的 MLIR 18.1.8 中不存在，正确常量名是 `ShapedType::kDynamic`

- **原文**：“`tensor<?x3xf32>` 里 `?` 在 C++ 侧是常量 `ShapedType::kDynamicSize`（= INT64_MIN，一个巨大的负数）。”
- **依据**：在 /usr/lib/llvm-18/include 全树检索 `kDynamicSize` 为 0 处命中；MLIR 18 中该常量为 `ShapedType::kDynamic`，定义于 mlir/IR/BuiltinTypeInterfaces.h.inc 第 113–114 行：`static constexpr int64_t kDynamic = std::numeric_limits<int64_t>::min();`，且 `isDynamic(dValue) { return dValue == kDynamic; }`。数值结论（INT64_MIN = -9223372036854775808，与 5.4 节真实报错一致）正确，但读者若照文中写法使用 `ShapedType::kDynamicSize` 会直接编译失败（kDynamicSize 是旧版 MLIR 的名称）。同一过时名称还出现在：5.4 节“——`?` 的内部哨兵值 `kDynamicSize`（INT64_MIN）”、第 6 节错误 3“`?` 的内部值是哨兵 `kDynamicSize`”、images/02-mechanism.svg 底部注释、code/mini/lib/MatmulVerifier.cpp 第 45 行注释。教程代码本身可编译（只用到了 `ShapedType::isDynamic`），受影响的仅是正文与注释中的名称。
- **置信度**：高。已对照本机 MLIR 18.1.8 头文件逐条验证；未考证该常量改名的具体版本号（不影响本结论）。

#### 2. 动态维度负例的 N 比较数字写错：应为 N 3 ≠ 5，不是 2 ≠ 5（3.3 节与 5.3 节共三处）

- **原文**：“内维 ? 对 ? 放行，输出 N 2 ≠ 5 照拦”
- **依据**：`2x? · ?x3 -> 2x5` 中 rhs 的最后一维 N = 3（不是 2），res 的 N = 5；本机实测报错为 "error: 'mini.matmul' op result shape must be [M, N] derived from the operands: expected [..., 2, 3] from lhs 'tensor<2x?xf32>' and rhs 'tensor<?x3xf32>', but got 'tensor<2x5xf32>'"——期望值是 [..., 2, 3]，即 M=2、N=3，数字 2 属于 M 维（lhs M=2 与 res M=2 是匹配的，不是触发拦截的那一对）。同一数字错误在 5.3 节又出现两处：引言“（内维 ? 对 ? 放行，输出 N 却是静态的 2 vs 5）”和其后图注句“K 是 `?` 对 `?`（放行），N 是 2 对 5（拦截）”，均与它们正下方引用的同一条真实输出（expected [..., 2, 3]）自相矛盾；正确写法是 3 对 5。
- **置信度**：高。以本机真实运行输出核对，三处引用均已在 README 原文中逐字定位。

#### 3. 3.1 节把 `SameOperandsAndResultType` 归入"只能描述单个值自身的规则"，与 MLIR 事实及教程自身说法矛盾

- **原文**：“ODS 类型约束（`RankedTensorOf`、trait 如 `SameOperandsAndResultType`）只能描述**单个值自身**的规则”
- **依据**：`SameOperandsAndResultType` 恰恰是跨值约束：mlir/Interfaces/InferTypeOpInterface.td 第 375 行注释明确写 "Op has the same operand and result type"（第 377 行 def），它要求全部操作数与结果类型一致，是 ODS（NativeOpTrait）可表达的"多个值之间"的规则，并非"单个值自身"的规则；教程第 9 节自己也承认"ODS 的 trait 已经查过了"（指 mini.add 的 Shape 一致性检查，见 MiniOps.td 中 mini.add 的定义）。准确表述应为：`RankedTensorOf` 这类类型约束只作用于单个值；ODS 还能表达少量跨值相等关系（`SameOperandsAndResultType`、`AllTypesMatch` 等），但表达不了"内维匹配、输出 [M,N]"这类需要逐维比较的规则。本条不影响"内维匹配必须手写"的结论，但定义性表述有事实错误。
- **置信度**：高。以 MLIR 18.1.8 头文件与教程自身（第 9 节、MiniOps.td 中 mini.add 的定义）交叉验证。

#### 4. 第 6 节错误 1 的“现象”按其所述失误步骤（文件已在 lib/ 里、只是没登记）不可复现：实际会卡在 CMake configure 期，而不是“编译正常、链接报错”

- **原文**：“现象：编译一切正常，链接 mini-opt 时爆出长串错误，核心一句是 `undefined reference to 'mini::MatmulOp::verify()'`（本教程开发时真实复现）。”
- **依据**：在本机同一工程、同一工具链上复现“MatmulVerifier.cpp 放在 lib/ 目录但未登记进 add_mlir_dialect_library”：cmake configure 阶段直接失败，报 "CMake Error at /usr/lib/llvm-18/lib/cmake/llvm/LLVMProcessSources.cmake:116 (message): Found erroneous configuration for source file MatmulVerifier.cpp … this target lists all files in that directory"——LLVM/MLIR 构建系统强制目录内源文件全部登记进该目录的 target，根本走不到“编译一切正常”的阶段。`undefined reference to 'mini::MatmulOp::verify()'` 这一链接错误本身真实存在（本机已复现），但它对应的是“hasVerifier = 1 而 mini-opt 链接的静态库里没有 verify() 定义”的场景：.cpp 尚未创建，或文件放在 lib/ 之外（如工程根目录，同样已复现：configure 与编译通过、链接期才报 undefined reference）；Day 42 教程第 6 节的表述“文件在别处、符号没进库时才轮到链接器抱怨”与此一致。按错误 1 现在的写法，读者照步骤复现会看到完全不同的报错（configure 期 CMake Error），反而困惑。
- **置信度**：高。在本教程锁定的环境里分别复现了三种场景：文件在 lib/ 未登记 → configure 失败；文件不存在 → 链接期 undefined reference；文件在工程根目录未登记 → 链接期 undefined reference。

## 【存疑】

#### 1. "绝不误拒合法 IR（soundness）"的术语标注与通行约定方向相反

- **原文**：“Verifier 的底线是**绝不误拒合法 IR**（soundness）”
- **依据**：在形式验证与静态分析的通行术语里，验证器的 soundness 通常指"接受 ⇒ 合法"（绝不误收，允许误拒），而"合法 ⇒ 接受"（绝不误拒）叫 completeness；静态分析里 "sound" 也指"不漏报（宁可误报）"，与本教程"绝不误拒、宁可放过"的取向正好相反。若按"拒绝即断言非法、该断言永不出错"的读法，标注又可自圆其说。MLIR 官方文档并未使用该术语，不同背景的读者容易读反。建议删去括号注记，或就地用一句话定义（例如"这里指'拒绝必有铁证'，即不会误拒合法 IR"）。
- **置信度**：中。术语约定因社区而异（验证器视角与分析器视角存在两种读法），既可能是标注反了，也可能是作者有意采用"拒绝即断言"的读法，故列为存疑而非错误。

## 【建议】

#### 1. "完整文件 101 行含注释"与实际行数不符

- **原文**：“一个 `verify()` 加两个 helper，完整文件 101 行含注释”
- **依据**：`code/mini/lib/MatmulVerifier.cpp` 实际为 103 行（`wc -l` 核对；非空行 87 行，两种口径都对不上 101）。建议更正数字或改为"约百行"。
- **置信度**：高。

#### 2. "7 个负例全拦／4 个 rc=0"与 5.3 节表格的行数（8 个 rc=1、5 个 rc=0）不一致

- **原文**：“全程本机实测：7 个负例全拦、4 个正例零误伤、Day 38 目标图回归无恙”
- **依据**：5.3 节表格中 rc=1 的测试共 8 个（inner_dim、bad_result_shape、rank_mismatch、batch_mismatch、dynamic_bad_inner、dynamic_bad_result、two_errors、sentinel_probe），rc=0 的共 5 个（ok_2d、ok_batched、dynamic_ok、dynamic_refine、pipeline_regression）。第 9 节"7 个负例全拦、4 个正例零误伤"若按"负例不含两个探针、正例不含回归"的口径恰好成立，但该口径未写明，且与 5.3 节"2 正 + 4 静态负 + 4 动态 + 2 探针 + 1 回归"的分类对不齐；图 3 图注"为什么 4 个 rc=0 里有两个带着 ？"同样按 4 计数，而它所指的同一张表格（以及 images/03-real-results.svg 右侧表格和底部"拦截侧：7 个负例全部被拦"）里读者数出来的是 5 个 rc=0、8 个 rc=1。建议统一口径（例如写明"8 个 rc=1（含 2 个探针）、4 个正例＋1 个回归 rc=0"）。
- **置信度**：高（计数事实），建议内容属口径澄清。

#### 3. run_all.sh 在构建失败时不中止，可能用旧二进制产生"假重放"

- **原文**：“`code/run_all.sh` 一键重放全部实验”
- **依据**：本机实测：/tmp/day039/build 的 CMake 缓存指向仓库重组前的旧路径（tutorials/day-039/…），脚本第 1 步 `cmake --build` 报 "The source ... does not match the source ... used to generate cache" 并失败，但脚本（`set -uo pipefail`，无 `-e`）不中止，继续用 /tmp/day039/build/bin 里 11 月 12 日的旧 mini-opt 跑完 13 个测试，输出看起来一切正常（本次重放 13 个退出码与全新构建一致，纯属旧二进制恰好同源）。任何 /tmp 中留有指向旧路径或构建失败缓存的机器都会得到"重放成功"的假象。建议构建后校验 mini-opt 已生成（或构建失败即退出）。全新 /tmp 下按 5.3 节命令配置构建可正常工作（已在临时目录验证）。
- **置信度**：高（本机复现）；严重度低，全新环境不受影响。

#### 4. 5.3 节引用的报错换行是目视折行，不是真实输出的换行

- **原文**：“matmul_inner_dim.mlir:8:10: error: 'mini.matmul' op requires matching inner”
- **依据**：该条 error 在重定向到文件（`cat -A` 核验无内部换行符）和伪终端下都是单行长字符串；README 中 "requires matching inner / dimensions: … has / second-to-last dim 2" 的三行折行来自作者终端宽度的目视换行。文字内容逐字一致，仅换行位置不真实。建议注明为终端折行或合并为单行，避免读者比对自己的输出时误以为格式不同。
- **置信度**：高。已用 `cat -A` 与重定向两种方式核验真实字节流。

#### 5. 图 2 中"那会误拒 ?x3·3x2→2x2（5.4 节实测）"的出处标错

- **原文**：“图右的卡片是两个真实运行结果，底部小字是 `?` 的内部表示（哨兵值）——5.4 节会真实踩到这个坑。”
- **依据**：images/02-mechanism.svg 第 117 行写"那会误拒 ?x3·3x2→2x2（5.4 节实测）"，但 ?x3·3x2→2x2 被严格相等误拒的实验在第 6 节错误 3（"本机真实实验"）与 5.3 节表格（matmul_dynamic_refine，rc=0）中；5.4 节只做了 ?x3·3x2→?x5 的哨兵探针。README 正文这句本身无误（哨兵泄漏确实在 5.4 节），错的是 SVG 内部的交叉引用。建议把图内引用改为"第 6 节错误 3"。按校对规则未改动 SVG，仅在此报告。
- **置信度**：高。

#### 6. emitOpError 与"裸 emitError"的差异描述把"位置"也算成了差异点

- **原文**：“前者自动带上 `'mini.matmul' op` 前缀和 op 的位置”
- **依据**：mlir/IR/Operation.h（18.1.8）第 877/881 行：`emitOpError` 的注释是 "Emit an error with the op name prefixed, which is convenient for verifiers"，唯一差异是 op 名前缀；`Operation::emitError` 同样把诊断挂在本 op 的位置，两者位置行为一致。建议措辞改为"前者额外带上 'mini.matmul' op 前缀（位置两者都会挂）"。
- **置信度**：高。

#### 7. 可补充官方文档明示的 verify() 边界：不要访问嵌套/其他操作

- **原文**：“进入 `verify()` 时，"是秩 ≥ 2 的 f32 张量"已经成立，我们只需要查增量部分。”
- **依据**：mlir/IR/OpBase.td（18.1.8）第 398–404 行对 hasVerifier 的官方说明明确写道："This verifier shouldn't access any nested operations because those operations may ill-formed. Use the `hasRegionVerifier` below instead."。这是初学者写 Verifier 时最容易踩的边界（例如想顺手检查 lhs 的生产者），而第 7 节选做挑战恰好建议把"checking the producer of lhs"写进 note——正文若补一句"要看的对象超出本 op（如生产者、使用者）时用 note 或后面的 Pass，不要写进 verify()"，可以提前堵住这个坑。
- **置信度**：高（依据为本机 MLIR 18.1.8 头文件原文）。
