# 第 37 天技术校对报告

审阅对象：`tutorials/week-006/day-037/`（README.md、`code/` 全部文件、`images/` 三张 SVG）。审阅环境与教程声明一致：Ubuntu 20.04 aarch64、LLVM／MLIR 18.1.8（`mlir-opt-18`、`mlir-tblgen`）、cmake 3.20.5、ninja 1.10.0、gcc 9.4.0。校对方式：完整重放 `code/run_all.sh`（清空 `/tmp/day037/build` 后全新构建），并在 `/tmp/opencode/` 下复做 5.4 对照实验（rank 2→3）、`GET_OP_CLASSES` 链接错误实验、删除 `assemblyFormat` 的对照实验、删除 `MiniOpt.cpp` 中 `#include "mini/Ops.h"` 的对照实验，另用 Day 36 工程复现第 1 节开篇报错、读取真实生成的 `MiniOps.h.inc`／`MiniOps.cpp.inc` 并核对 MLIR 18.1.8 安装头文件中的 TableGen 定义。教程的主体事实（构建 10 步、`.inc` 行数 131／267、六次运行的全部退出码与报错文案、verifyInvariantsImpl 代码节选、Day 36 开篇报错、5.4 与链接两个对照实验、`%a`→`%arg0` 重命名习惯、`--show-dialects` 口径）均复现一致。以下为发现的偏差。

## 【错误】

#### 1. `OpTrait::Pure` 在 MLIR 18.1.8 中不存在，`[Pure]` 的真实展开不是它
- **原文**：“今天只要知道它会被展开成 `OpTrait::Pure` 等一组 C++ trait 即可”
- **依据**：MLIR 18.1.8 安装头文件 `/usr/lib/llvm-18/include/mlir/Interfaces/SideEffectInterfaces.td` 第 146 行定义 `def Pure : TraitList<[AlwaysSpeculatable, NoMemoryEffect]>;`，其中 `AlwaysSpeculatable` 又是 `TraitList<[ConditionallySpeculatable, AlwaysSpeculatableImplTrait]>`（第 136 行）；grep 全部 MLIR 头文件不存在任何 `OpTrait::Pure`。本仓库真实链接错误实验的符号与生成的 `MiniOps.h.inc` 均显示 MatmulOp 的 trait 展开为 `ConditionallySpeculatable::Trait`、`AlwaysSpeculatableImplTrait`、`MemoryEffectOpInterface::Trait` 三个。正确说法是“展开成 AlwaysSpeculatable＋NoMemoryEffect（共三个 C++ trait）”。`images/02-mechanism.svg` 中“OpTrait::Pure：由 [Pure] 进来”重复了同一错误。
- **置信度**：高（安装头文件＋真实构建产物双重核实）

#### 2. 五要素之“描述”不会生成“代码里的文档注释”
- **原文**：“生成代码里的文档注释，也供人阅读”
- **依据**：真实构建产物 `MiniOps.h.inc`（131 行）与 `MiniOps.cpp.inc`（267 行）中 grep 不到 summary／description 的任何文本（如 "matrix multiplication"）；`mlir-tblgen --help` 显示文档由独立的 `-gen-op-doc`／`-gen-dialect-doc` 目标生成 Markdown，本项目 CMake 只运行 decls／defs／dialect／types 四类生成，未跑文档目标；实测 `mlir-tblgen -gen-op-doc MiniOps.td` 输出的 Markdown 才包含 description 全文。正确说法：summary／description 供 `-gen-op-doc` 文档生成与人阅读，不进入今天的 `.inc`。`images/01-overview.svg` 中“给人和工具看的文档，随 .inc 进 C++”同样不成立。
- **置信度**：高（grep 真实产物＋实测 tblgen 命令）

#### 3. generic 形态的解析／打印与 `assemblyFormat` 无关，“语法票同时驱动两种打印”因果不成立
- **原文**：“证明 ⑥ 语法票同时驱动两种打印”
- **依据**：复现实验：复制工程并删除 `MiniOps.td` 中 `let assemblyFormat` 整段后重新构建，generic 形态 `%0 = "mini.matmul"(%arg0, %arg1) : …` 仍能解析并 round-trip（rc=0），pretty 形态则报 `error: custom op 'mini.matmul' has no custom assembly form`。说明 generic 形态由 MLIR 框架的通用汇编格式直接支持，`--mlir-print-op-generic` 强制走框架的 generic 打印器并绕过生成的 `print()`，与 ⑥ 是否存在无关。“pretty↔generic 可无损互换”这一结论本身正确，但原因是框架为每个 op 提供双形态，不是 ⑥ 同时生成了两者。3.3 节“——所以 pretty 文本和 generic 文本（`"mini.matmul"(%arg0, %arg1) : …`）可以无损互换”中的“所以”是同一条错误因果链。
- **置信度**：高（对照实验复现，两种形态行为差异可观察）

#### 4. “一个字符都不差”与教程自己的真实输出矛盾
- **原文**：“（解析→验证→打印，一个字符都不差）”
- **依据**：5.3 第 2 步的真实输出（本人复现一致）把 `%a`→`%arg0`、`%b`→`%arg1`、`%c`→`%0`，连 matmul 那一行也不是逐字符一致；实测 `mlir-opt-18` 对含 func／arith 的普通输入同样重命名为 `%arg0`／`%0`（MLIR 18 文本 round-trip 默认不保留 SSA 名），即 round-trip 保真的是 IR 语义与算子的自定义语法形态，不是文本逐字符一致。第 4 节“**round-trip 成立**意味着 `parse ∘ print = id`——文本进、文本出，一个字符不差”还有复合顺序问题：按函数复合记法 `parse ∘ print` 是先 print 后 parse，描述“文本进、文本出”的应是 `print ∘ parse = id`（且同样不是逐字符一致）；图 2 右下“→ 原样”也是同一口径。
- **置信度**：高（复现＋与教程自身展示的输出直接矛盾）

#### 5. 图 2 写的 “OperandAdaptor” 在 MLIR 18.1.8 中已不存在
- **原文**：“`-gen-op-decls` 吐 `MiniOps.h.inc`（131 行类声明），`-gen-op-defs` 吐 `MiniOps.cpp.inc`（267 行实现）”
- **依据**：该图注对应的 `images/02-mechanism.svg` 在 `MiniOps.h.inc` 卡片里写“OperandAdaptor：直接取操作数”，但本仓库真实生成的 `MiniOps.h.inc` 第 84／95 行是 `class MatmulOpAdaptor : public MatmulOpGenericAdaptor<::mlir::ValueRange>` 与 `using Adaptor = MatmulOpAdaptor;`，全文无 “OperandAdaptor”——该名称在 MLIR 14（2022 年）已由 `OperandAdaptor` 改名为 `Adaptor`，18.1.8 中不复存在。README 正文没有这个说法，仅图 2 有，修图时应改为 `Adaptor`。
- **置信度**：高（真实 `.inc` 文件核对）

## 【存疑】

#### 1. 5.3 节引用的构建日志行号与四次复现均不一致
- **原文**：“[1/10] Building MiniOps.h.inc...”
- **依据**：四次全新构建（run_all.sh、直接 `cmake --build`、两个副本工程）中 `[1/10]` 均为 `Building MiniOps.cpp.inc...`；`MiniOps.h.inc` 分别出现在 [2/10]／[6/10]，`MiniOpsDialect.h.inc` 出现在 [3/10]／[5/10]，均未出现引文的 `[1/10]=MiniOps.h.inc`＋`[6/10]=MiniOpsDialect.h.inc` 组合；且 `build.ninja` 中 `MiniOps.cpp.inc` 的构建边（第 309 行）排在 `MiniOps.h.inc`（第 319 行）之前。但 ninja 并行调度的输出顺序确有波动（增量重建实测一次 `[1/10]` 为 MiniOps.h.inc、另一次为 MiniOpsDialect.cpp.inc，故 5.4 节“日志里能看到 `[1/10] Building MiniOps.h.inc...` 重来一遍”可以复现），无法断言作者当时的全新构建必然不同。引文的其余部分（[9/10]／[10/10] 两行、总 10 步、前 6 步 tblgen 后 4 步编译链接）全部复现一致。
- **置信度**：中（复现 4/4 不一致，但 ninja 输出顺序非完全确定）

#### 2. “几十条 -Wunused-but-set-parameter 警告”实测为 17 条
- **原文**：“编译期会刷出几十条 MLIR 头文件的 `-Wunused-but-set-parameter` 警告”
- **依据**：同版本环境（Ubuntu 20.04 aarch64＋MLIR 18.1.8＋gcc 9.4.0）复现构建日志中该类警告共 17 条（Attributes.h 4 条、Types.h 1 条、OperationSupport.h 若干），全部来自 `/usr/lib/llvm-18/include` 上游头文件——“来自上游实例化、与我们的代码无关、可忽略”的判断正确，但“几十条”偏高，17 条更接近“十几条”。同代码同工具链下实例化集合固定，条数应稳定，怀疑计数口径不同或笔误。
- **置信度**：中（单一环境复现 17 条；无法完全排除作者当时的构建变体）

## 【建议】

#### 1. “11 行 → 1 行”实为 12 行 → 1 行
- **原文**：“11 行 → 1 行 add_mlir_dialect(MiniOps mini)”
- **依据**：Day 36 的 `tutorials/week-006/day-036/code/mini/include/mini/CMakeLists.txt` 实测 12 行（7 行注释＋1 空行＋4 条命令：set＋mlir_tablegen×2＋add_public_tablegen_target），换成 Day 37 的 1 行属实，但起点行数是 12 不是 11，不影响技术结论。
- **置信度**：高

#### 2. MiniOpt.cpp 里的 `#include "mini/Ops.h"` 并非算子注册的必要装配点
- **原文**：“修复：对照 5.2 节检查两处装配点——`#include "mini/Ops.h"` 与 `initialize()` 的 `addOperations<GET_OP_LIST>`”
- **依据**：复现实验：删掉 MiniOpt.cpp 的 `#include "mini/Ops.h"` 后照常构建成功、正例 round-trip rc=0——算子注册真正承重的是 MiniDialect.cpp 里的 `GET_OP_CLASSES` include 与 `initialize()` 的 `addOperations`（错误 3 的“原因”一栏只列后者，是对的；MiniDialect.cpp 缺 Ops.h 会导致编译失败而非 op unknown）。MiniOpt.cpp 这一行只是把类声明暴露给工具的翻译单元，删掉不会产生“custom op unknown”。建议正文把“承重装配”与“顺手 include”区分开，避免读者误以为缺它就会报错 3。
- **置信度**：高（实验复现）

#### 3. 负例报错的手工折行与“恰好是摘要字符串＋‘但实际收到什么’”的表述不够精确
- **原文**：“error: 'mini.matmul' op result #0 must be ranked f32 tensor with rank >= 2”
- **依据**：真实输出中该报错为单行（“…rank >= 2 of 32-bit float values, but got 'tensor<2x2xf64>'”，其后还有一行 “note: see current operation”），教程在 “>= 2” 处手工折行并缩进，易被误读为终端原样换行；且真实文案在摘要字符串与 “but got” 之间还有框架自动拼接的 “ of 32-bit float values”（来自 `[F32]` 元素类型约束），故“报错文案恰好是 3.2 节的摘要字符串＋‘但实际收到什么’”漏了这一段。建议注明“折行为排版所加”或改为单行引用。
- **置信度**：高

#### 4. 图 1 “④ 验证：6 个 .mlir”与正文“5 个 .mlir 测试”不一致
- **原文**：“5 个 `.mlir` 测试”
- **依据**：`code/` 下实际只有 5 个 `.mlir` 文件（正例、三条负例、内维探针），第 6 次运行是同一份 matmul_ok.mlir 交给 mlir-opt-18；图 1 把“6 次运行”写成了“6 个 .mlir”，与验收清单的“5 个 `.mlir` 测试”自相矛盾，建议图 1 改为“6 次运行”或“5 个 .mlir”。
- **置信度**：高

#### 5. 图 2 代码区行尾标记“①①”疑为笔误
- **原文**：“下面是 `mini.matmul` 的五要素（①～⑥ 标注与图 1 对应）”
- **依据**：`images/02-mechanism.svg` 在 `Mini_Op<"matmul", [Pure]> {` 行尾渲染出“①①”两个标记，按图注该行应对应单个“①”（名称要素）；属绘图笔误，不影响语义，建议修图时一并改掉。
- **置信度**：高

#### 6. “昨天 rc=0”应为“改表前 rc=0”
- **原文**：“同一份输入，昨天 rc=0、改表后 rc=1”
- **依据**：rc=0 来自今天 5.3 第 2 步的正例运行，而“昨天”（Day 36）的 mini-opt 对同一输入报 `custom op 'mini.matmul' is unknown`（rc=1，第 1 节开篇即为该真实输出），字面上的“昨天 rc=0”与史实不符；此处想表达的是“同一工程未改约束时 rc=0”，建议改为“改表前 rc=0”或“刚才 rc=0”。
- **置信度**：高
