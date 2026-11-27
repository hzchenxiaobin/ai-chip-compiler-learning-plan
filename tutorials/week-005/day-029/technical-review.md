# 第 29 天技术校对报告

校对环境与教程同一台机器（Ubuntu 20.04 arm64，内核 5.10.0-182.0.0.95.r3450_282.hce2.aarch64，Ubuntu LLVM 18.1.8）。以下判断均以本机可复现实验、dpkg 元数据、上游 llvm-project release/18.x 源码或官方文档核对为准；无法核实之处已在置信度中注明。三步闭环（canonicalize 8→2 条 op、FileCheck PASS、JIT 打印 16）、42→48 对照实验、`--mlir-print-ir-after-all` 输出格式、env_check.sh 输出、388 个 Pass 开关计数、第 6 节四条报错的原文与站点归属（错误 2/3 在第①站 Parser、错误 4 在第②站 Verifier）均已逐项复现通过，不再列为意见。

## 【错误】
#### 1. 前置准备的磁盘占用估算偏低近一倍
- **原文**：“一台能用 apt（或其他包管理器）装 LLVM 18 的 Linux 机器、约 200 MB 磁盘、基本命令行操作”
- **依据**：按教程 5.1 节的两条 apt 命令实测占用远超 200 MB：dpkg 元数据 mlir-18-tools Installed-Size 248944 KiB（≈243 MiB，du 实测 /usr/lib/llvm-18/bin 共 493M，含 llvm-18-tools 的二进制）；其硬依赖 libllvm18 113478 KiB（≈111 MiB，`apt-cache depends mlir-18-tools` 确认 Depends: libllvm18，ldd 确认 mlir-opt 链接 libLLVM-18.so.18.1）；llvm-18-tools 2725 KiB。干净系统上合计约 356 MiB（≈374 MB）；即使只算 mlir-18-tools 单包也约 255 MB。按"约 200 MB"预留磁盘的读者可能装不下，建议改为"约 400 MB"或"数百 MB"。
- **置信度**：高（数值来自包元数据与 du 实测，与具体机器无关）。

## 【存疑】
#### 1. “上游某些构建的 runner 会注册更多方言”更可能是上游固有设计而非构建差异
- **原文**：“（本机构建如此；上游某些构建的 runner 会注册更多方言，所以"网上能跑我这不能跑"多半是构建差异）。”
- **依据**：本机复现确认报错本身：mlir-cpu-runner-18 直接吃未 lower 的 IR 报 `Dialect 'func' not found for custom op 'func.func'`。但核对上游源码（llvm-project release/18.x）：mlir/tools/mlir-cpu-runner/mlir-cpu-runner.cpp 全文仅 34 行，main 里只构造 `DialectRegistry` 并调用 `registerAllToLLVMIRTranslations`，随后由 JitRunnerMain（mlir/lib/ExecutionEngine/JitRunner.cpp）用该 registry 创建 MLIRContext——上游标准构建同样不注册 func/arith，即“runner 只收 LLVM 方言输入”是工具的固有契约，不是 Ubuntu/本机打包的特殊性。mlir-cat 也不是上游 mlir/tools 中的工具，而是上游示例 mlir/examples/minimal-opt/mlir-cat.cpp（不注册任何方言、仅允许 generic 形式的未注册 op），Ubuntu 把这个示例工具打进了 mlir-18-tools。教程 3.2 节“本机的这个构建不注册 func 方言”“本机构建的 mlir-cat 和 mlir-cpu-runner 只认识很小的子集”的观察结果属实，但把原因表述为“本机构建如此”容易让读者以为换个构建或版本就能直接喂 func IR；“网上能跑我这不能跑”的更常见解释是那些教程先做了 lower。不确定点：无法排除某些第三方自定义 runner 注册了更多方言，故列存疑。
- **置信度**：高（上游源码逐行核对＋本机复现；“存在注册更多方言的第三方构建”这一点无法证伪）。

## 【建议】
#### 1. 4 节的报错引文缺少“than prior uses”，与真实输出不一致
- **原文**：“`use of value '%x' expects different type: 'i64' vs 'i32'`——SSA 值类型对不上，第①站（还带 `note:` 指出第一次使用的位置）”
- **依据**：本机实测（`%r = arith.addi %x, %x : i64` 且 `%x: i32`）真实报错为 `use of value '%x' expects different type than prior uses: 'i64' vs 'i32'`，第 6 节错误 3 的引用与实测一致，但 4 节和 02-mechanism.svg 里的引文少了“than prior uses”五个词；读者拿这段字符串去 grep 报错或查文档会对不上。第①站归属本身正确（另经实验证实：同文件后行再放一个第①站必报的语法错时只报前者，说明该错误在解析期产生；源码核对为 mlir/lib/AsmParser/Parser.cpp 的 OperationParser::resolveSSAUse）。
- **置信度**：高（实测输出逐字符比对＋源码定位）。

#### 2. 错误 4 的复现方式宜写明索引必须是 SSA 值
- **原文**：“现象：给 `memref<2x3xf32>` 的 load 提供三个索引；这次报错发生在**第②站 Verifier**——语法本身是通的（load 的语法允许任意个索引）”
- **依据**：本机实测：索引写成 SSA 值（`%c0 = arith.constant 0 : index` 等＋`memref.load %m[%c0, %c1, %c2] : memref<2x3xf32>`）时确实得到教程所述的 `error: 'memref.load' op incorrect number of indices for load, expected 2 but got 3` 及 `note: see current operation:` 的 generic 打印，第②站结论正确；但初学者最自然的写法是字面量 `memref.load %m[0, 1, 2]`，这会在第①站就报 `error: expected ']'`（操作数位置不接受裸整数），根本到不了 Verifier。建议在“现象”里给出用 index 常量做索引的最小复现 IR，避免读者用字面量复现时看到另一个错误而怀疑分类。
- **置信度**：高（两种写法均实测）。

#### 3. 图 1 底部链路把 canonicalize 的输出直接画成了 JIT 的输入
- **原文**：“底部是环境一装好就能跑通的那条链——`checkin.mlir` 经 `mlir-opt-18 --canonicalize` 变成 2 条 op，FileCheck 判卷通过，JIT 在终端打印 `16`（均为本机真实结果）。”
- **依据**：01-overview.svg 底部流水线里“2 条 op”方框直接用箭头指向“JIT 执行”方框；但 5.3 节第 ③ 步与 run_all.sh 的真实命令是 JIT 执行 `run.mlir`（未先 canonicalize，直接 lower），canonicalize＋FileCheck 与 lower＋JIT 是两条并列的验证路径（图 3 右侧 panel 画的才是真实路径）。按图 1 的链路，初学者可能尝试把 `--canonicalize` 的输出接给 runner。建议把箭头改为在 FileCheck 后分叉，或注明“JIT 走 run.mlir 的 lower 路径”。
- **置信度**：高（命令与脚本逐一核对）。

#### 4. “四站流水线”宜补充 Verifier 在每个 Pass 之后默认还会再跑
- **原文**：“`Verifier` 检查结构约束，比如操作数个数、索引数量（结构不合法在这站报）”
- **依据**：mlir-opt 有 `--verify-each` 开关（`--help-list` 原文：“Run the verifier after each transformation pass”），默认开启，即 Pass 管线里每个 Pass 跑完都会再验证一次——这是后续（第 45 天起）写自定义 Pass 时定位“哪一步把 IR 改坏”的关键机制。把验证画成仅第②站一次作为入门简化可以接受，但建议加一句“Pass 之后还会再验”，为后续调试铺路。另外“操作数个数”的例子在 generic 形式下确属第②站（实测 `"arith.addi"(%x) : (i32) -> i32` 报 `'arith.addi' op expected 2 operands, but found 1`，带 generic note）；自定义语法下则是第①站 Parser 报 `expected ','`，教程错误 2 的归类不受影响。
- **置信度**：高（本机实测＋`--help-list` 原文）。

#### 5. “本机没有打包 lit”在本机上字面不成立（若指 Ubuntu deb 包则成立）
- **原文**：“本机没有打包 lit，所以手动执行它底层的那条管道——效果相同”
- **依据**：本机 `command -v lit` 可找到 /opt/buildtools/Python-3.11.4/bin/lit（`lit --version` 输出 18.1.8，非 apt 来源）；同时实测 Ubuntu 的 mlir-18-tools/llvm-18-tools 确实不带 lit（dpkg -L 无 lit，/usr/lib/llvm-18/bin 亦无）。“打包”若指 Ubuntu 的 deb 包则属实，但字面读作“本机没有 lit”与当前机器状态不符。建议措辞精确为“Ubuntu 的 LLVM 18 包不带 lit”。
- **置信度**：中（/opt/buildtools 属本环境开发工具，不确定教程写作当天是否已存在；Ubuntu 包不含 lit 为实测事实）。

#### 6. “8 条 op → 2 条”的计数未含 func.return，宜与图 3 的口径统一
- **原文**：“函数体从 8 条 op 缩到 2 条”
- **依据**：MLIR 中 `func.return` 同样是 Operation（第 9 节预告 Day 30 讲“一切皆 Operation”）；严格计数输入函数体是 9 条（8＋return）、输出 3 条（2＋return）。图 3 已用“输出：2 条 op（＋ return）”注明口径，正文（含第 1 节“从 8 条 op 化简成 2 条”）建议同样补“（不含 return）”，与后续概念的精确表述衔接。
- **置信度**：高（MLIR 语义明确；属计数口径问题，结论本身无误）。

#### 7. 路线 B 标注“官方文档命令”，但 TARGETS 参数与当前官方页不一致
- **原文**：“以下为官方文档命令，本机未执行——完整构建通常需要几十分钟到数小时”
- **依据**：教程代码块写 `-DLLVM_TARGETS_TO_BUILD="Native"`；当前 MLIR 官方 Getting Started（https://mlir.llvm.org/getting_started/，本次已抓取核对）写的是 `-DLLVM_TARGETS_TO_BUILD="Native;NVPTX;AMDGPU"`，其余 cmake 参数及 `cmake --build . --target check-mlir` 与官方一致（教程追加的“只编需要的工具”一行是合理补充）。纯 CPU 学习环境删掉 NVPTX/AMDGPU 合理且省时，但既声明“官方文档命令”，宜注明 TARGETS 做了删减。不确定点：LLVM 18 时代的官方页存档（web.archive.org）本次无法访问，未能确认 2024 年时是否即为 “Native”。
- **置信度**：中（当前官方页已核对；18 时代存档未能访问）。

#### 8. “全文如下”实际省略了文件开头的注释块
- **原文**：“`checkin.mlir` 全文如下（顶部的 `CHECK` 注释就是给 FileCheck 的考卷）：”
- **依据**：code/checkin.mlir 开头另有 12 行说明注释（从“// checkin.mlir —— 第 29 天的‘打卡’示例”到“//   mlir-opt-18 checkin.mlir --canonicalize | FileCheck-18 checkin.mlir”），README 展示的代码块从 CHECK 行开始。展示内容与文件的功能部分等价，但“全文”二字不确切；建议改为“关键内容如下”或补齐注释块。
- **置信度**：高（与仓库内文件逐行比对）。
