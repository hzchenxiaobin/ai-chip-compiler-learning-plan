# 第 38 天技术校对报告

**审阅范围**：`tutorials/week-006/day-038` 的 README.md、`code/` 全部源码与 8 个 `.mlir` 用例、`images/` 三张 SVG。
**核实方式**：在临时目录用仓库源码全新构建 mini-opt 并重放 `run_all.sh` 全部 7 步，正例/负例输出与退出码和 README 逐字比对；另做 6 组探针实验（f64 类型槽、括号类型语法、同一 .mlir 混合两类错误、内维不匹配 matmul 回归、删除 Ops.h 两个 include 的重编译、constant assemblyFormat 变体重编译）；上游 .td 断言逐条对照本机 `/usr/lib/llvm-18/include`（LLVM/MLIR 18.1.8）源文件与 GitHub llvm-project release/18.x。除下列条目外，教程的主要技术论断——`Pure`/`SameOperandsAndResultType`/`F64ElementsAttr`/`AllTypesMatch` 的上游定义位置与原文、四条负例的真实报错与"解析期/验证期"拦截时机、f64 对比实验、错误 1/2 的"踩坑"复现、Day 25/26/32/43/47/51/60/61/124 交叉引用、手算数值 A·B=[[58,64],[139,154]] 等——均核实无误。
**配图审阅**：新增 `images/04-parse-vs-verify.svg`（图 4，插入第 6 节错误 4"原因"之后），并对 `02-ops-anatomy.svg` 的一处双重转义做了最小修复（见【建议】3）。

## 【错误】

#### 1. 逐元素 pretty 语法示例写成了带括号的类型列表，逐字输入会被解析器拒绝
- **原文**：“`mini.add %m, %bias : (tensor<2x2xf32>, tensor<2x2xf32>) -> tensor<2x2xf32>` 合法”
- **依据**：括号类型列表 `(tensor<...>, tensor<...>) -> ...` 是泛型形式（`--mlir-print-op-generic`）的语法，不属于 assemblyFormat 生成的 pretty 语法。用仓库代码构建的 mini-opt 实测：`mini.add %x, %y : (tensor<2x2xf32>, tensor<2x2xf32>) -> tensor<2x2xf32>` 在解析期即被拒，报 `custom op 'mini.add' invalid kind of type specified`（rc=1），并非"合法"；正确写法见 5.3 节真实输出（无括号）。第 6 节错误 3 的"现象"行同样写成 `mini.add %m, %bias : (tensor<2x2xf32>, tensor<1x2xf32>) -> tensor<2x2xf32>` 并配验证期报错 `'mini.add' op requires the same type for all operands and results`——带括号的输入到不了验证期，读者按原文逐字复现不出所引报错（仓库里的 `add_bad_shape.mlir` 用的是无括号写法，报错文本本身真实无误）。
- **置信度**：高（已实测两种写法，括号形式确定在解析期被拒；报错文本逐字核对）。

#### 2. arith.constant 示例混用了两种常量写法，`dense<42> : i32` 不是合法 MLIR
- **原文**：“`arith.constant dense<42> : i32` 同款道理”
- **依据**：标量常量应写 `arith.constant 42 : i32`；`dense<...>` 是 ElementsAttr 字面量，类型必须是 tensor/vector 等 ShapedType，不能是 `i32`。用 mlir-opt-18（18.1.8）实测 `arith.constant dense<42> : i32` 报 `error: elements literal must be a shaped type`（rc=1），而 `arith.constant dense<42> : tensor<1xi32>` 合法（rc=0）。该行想说明的原理（AllTypesMatch 让类型只写一遍）本身正确，但示例文本不可运行，宜改成两种合法形式之一。
- **置信度**：高（本机 mlir-opt-18 实测两种形式）。

#### 3. tblgen 报错引文与真实输出不一致
- **原文**：“不 include 这行，tblgen 会报 "SameOperandsAndResultType was not declared"。”
- **依据**：在临时副本删去 `include "mlir/Interfaces/InferTypeOpInterface.td"` 后重新构建，mlir-tblgen（18.1.8）的真实报错是 `MiniOps.td:85:40: error: Variable not defined: 'SameOperandsAndResultType'`（每个使用点各报一次），并非引文里的 "was not declared"。"必须 include 这一行"的结论本身正确（已实测复现），但教程反复强调"报错要逐字看"，引文应与真实输出一致，否则读者按引文搜索排查会落空；`code/mini/include/mini/MiniOps.td` 第 22～24 行注释有同样的引文，需一并修正（本报告仅记录，不改原文）。
- **置信度**：高（本机复现，输出逐字核对）。

## 【存疑】
- 无。

## 【建议】

#### 1. AlwaysSpeculatable 的通俗解释偏向"编译期求值"，与上游注释本义有偏差
- **原文**：“即两件事：无内存副作用（NoMemoryEffect），且可提前到编译期推测求值（AlwaysSpeculatable）。”
- **依据**：上游 `SideEffectInterfaces.td` 中 `def Pure : TraitList<[AlwaysSpeculatable, NoMemoryEffect]>;` 的原文注释是 "Always speculatable operation that does not touch memory. These operations are always legal to hoist or sink."（已对照本机 18.1.8 头文件核实）。"可推测"的本义是"可无条件提前执行（如外提出条件分支）或下沉而不出错"，"编译期求值"只是它在常量折叠等场景下的推论之一；建议改成"可无条件提前执行（外提/下沉都安全）"，与 Day 51 融合要"搬动算子"的叙事也更贴合。引文里的 TraitList 定义本身逐字准确，不影响教程主线正确性。
- **置信度**：高（上游定义已核实；仅通俗化措辞可更精确）。

#### 2. "Day 41 拼出第一张端到端 mini IR"与今日"第一次完整跑通"存在叙事张力
- **原文**：“Day 41 拼出第一张端到端 mini IR。今天之后，`MatMul → Add → Relu` 所需的算子全部到齐。”
- **依据**：本日 5.3 节已让完整链路 `pipeline_ok.mlir`（3 个 constant＋matmul＋add＋relu＋return）通过 mini-opt 的解析→验证→打印（rc=0），今日目标也写"整条目标图第一次通过 mini-opt 的'解析 → 验证 → 打印'"；而 Day 41 的教程同样自称"第一张端到端 mini IR 完整走解析、验证、打印三关"。两处"第一"的实际增量是 Day 41 时手写 Verifier 已生效、Pass/Dialect 注册表已接好——建议此句补半句点明差别，避免读者疑惑"今天不是已经跑通了吗"。
- **置信度**：中（Day 41 教程已存在并核对其表述；属内部叙事一致性，非硬性技术错误）。

#### 3. 图 2 泛型对照行有 XML 双重转义，"<{…}>"在浏览器里显示成字面 &lt;{…}&gt;
- **原文**：“注意 constant 的数据全在 `<{value = …}>` 属性里，操作数列表是**空的** `()`”
- **依据**：`images/02-ops-anatomy.svg` 第 89 行把说明写成了 `&amp;lt;{…}&amp;gt;`（双重转义），XML 解析后的文本内容是字面的 `&lt;{…}&gt;`，浏览器里显示为"&lt;{…}&gt;"而不是"<{…}>"，与正文强调的 `<{value = …}>` 写法不一致（同一行的泛型 IR 主体部分转义正确，仅此一处漏改）。已按"最小修复"原则将该处改回 `&lt;`/`&gt;`，其余内容未动，修复后 SVG 仍为有效 XML。
- **置信度**：高（用 ElementTree 解析该 SVG 并输出渲染文本验证）。
