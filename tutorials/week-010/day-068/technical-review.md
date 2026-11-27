# 第 68 天技术校对报告

审阅人立场：十年经验 AI 芯片编译器工程师。审阅范围：`tutorials/week-010/day-068/` 的 README、代码、`outputs/` 全部冻结输出与 4 张 SVG。核实手段：在临时目录复跑全部代码与测试（主实验 39/39、验收测试 37/37、`run_all.sh` 输出与冻结输出逐字节一致）；用 numpy 独立对拍排列约定、合并方向 `r[i] = q[p[i]]`、reduce 重映射 `axis → p⁻¹(k)`（50 组随机全对）；用本机 `/usr/lib/llvm-18/bin/mlir-opt`（Ubuntu LLVM 18.1.8）复测全部 5 个探针及补充探针；查证 LLVM 18/19/20 源码中 linalg DataLayoutPropagation 的实际注册模式。总体结论：本日教程的技术密度和实测诚实度很高，绝大多数技术论断（数学推导、Pattern 逻辑、MLIR stock 裁决、收益记账）均经复跑或独立推导验证为正确；发现 1 处跨天引用的事实性错误、1 处过于绝对的表述、3 处可改进点。

## 【错误】

#### 1. 「第 52 天多使用者限制第二次上岗」的引用计数与第 66 天自述矛盾
- **原文**：“第 52 天的「多使用者限制」今天第二次正式上岗（Day 65 用过一次）”
- **依据**：该断言说 Day 52 的多使用者结论此前只被正式使用过一次（Day 65）。但 `tutorials/week-010/day-066/README.md` 第 5 行（前置准备）明确写道：“第 52 天「融合的多使用者限制」的结论继续上岗”，且 Day 66 正文（3.2 节、场景 E）实际执行了唯一使用者检查与多使用者反例测试；Day 67 的前置准备虽说明恒等消除不需要该检查，但也没有否定 Day 66 的使用。因此到第 68 天为止，Day 52 的结论至少已在 Day 65 与 Day 66 两次正式上岗，今天是第三次（或更多），括号里“Day 65 用过一次”遗漏了 Day 66。这是跨天交叉引用的事实性错误，不涉及编译原理本身，但会误导读者拼装本周知识的复用链路。
- **置信度**：高。day-066/README.md 的原文可直接核对，无需推断。

## 【存疑】

#### 2. 「一字不改地复用」Day 65 合并 Pattern 的表述过于绝对
- **原文**：“Day 65 的合并（`r[i] = p_inner[p_outer[i]]`，恒等时透传）一字不改地复用”
- **依据**：按“规则/公式”的读法该句成立——合并方向 `r[i] = perm_inner[perm_outer[i]]`（Day 68 代码 `merge_adjacent_transposes` 的 docstring 与实现，`layout_prop_lab.py` 第 395–419 行）与 Day 65 的 `compose_perm`/`merge_consecutive_transpose`（`day-065/code/transpose_elim_lab.py` 第 90–96、270–299 行）在数学上完全一致（本报告用 numpy 对拍核实）。但按“代码逐字复用”的读法则不成立：Day 65 的 Pattern 运行在 `MiniGraph`/`MiniTransposeOp` 上，Day 68 的 `merge_adjacent_transposes` 是在新 `Graph`/`Op` 类上的重新实现（约 25 行新代码，含 `_splice`/`dce` 等全新配套机制），两份代码无一字相同。第 5.2 节标题是“编写代码”，读者在此处最容易把“一字不改”理解成代码级复用，随后去 Day 65 的文件里找同名函数会扑空。建议改述为“规则原样复用（在新 Graph 类上重实现）”。第 2 节的“合并规则不改一行”因主语是“规则”，问题较小，但同理可更精确。
- **置信度**：高（两份代码确实不同、规则确实一致）；分级为存疑而非错误，是因为该句在“规则复用”的读法下并不构成技术错误，取决于读者如何断句。

## 【建议】

#### 3. 5.1 节文件树遗漏 `code/make_images.py`
- **原文**：“    ├── run_all.sh                一键复跑”
- **依据**：5.1 的目录树逐项列出了 `code/` 下的 8 个文件与 `outputs/`，但实际目录中还有一个 34 KB 的 `make_images.py`（4 张 SVG 的生成脚本）未列入。相邻各天的惯例是列入该项：day-067 的目录树含“├── make_images.py             # 生成 4 张 SVG 的脚本”。遗漏会让想复现或修改配图的读者不知道图的来源脚本，也削弱了“图片可再生成”的可信度。在 `run_all.sh` 行与 `outputs/` 行之间补一行即可。
- **置信度**：高（文件客观存在，day-067 有对照惯例）。

#### 4. 可补一句 `--test-linalg-data-layout-propagation` 的存在性说明，让「实测结论」更无懈可击
- **原文**：“（linalg 没有注册任何 transpose 传播规则——这是实测结论，不是猜测）”
- **依据**：该论断经两条独立途径核实为真：① 实测——本机 LLVM 18.1.8 上 `mlir-opt --help` 确实注册了一个名字很像在做这件事的 test-only pass `--test-linalg-data-layout-propagation`，但对 `push_probe.mlir`、`sandwich_probe.mlir` 以及新构造的 transpose→generic 探针运行后 IR 均原样返回（本报告复测）；② 源码——LLVM 18 `mlir/lib/Dialect/Linalg/Transforms/DataLayoutPropagation.cpp` 的 `populateDataLayoutPropagationPatterns` 只注册 `BubbleUpPackOpThroughGenericOpPattern`、`PushDownUnPackOpThroughGenericOp`、`PushDownUnPackThroughPadOp` 三个模式（对象是 `tensor.pack`/`tensor.unpack`，不是 `linalg.transpose`），LLVM 19/20 同文件亦无 transpose 传播模式（已核对 release/19.x、release/20.x 源码）。问题在于：读者若在 `mlir-opt --help` 里 grep “propagation”，会看到 `--test-linalg-data-layout-propagation` 和 `--sharding-propagation` 两个名字，容易怀疑教程结论。建议在正文或探针注释里补一句“`--test-linalg-data-layout-propagation` 是 test-only 通道，只传播 tensor.pack/unpack，对本探针原样返回”，把这条实测结论钉得更死。
- **置信度**：高（实测 + LLVM 18/19/20 三版源码核对）。

#### 5. 5.2 节 `_splice` 改写机制的因果句读不通，易让初学者误解 DCE 对象
- **原文**：“改写后 `E` 的旧结点因唯一使用者已换成 `t` 而被 DCE 回收”
- **依据**：代码实际机制（`layout_prop_lab.py` 第 358–383 行）是：改写前 `t` 是 `E` 的唯一使用者；`_splice` 把 `t` 的位置替换为 `(t2, e2)` 并把全图对 `t` 的引用改名为 `e2` 之后，`t` 结点消失，旧 `E` 因此**失去**全部使用者，被 `g.dce()` 按“从 return 不可达”回收。“唯一使用者已换成 `t`”按字面读是“E 的使用者变成了 t”，方向正好拧了（t 本来就是 E 的使用者，改写后它没了而不是换了进来）。结论（旧 E 被 DCE 回收、算子不增殖）本身正确，但这句话的因果表述对初学者是理解障碍，建议改为“旧 `E` 的唯一使用者 `t` 已被替换删除，`E` 从 return 不可达而被 DCE 回收”。
- **置信度**：高（机制经代码阅读与 39/39 实测交叉验证；仅句子表述问题，不影响技术正确性）。

## 复核记录（供续跑参考）

- 复跑环境：Python 3.11.4 / numpy 1.26.4 / Ubuntu LLVM 18.1.8（`/usr/lib/llvm-18/bin/mlir-opt`），全部在 `/tmp/opencode` 临时目录进行，未触碰仓库冻结产物。
- `layout_prop_lab.py`：PASS 39 / FAIL 0，输出与 `outputs/layout_prop_lab.txt` 一致（CRLF 归一后 diff 为空）。
- `test_layout_prop.py`：PASS 37 / FAIL 0。`run_all.sh` 输出与 `outputs/run_all.txt` 一致。
- 独立数值核实：`T_p(A)[idx] = A[idx∘q]`（q=p⁻¹，与 `np.transpose` 文档一致）；三明治合并 `r[i]=q[p[i]]`（外 p 内 q）随机对拍为真；必做练习 `T_(0,2,1)(Neg(T_(1,2,0)(x)))` 的 `r=(1,0,2)`、终态转置数 1 为真；reduce 重映射 50 组随机全对；reshape 同 shape 错值反例复算为真；tosa 折叠产物 `dense<[[1,-4],[-2,5],[3,-6]]>` 与 `outputs/tosa_const_probe.fold.mlir` 一致。
- MLIR 复测：`--canonicalize`（push/sandwich 探针）、`--convert-linalg-to-loops`（6/3/3 vs 2/1/1）、`--tosa-layerwise-constant-fold`、`--test-linalg-data-layout-propagation`（无变化）、`--linalg-fuse-elementwise-ops`（无变化）、`--sccp`（不折 `linalg.transpose(const)`，与探针注释的“对照”说法一致）。
- SVG：4 张均为有效 XML、可被 rsvg-convert 渲染、无文字越界，图中数值/计数/单位与冻结输出一致；图片链接与图注齐全。本次审阅未新增图片：现有 4 张已覆盖全貌、机制、前后对照与约束裁决表，reduce 重映射与 reshape 反例在 04-constraints.svg 中已有带数值的一行裁决，新增图无明显收益。
