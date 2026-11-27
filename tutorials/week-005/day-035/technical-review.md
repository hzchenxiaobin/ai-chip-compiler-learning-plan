# 第 35 天技术校对报告

审阅对象：`tutorials/week-005/day-035/README.md`、`code/` 下 4 个文件、`images/` 下 3 张原有 SVG（技术校对范围；配图审查后另新增第 4 张 `04-lowering-staircase.svg`，非校对对象）。
审阅环境：与教程声明一致——Ubuntu 20.04.5 (aarch64)、Ubuntu LLVM 18.1.8（`mlir-18-tools` 1:18.1.8-11~20.04.2）。`bash code/run_all.sh` 全流程已在本地重放核对（含三支报错探针与 bytecode 彩蛋），中间产物仅写入 `/tmp`，未改动仓库冻结内容。

## 【错误】

#### 1. `mlir-opt-18` 注册方言数写成 46，实测为 44
- **原文**："本机 `mlir-opt-18 --show-dialects` 实测注册了 **46 个方言**"
- **依据**：在本机（与 §5.1 声明的环境完全一致）执行 `mlir-opt-18 --show-dialects`，首行 `Available Dialects:` 后按逗号拆分实际列出 **44** 个方言（acc、affine、…、vector、x86vector，逐项清点见命令输出）。46 恰好等于 `mlir-opt-18 --show-dialects | head -1 | tr ',' ' ' | wc -w` 的结果——该写法把行首两个标题词 “Available”“Dialects:” 也计成了方言，极可能是原始清点方式出错。同一错误数字还出现在：§7 选做(2)“（本机 46 家）”、§9“认得 46 家户口”、图 2 的替代文本“46 方言注册表”，以及 `images/02-concept-map.svg`（“mlir-opt-18 认识 46 个方言”）和 `images/03-exam-annotated.svg`（“mlir-opt-18 共注册 46 个”）。正确值为 44。
- **置信度**：高（本机两次独立清点均为 44；“46 源于 `wc -w` 误计标题词”是对成因的推断，但数字本身与成因无关地确凿）。

## 【存疑】

#### 1. bytecode 大小 562 字节在本仓库路径下无法复现（实测 571；该数随源文件路径变化）
- **原文**："文本 548 字节 vs bytecode 562 字节；两种序列化读回后打印完全一致"
- **依据**：在当前仓库路径下重放 `bash code/run_all.sh`，彩蛋输出为“文本 548 字节 vs bytecode **571** 字节；两种序列化读回后打印完全一致”——文本 548 与“读回打印一致”均复现，唯独 562 复现不出。原因是 bytecode 会把源文件的**绝对路径**记进 Location：同一份 `week5_exam.mlir` 从 48 字符路径（`/tmp/opencode/.../code/week5_exam.mlir`）发射得 518 字节，从本仓库 90 字符路径发射得 571 字节，克隆位置不同的读者会得到不同数字。因此紧随其后的“（bytecode 比 548 字节的文本还大一点，因为它把源文件路径记进了 Location…）”只在长路径场景成立——短路径下 bytecode 反而小于文本（518 < 548），不宜被读成一般规律（正文已自注“大小不是重点”，故不算错误）。建议正文把该数字标注为“随路径变化”或改为区间描述。
- **置信度**：高（尺寸与路径依赖均经实测；最初 562 对应的记录路径已无法考证，此点不可验证）。

## 【建议】

#### 1. “五件套”漏了 Operation 的第六格：successors（后继块）
- **原文**："身上永远带五件套：名字、操作数、属性、区域、结果"
- **依据**：MLIR 官方语言参考对 Operation 的完整构件是 operands、results、attributes、**successors**、regions（终结符类 op 如 `cf.br`/`cf.cond_br` 携带后继块）。本日必做练习(1)恰好要标注 `cf.br ^bb1(%6, %5 : index, f32)`——其尾部带值本质是“后继块参数”，不是普通操作数；只学五件套的初学者极易把它误读成 `cf.br` 的第 2、3 个操作数。建议在 §3.1 或 §4 加一句脚注（例如“终结符还多一格：后继块及其携带值，见练习(1)的 `cf.br`”）。不影响其余论述正确性。
- **置信度**：高。

#### 2. “mlir-cpu-runner 只注册了 llvm 方言”漏了恒在的 builtin
- **原文**："而 `mlir-cpu-runner` 只注册了 llvm 方言——门口验户口，直接不认识。"
- **依据**：实测 `mlir-cpu-runner-18` 解析 `module {}` 成功（报 "Error: entry point not found"，即解析通过），而 `func`/`arith`/`memref`/`scf` 的 op 全部报 `Dialect ... not found`——builtin 方言在 MLIRContext 中总是注册、无法注销，且 §5.3 表格 s3 行自己也写着住户含 builtin。建议措辞改为“除核心 builtin 外只注册了 llvm 方言”，与自家表格保持一致。教学结论（注册表决定谁能被解析）不受影响。
- **置信度**：高。

#### 3. 必做练习(1)引用的“5.3 节 s2”与括号里的命令不是同一份输出
- **原文**："对 5.3 节 s2 的输出（`mlir-opt-18 code/week5_exam.mlir --convert-scf-to-cf`）做块级标注"
- **依据**：§5.3 的 s2 由 `week5_run.mlir` 经 bufferize＋`--convert-scf-to-cf` 产生，其回边为 `cf.br ^bb1(%7, %6 : index, f32)`（实测 `/tmp/day035/s2.mlir` 第 18 行）；而括号里的命令作用于 `week5_exam.mlir`（无 @main、块编号与值编号不同），产物回边为 `cf.br ^bb1(%6, %5 : index, f32)`（实测一致，练习引用的正是这行）。引用值名 %6/%5 与命令产物相符、但与“5.3 节 s2”不符，两份 IR 的前驱/值编号都对不上，初学者对照会被值名差异绊住。建议统一口径（要么改为“对考卷单独跑 --convert-scf-to-cf 的输出”，要么改用 week5_run 的 s2 并把 %6/%5 换成 %7/%6）。
- **置信度**：高。

#### 4. “13 行 IR”实为 16 行（13 是 op 数）
- **原文**："而且恰好把第 5 周七种零件全部装进 13 行 IR 里"
- **依据**：`code/week5_exam.mlir` 与 §1 代码块均为 **16** 行；13 是去掉 3 行收尾大括号后的 op 行数（与 13 个 op 对应）。初学者逐行一数得到 16，容易怀疑自己数错。建议写成“13 个 op（16 行）”。
- **置信度**：高。
