# 第 50 天技术校对报告

> 校对环境：与教程声明一致（Ubuntu `libmlir-18-dev` 18.1.8、GCC 9.4.0、aarch64 Linux）。已在 `/tmp/opencode/day050-verify/` 副本中完整重新构建 mini-opt 并复跑 `run_tests.sh`：15/15 通过（7 正例 rc=0＋8 负例 rc=1），全部报错文案、round-trip 输出、op 计数 remark 与教程及 `outputs/` 冻结记录逐字一致；第 6 节三个"真实踩坑"（CMake 登记、窄约束、漏规则 5）均已独立复现。以下意见只针对无法通过运行验证或与已核实事实相悖的表述。

## 【错误】
#### 1. "bias 与 res 一致就等价于与 [M,N] 一致"在 res 含动态维时不成立
- **原文**：“因为规则 4 刚刚查过 `res = [M,N]`（静态维铁证），bias 与 res 一致就等价于与 [M,N] 一致。”
- **依据**：规则 4（`MatmulRules.h` 的 `verifyMatmulShapes`）对 res 的检查用的是 `staticallyCompatible`——res 的维为 `?` 时是保守放行，并非"铁证"；因此 res 含动态维时"bias 对 res 一致"严格弱于"bias 对 [M,N] 一致"。本机用仓库代码实测反例：`lhs: tensor<3x2xf32> · rhs: tensor<2x2xf32> → res: tensor<?x2xf32>, bias: tensor<4x2xf32>`，规则 1～4 全过（res 的 M 维动态，无法反驳 M=3），规则 5 中 `classifyShapePair(4x2, ?x2)` 把动态维跳过后判为 Same，整体 rc=0 放行——而 bias 的 4 对 lhs 静态给出的 M=3 是可证明的非法，若按 [M,N]=[3,2] 比较应判 Mismatch 拦下。即该等价性命题只在 res 最后两维全静态时成立；文中不加限定地断言"等价"，且"（静态维铁证）"的说法与 3.3 节"任一方动态 → 放行"的口径自相矛盾。图片 `images/03-rule-union.svg` 右卡中"规则 4 刚查过 res = [M,N]，bias 对上 res 就等价于对上 [M,N]"重复了同一论断，修正时需一并处理。修改方向：把论断限定为"res 相应维为静态时二者等价；res 有 `?` 时对 res 比更宽松（保守放行）"，或改为直接与 [M,N] 比较。
- **置信度**：高——反例在当天代码上实际运行（rc=0），判定路径可从 `MatmulRules.h`/`ShapeRelation.h` 源码逐行推出。

## 【存疑】
#### 1. "Lowering 到循环时中间结果必须先写回内存再读出"表述过于绝对
- **原文**：“将来 Lowering 到循环时它要先写回内存、再被 `relu` 读出来”
- **依据**：作为一般性编译器论断存在反例：MLIR 自己的 linalg tile-and-fuse、以及带跨 kernel 缓存复用的硬件，都可以让未融合 IR 的中间结果不落 DRAM。该表述只在"逐算子独立生成 kernel、无跨 kernel 缓存复用"的朴素 Lowering 模型下成立。教程后续第 72 天自己也是把它作为理想化假设处理的（原文明确"今天是**无缓存复用口径**：假设 kernel 之间交接必须经过 DRAM……算出的是融合收益的一阶理想值"），且图 2 的措辞是"先写回内存再读出来的**候选**"，比正文更准确。建议此处补一句限定（例如"在逐算子生成 kernel 的朴素 Lowering 下"），避免读者把它当成 MLIR 的普遍规律。
- **置信度**：中——语义在项目自身后续（第 71/72 天）的口径内自洽，问题只在于本句以无条件断言的形式出现；不影响当天任何代码或结论。

## 【建议】
#### 1. 图 3 右卡有一行文本截断，句子不完整
- **原文**：“把 `MatmulVerifier.cpp` 里的四条 matmul 规则提取成 `MatmulRules.h`，两个算子调用同一个函数”
- **依据**：`images/03-rule-union.svg` 右卡第 204 行处的文本是"一行转发 verifyMatmulShapes()——共享头文件 MatmulRules.h 今天刚从"，句子在"今天刚从"处戛然而止（来源为 `code/make_images.py` 第 413 行的生成文本本身就写断了），缺"MatmulVerifier.cpp 提取"等宾语；同一卡片下方还有一处"就等价于对上 [M,N]"（与【错误】第 1 条同源）。SVG 本身是有效 XML、可正常渲染，但截断句会降低图注的可读性与可信度，建议修正生成脚本后重新生成该图。
- **置信度**：高——直接从 SVG 与 make_images.py 源文本核对。

#### 2. 图 4 底部验收口径算式把回归测试重复计数
- **原文**：“写 15 个 IR 测试：7 个正例（含"老图原样通过"的回归测试）＋8 个负例（每条规则至少一个反例）”
- **依据**：`images/04-verifier-tests.svg` 底部写"验收口径：7 正例 + 8 负例 + 1 张老图回归 = 15/15"——`target_graph_unfused` 本身就是 7 个正例之一（README 第 5.3 节正例列表第 6 行），再单列"1 张老图回归"会让人按 7+8+1=16 理解，与"15"对不上；README 原文的"7 正例（含回归）＋8 负例"才是正确口径。图为冻结产物、正文正确，属于图内文字与正文不一致的小瑕疵。
- **置信度**：高——README、run_tests.sh 与冻结输出三方核对一致。

#### 3. 图 4 把未融合图的 matmul 结果写成 `%mm`，与真实 IR 的 `%m` 不一致
- **原文**：“%m = mini.matmul %a, %b        : 2x3 · 3x2 -> 2x2”
- **依据**：`target_graph_unfused.mlir`（以及 README 第 1 节的目标图）中 matmul 的结果 SSA 名是 `%m`、add 的结果是 `%s`；`images/04-verifier-tests.svg` op 计数卡写的是"中间结果 %mm（2x2）与 %s（2x2）都是 SSA 值"。数值（2x2）与结论都正确，仅 SSA 名与真实 IR 不一致，初学者拿图对 IR 时会产生疑惑。
- **置信度**：高——`grep` 与冻结输出 remark 均可核对。

#### 4. 冻结输出中的文件路径与当前仓库布局不一致
- **原文**：“完整记录在 `code/outputs/test-summary.txt`”
- **依据**：`code/outputs/test-summary.txt`、`count-unfused.txt`、`count-fused.txt` 内的诊断行带旧路径前缀 `tutorials/day-050/code/...`（缺 `week-008/`），首行 `mini-opt:` 指向 `/tmp/opencode/day050-build/bin/mini-opt`。这些是真实运行记录、内容本身无误（报错文案与本次复跑逐字一致），但读者在本仓库按 `tutorials/week-008/day-050/` 对路径时会发现对不上。冻结产物不宜改写，建议后续批次生成时直接在最终路径下运行，或在教程中说明记录时的路径环境。
- **置信度**：高——逐行比对冻结文件与本次 `/tmp` 复跑输出。

#### 5. 两处"逐字/全文"级别的引用保真度声明偏松
- **原文**：“省略了中文注释和 shape 规则的后半段描述；description 逐字保留”
- **依据**：该括注本身前后矛盾：所省略的"shape 规则后半段"正是 `MiniOps.td` 中 description 的一部分（`Shape rules are the union of the two member ops: ...` 一段），说"逐字保留"又声明省略了一半，读者到仓库对照时会发现 description 比教程展示的长。已展示部分确为逐字复制（含公式段），问题只在措辞。类似地，5.2 节"`FusedAddReluVerifier.cpp` 全文——短到可以整体贴出"实际省略了文件头注释、include 与两行函数内注释（可执行语句与报错文案完整无缺）。两处都不影响技术正确性，建议改为"节选、所引部分逐字"之类的准确说法。
- **置信度**：高——与仓库 `MiniOps.td`、`lib/FusedAddReluVerifier.cpp` 逐行 diff 核对。
