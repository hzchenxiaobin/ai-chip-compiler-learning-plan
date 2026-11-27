# 第 31 天技术校对报告

校验方法：在 Ubuntu 20.04.5（aarch64）、LLVM 18.1.8（`mlir-opt-18`／`mlir-cpu-runner-18`，与教程声明的环境一致）上重放 `probe.sh` 全部 6 组实验与 5 个错误探针，并对照 MLIR 18.1.8 官方源码（AsmPrinter.cpp、Verifier.cpp、ControlFlowOps.td）核实打印与校验行为。教程中全部 6 组实验输出、5 条报错原文（含 note）、`scf.for` 边界类型的报错原文均逐字复现，无一造假；以下为发现的问题。

## 【错误】

#### 1. 选做挑战(a) 声称存在"两个条件操作数、三个后继"的 `cf.cond_br`，该形态不存在
- **原文**：“需要两个 `cmpi` 和一条三路 `cf.cond_br`——它有两个条件操作数、三个后继”
- **依据**：`cf.cond_br` 的 ODS（mlir/Dialect/ControlFlow/IR/ControlFlowOps.td，LLVM 18.1.8）定义为**单个 i1 条件操作数＋恰好两个后继**（`ins I1:$condition`，successors 恰为 `trueDest`／`falseDest`），不存在"两个条件、三个后继"的形态。本机实测：写出 `cf.cond_br %isneg, %isbig, ^neg(…), ^big(…), ^other(…)` 直接解析失败，报 `error: expected block name`。实现三路分支需要**级联两条 `cf.cond_br`**（先判负数、再在中间块判 |x|>100）或改用 `cf.switch`。读者照挑战(a)原文写"一条三路 cf.cond_br"必然被解析器拦下。
- **置信度**：高。ODS 定义与解析实测双重核实。

#### 2. `code/loop_sum.mlir` 文件头注释断言 sum_to_n(5)=15、JIT 打印 15，与真实行为相反
- **原文**：“`loop_sum.mlir` 的关键部分（完整文件见 `code/loop_sum.mlir`）：”
- **依据**：README 5.2 引导读者打开完整文件，而该文件第 9 行注释写着 `// sum_to_n(5) = 1+2+3+4+5 = 15，一会儿 JIT 打印 15。`。本机实测（`mlir-opt-18`→`mlir-cpu-runner-18`）该文件 JIT 输出为 **10**：`scf.for` 上界是开区间（`%i < ub` 即退出），`%i` 取 1、2、3、4，和为 10——这正是本教程 5.3 实验⑥与 5.4 节的核心结论。该注释是过时的错误预测，与同文件的循环写法、与教程正文直接矛盾；读者按教程"先预测再验证"的习惯读代码注释会先被灌入错误答案。README 引用行本身无误，错误在被引用交付物的注释中。
- **置信度**：高。本机重放输出与教程 5.3/5.4 记录一致（10／15），仅该文件注释矛盾。

## 【存疑】

#### 1. "Region 反复复用"的说法对实验⑤（scf→cf）按字面读不成立，易被理解为 scf.for 的 Region 会保留
- **原文**：“高层 scf → 低层 cf，Region 反复复用、Block 拆开重组”
- **依据**：实验⑤的真实输出里，`scf.for` 整条 op 连同它持有的 Region **被删除**，拆出的 4 个新块全部位于 `func.func` 的 Region 中——被"复用"的壳是外层函数的 Region，scf.for 自己的 Region 并未复用（SCFToControlFlow 的做法就是在父 Region 里建块、搬运循环体 op、擦除原 op；输出里 `arith.addi` 已住在 `^bb2` 也可佐证）。3.1 节同款表述"把一个 Region 里的高层 op 换成低层 op，Region 这个壳反复复用"对 **op 级**转换（如 arith→llvm 在 func Region 内换 op）成立，对控制流结构降级不成立。由于本句紧跟在展示"scf.for 消失"的输出之后，初学者很容易读成"scf.for 的 Region 会保留下来换内容"，与实验结果矛盾；若限定主语为"外层 func 的 Region 作为容器一直复用"则成立。建议明确限定。
- **置信度**：中。机制已由输出实测核实；但"Region 复用"存在"指 func Region"的成立读法，故列存疑而非错误。

## 【建议】

#### 1. 第 4 节步骤④ 的 cond_br 行混用源码名与 round-trip 名，在源码和输出里都搜不到
- **原文**：“`cf.cond_br %neg, ^bb1(%c0 : i32), ^bb2(%x : i32)`”
- **依据**：这行是"源码值名（`%neg`、`%c0`、`%x`）＋round-trip 块名（`^bb1`、`^bb2`）"的混血：源码里是 `cf.cond_br %neg, ^neg_zero(%c0 : i32), ^merge(%x : i32)`，实验①输出是 `cf.cond_br %0, ^bb1(%c0_i32 : i32), ^bb2(%arg0 : i32)`。教程第 6 节错误 6 自己强调"打印出来的名字在源码里搜不到"，而这一行恰好在两种文本里都精确搜不到，初学者逐行对照时会困惑。技术关系本身无误（真分支带 %c0、假分支带 %x 与代码一致），建议统一为源码版或输出版之一。
- **置信度**：高。源码与输出均已核对。

#### 2. 遗漏一个手写 CFG 时的必知坑：入口块禁止有前驱（回边不能画到 ^bb0）
- **原文**：“`^bb0` 没有前驱，`%x` 在块头出生”
- **依据**：“没有前驱”在 MLIR 里不是"恰好没有"而是**禁止有**：`cf.cond_br` 的官方 ODS 描述明确“not allowed to target the entry block for a region”；本机实测手写回边指向入口块（`cf.br ^entry`，`^entry` 为函数体首块）报 `error: entry block of region may not have predecessors`。本日教读者手写多块 CFG（`branch_relu`），且实验⑤刚展示"回边"概念（回边指向循环头 `^bb1` 而非入口）——初学者下一步自己手写循环时几乎必然把回边画到 `^bb0` 上并撞到这条报错，而五个探针未覆盖它。建议在 3.2 或第 6 节补一句话预警。
- **置信度**：高。ODS 描述与本机解析实测双重核实。
