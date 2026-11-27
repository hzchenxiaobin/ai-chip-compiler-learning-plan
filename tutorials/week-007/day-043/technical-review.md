# 第 43 天技术校对报告

审阅对象：`tutorials/week-007/day-043/`（README.md、`code/` 全部交付物、3 张 SVG）。审阅方法：在本机完整重放 `bash tdd_replay.sh`、`bash run_all.sh`（含 Day 42 mini-opt 现场构建与 6 个探针）、5.5 节全部 CLI 命令、第 7 节练习的 5 行输入；对照 Day 42 冻结源码（MatmulVerifier.cpp、MiniOps.td、ShapeRelation.h）核对 Verifier 四条规则与 ODS 约束；对照本机安装且构建实际使用的 MLIR 18.1.8 头文件（/usr/lib/llvm-18）核对哨兵值与接口论断。所有"真实输出"块与复跑结果逐行核对一致（除下文【建议】第 1 条所述节选问题）。

## 【错误】

#### 1. 动态维哨兵的名称 `kDynamicSize` 在本教程锁定的 MLIR 18.1.8 里已不存在

- **原文**：“`kDynamicSize` 是 MLIR 的内部哨兵值（一个巨大的负数，所以 Day 42 打印错误信息时要先过 `dimToString` 把它翻回 `?`）”
- **依据**：本机构建探针实际使用的 MLIR 18.1.8（`llvm-config --version` 为 18.1.8）头文件 `/usr/lib/llvm-18/include/mlir/IR/BuiltinTypeInterfaces.h.inc` 第 113～119 行将该哨兵定义为 `static constexpr int64_t kDynamic = std::numeric_limits<int64_t>::min();`，`isDynamic()` 比较的也是 `kDynamic`；对整个 `/usr/lib/llvm-18` 目录 grep 不到任何 `kDynamicSize`（该名是上游改名前的旧称）。数值语义（INT64_MIN、巨大负数）和"`isDynamic()` 判的就是它"（README 第 52 行）都正确，但读者按 `kDynamicSize` 检索 18.1.8 头文件会一无所获；`code/matmul_infer.py:29` 注释和 Day 42 冻结代码注释同样沿用旧名，属同源问题。
- **置信度**：高——直接核对本机构建所用的 18.1.8 头文件并全树 grep 证实；上游改名的具体版本号未能本地确认，但这不影响"18.1.8 中不存在该标识符"的结论。

#### 2. "遇到 `?` 一律保守放行"对 Verifier 规则 1（秩一致）不成立

- **原文**：“都在"两侧都静态"时才可能报错，遇到 `?` 一律保守放行。”
- **依据**：秩是 ranked tensor 永远已知的属性，与维度是否写 `?` 无关：Day 42 源码 `lib/MatmulVerifier.cpp:59` 的规则 1 直接比较 `getRank()`。本机用 Day 42 mini-opt 实测 `tensor<?x?xf32> · tensor<?x?x?xf32> -> tensor<?x?xf32>`（全维 `?`、仅秩 2≠3），报 `'mini.matmul' op requires the same rank for both operands and the result, but got ranks 2, 3 and 2` 且 rc=1——`?` 并未让它保守放行。"两侧都静态才可能报错、遇 `?` 放行"只对规则 2～4（逐维经 `staticallyCompatible` 比较，见 MatmulVerifier.cpp:38）成立；把规则 1 一并纳入，既与实测反例矛盾，也与教程自己的 T14 期望值和 R0（"秩不等属结构性非法"）自相矛盾。
- **置信度**：高——反例已用 Day 42 mini-opt 本机复现（rc=1），规则 2～4 部分与源码逐行一致；问题仅出在这句前置补给把四条规则不加区分地并入同一结论。

## 【存疑】

#### 1. "真实编译器都有 Shape 推导"的"都"过于绝对

- **原文**：“所以真实编译器都有 **Shape 推导（Shape Inference）**：操作数类型进，结果类型出，编译器自己算。”
- **依据**：本地可核实的部分：MLIR 上游只把类型推导做成**可选**的 OpInterface（`/usr/lib/llvm-18/include/mlir/Interfaces/InferTypeOpInterface.td`），未实现该接口的算子其结果类型仍由前端显式写出——本系列 mini 方言到 Day 43 为止就是"运行于真实 MLIR 基础设施、结果类型人写"的现存实例，Day 44 才补上推导。至于各商用编译器是否"都"在编译期算 shape，我无法在本地逐一核实（TVM／ONNX-MLIR／torch-mlir 等确有；以动态 shape 为主的路线是否算"编译器自己算"我没有证据），不下断言。建议弱化为"主流 ML 编译器普遍都有"或举两三个实例限定范围。
- **置信度**：中——MLIR 侧事实可本地核实；对"真实编译器"全称覆盖面的质疑属于表述过于绝对，需作者自行判断是否收窄措辞。

## 【建议】

#### 1. 5.4 节 k_mismatch 输出块标"真实输出"实为节选，且"原样往返"未提 SSA 名被规范化

- **原文**：“第 [3/3] 步输出如下（真实输出；round-trip＝解析成 IR 再打印出来，原样往返）：”
- **依据**：本机复跑 `run_all.sh`：k_mismatch 段实际打印 4 行——错误信息行、源代码行、`^` 指示行和 `note: see current operation:` 行；README 只保留了首行（还重排了换行）而删去后三行，且未标"节选"（5.3 节三个输出块都标了"节选"，风格不一致）。另外五个 rc=0 探针的实际输出是 `%0 = mini.matmul %arg0, %arg1 ...`，而探针源文件里写的是 `%c`／`%a`／`%b`——round-trip 中 SSA 名被规范化重命名，"原样往返"仅对类型文本成立，初学者对照源文件会发现名字对不上。建议补"节选"标注并加一句 SSA 名规范化的说明。
- **置信度**：高——本机复跑输出与 README 逐行比对得出。

#### 2. 第 1 节"三个答案"与 6 个探针并非一一对应

- **原文**：“今天用 6 个探针实测（5.4 节，全部真实运行）：`?x3 · 3x2` 的结果类型写 `?x2`、写 `2x2`、甚至写 `?x?`，mini-opt 的退出码**全是 0**”
- **依据**：6 个探针里第三个答案 `?x?` 对应的 probe_result_all_dynamic 输入是 `2x3 · 3x2`（全静态），并非句中主语 `?x3 · 3x2`；`?x3 · 3x2 -> ?x?` 这个组合没有单独的探针。我另行用 Day 42 mini-opt 实测该组合确实 rc=0（论断本身成立），但初学者拿"6 个探针"对照 5.4 节清单时会找不到第三个组合的直接对应。建议注明第三个例子是探针 4 的变体，或换用与探针一致的输入表述。
- **置信度**：高——探针文件内容与实测均已核对。

#### 3. 测试分组名"单侧动态"涵盖 T08／T10 名不副实

- **原文**：“完整的 15 行按四组展开：全静态 T01–T05、单侧动态 T06–T10、batch 维 T11–T12、防御性失败 T13–T15。”
- **依据**：T08 的检查点自述"K 双侧动态"、T10 自述"全动态"，都不属于分组名"单侧动态：? 沿 M / N 传播"（`test_matmul_infer.py:23` 的同名分组注释被 README 第 137 行节选照抄）；5.3 节结论用"T06–T12 走出口②"才是准确口径。建议分组名改为"动态维传播"之类，或把 T08／T10 拆出，避免分组名与行内自述打架。
- **置信度**：高——仅涉及分组标签与行内文字的一致性，不影响任何技术结论。
