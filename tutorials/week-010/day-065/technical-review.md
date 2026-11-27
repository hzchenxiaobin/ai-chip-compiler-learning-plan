# 第 65 天技术校对报告

校对范围：`tutorials/week-010/day-065/README.md`、`code/`（transpose_elim_lab.py、test_transpose_elim.py、transpose_chain.mlir、run_all.sh）、`code/outputs/` 全部输出、`images/` 全部 SVG。校对方式：在本机（Python 3.11.4 / numpy 1.26.4 / Ubuntu LLVM 18.1.8 / aarch64，与教程声明环境一致）临时目录完整复跑主实验与验收测试（16/16、33/33 均复现），用 numpy 对拍核实全部排列代数断言，用本机 mlir-opt 复测 MLIR 侧结论，并对照 LLVM 官方源码（llvm-project release/18.x、19.x、20.x、21.x 与 main 分支）核实版本相关论断。

## 【错误】
#### 1. 结合律对拍的“729 组三元组”计数错误，实际是 216 组
- **原文**：“结合律保证先合并哪一对都不影响终点——729 组三元组实测”
- **依据**：`test_transpose_elim.py` 的 A5 用三重循环枚举 3 元排列的三元组：`itertools.permutations(range(3))` 只有 3! = 6 个排列，6³ = 216 组，不是 729（729 = 3⁶，与排列数无关）。用 `sum(1 for _ in itertools.permutations(range(3)))**3` 实测得 216。冻结输出 `outputs/test_transpose_elim.txt` 的 A5 行（“729 组 3 元三元组”）与 README 第 125、374、403 行、图 1/图 2/图 4 的 SVG 文字都带着同一个错数。结论本身（结合律成立、先合并哪一对终点相同）经我本地复算无误，错的是计数。
- **置信度**：高（两种独立方法核实：直接计数 216；代码逐行确认循环边界）。

#### 2. 随机压力对拍的“900 个初始 op、28.2%”是硬编码错值，实际 914 个、27.8%
- **原文**：“300 组共 900 个初始 op（平均链长 3），优化后剩 254 个（28.2%）”
- **依据**：`transpose_elim_lab.py` 第 669 行打印的是硬编码 `300 * 3`（“300 组共 {300*3} 个初始 op”），百分比按 `rand_ops / 9` 计算，即假定初始 op 恰好 900。但该段随机链由 `random.Random(65)` 生成，300 组链长之和实际是 914（两种独立方法核实：按同一 RNG 序列重放求和得 914；给 `run_passes` 打补丁统计每次调用时的 `len(graph.ops)`，末 300 次求和也是 914），平均链长 3.05。真实比例是 254/914 = 27.8%，不是 28.2%（254/900）。README 第 6、318、325、403 行与图 1/图 4 的 SVG 均沿用该错值。剩余数 254 与“300/300 通过”本身是动态真值，无误。
- **置信度**：高（RNG 重放与运行时插桩两法一致；代码行内硬编码可直接读出）。

## 【存疑】
#### 1. “stock 管道里没有这条规则”只对 LLVM 18 成立，LLVM 19+ 已加入该优化，个别未加版本限定的表述过于绝对
- **原文**：“这条优化在 stock 管道里不存在、要自己写”
- **依据**：对 LLVM 18.1.8 该说法完全属实：我核对了 llvm-project release/18.x 的 `mlir/lib/Dialect/Linalg/IR/LinalgOps.cpp`，`TransposeOp` 没有 `fold`、没有 `getCanonicalizationPatterns`，`LinalgDialect::getCanonicalizationPatterns` 只注册 `EraseDeadLinalgOp/FoldTensorCastConsumerOp/InferStaticShapeOfOperands`，均不合并转置链；本机 mlir-opt 实测（memref 与 tensor 两种写法）`--canonicalize` 都原样保留 2 个 `linalg.transpose`，与 outputs 一致。但 release/19.x、20.x、21.x 与 main 分支已加入 `TransposeOp::fold`（一维/恒等排列、仅 tensor）和 `FoldTransposeWithTranspose`（合并连续 `linalg.transpose`，组合规则 `foldedPerms[i] = defPerms[perms[i]]`，与本教程教的 `r[i] = p[q[i]]` 方向一致），官方测试 `mlir/test/Dialect/Linalg/canonicalize.mlir` 的 `@transpose_transpose_fold`/`@transpose_transpose_cancel`（tensor 形态）证明 stock 管道在 19+ 会合并/消除这种链。README 大多数位置已写“本机 LLVM 18.1.8 实测”且准确，但第 34 行这句与第 325 行“这条优化在 stock 管道不存在”、“而管道不会替你消它”未带版本限定，读者换用 LLVM 19+ 复现会得到相反结果。不确定点：19+ 对本教程所用 memref 形态（非 tensor）是否同样合并，本机没有 19+ 环境未实测；上游 `TransposeOp::fold` 注明“仅支持 tensor 类型”，`@transpose_buffer` 测试显示 memref 转置不被折叠，倾向于 memref 形态仍不合并，但这点未直接验证。
- **置信度**：高（18 无此规则：源码 + 本机双重复核；19+ 有此规则：官方源码与官方测试核对；19+ memref 行为未实测，为唯一不确定点）。

## 【建议】
#### 1. README 中 P2 代码摘录把“改写 outer”放在防御检查之前，与真实实现相反，失败路径会留下半改写的图
- **原文**：“原地把 outer 改写成从 inner 的输入直接转一次，再删 inner”
- **依据**：README 5.2 的 P2 片段顺序是：先执行 `outer.perm, outer.input_id, outer.in_shape = (r, inner.input_id, inner.in_shape)` 再 `verify_transpose(...)`，若校验失败 `continue`——此时 outer 已被改写而 inner 未删、也无回滚，图处于半改写状态。真实代码 `transpose_elim_lab.py` 第 288–297 行是先构造 `merged`、先 `verify_transpose(merged...)` 通过后才原地赋值并删 inner（查后再改）。由于该校验按构造是恒真的（`result_shape` 本身由同一 perm 推导），两条路径实际行为一致，教程结果不受影响；但展示给初学者的代码教的是“先改后查”的顺序，若防御分支真能触发就会破坏图。建议把 README 片段改成与真实实现一致的“先构造/先校验、后改写”。
- **置信度**：高（两版本逐行比对；失败路径不可达，故不影响本教程正确性）。

#### 2. “Verifier 的 E4 会先拒绝”对本教程的 mini 实现不成立，能抓住方向反的是数值对拍
- **原文**：“如果实现里还有类型检查，Verifier 的 E4 会先拒绝。”
- **依据**：mini 里 `MiniTransposeOp.result_shape` 是由 `in_shape` 和 `perm` 现算的属性，`verify_transpose` 的 E4 拿它与 `infer_transposed_shape(in_shape, perm)` 比较——两边用的是同一个（可能已经错了的）perm，方向写反时产物“自洽但错误”，E4 照样通过；本教程第 5 节的错误现场正是靠 numpy 数值对拍（`T_q∘T_p` 的值 vs `T_r` 的值）抓出 `(4,3,2) ≠ (3,2,4)` 的。E4 式拒绝只在结果类型独立声明（真实 MLIR：新 op 沿用链终点类型，perm 错则 `TransposeOp::verify` 报 "dim(result, i) ... doesn't match dim(input, permutation[i])"）的实现里成立。建议补一句区分，避免初学者以为 mini 的 E4 自检能防方向反。
- **置信度**：高（mini 代码路径逐行分析；MLIR 侧依据 TransposeOp::verify 的官方源码逻辑）。

#### 3. 遗漏“memref 缓冲身份/别名”这个初学者必知的坑：消除转置对在值语义下安全，在 memref 语义下未必
- **原文**：“MLIR 里对应 `rewriter.replaceOp` 后 `if (innerOp.use_empty()) erase`”
- **依据**：本教程的 MLIR 侧样例是 memref 形态：两个 `linalg.transpose` 各写进一个 `memref.alloc` 的新缓冲，函数返回第二个新缓冲。把它整体消除成 `return %in` 后，返回值与入参变成同一块缓冲（别名/缓冲身份对调用方可观察），这正是上游后来把 `TransposeOp::fold` 与相关折叠限定为“仅 tensor 类型”（main 分支 fold 中 `if (!isa<TensorType>(...)) return failure();`，`@transpose_buffer` 测试保留 memref 转置）的原因。mini 的 `eval` 是 numpy 值语义，`func.return %in` 天然安全，教程结论在本教程内不受影响；但初学者照这句 MLIR 配方把 Pattern 移植到 memref 管道时，缺了“删掉的两个 alloc 与别名可见性”这层检查。建议在 3.3 或常见错误里点一句。
- **置信度**：高（上游源码与官方测试依据；对本教程自身的正确性无影响，属关键坑提示）。

#### 4. 5.1 文件树的 outputs/ 清单不完整，少列了两个真实产物
- **原文**：“└── outputs/                   # 全部真实输出”
- **依据**：`transpose_elim_lab.py` 除生成树中列出的 5 个文件外，还会把 `--canonicalize`/`--convert-linalg-to-loops` 的直接产物写入 `outputs/transpose_chain.canon.mlir` 和 `outputs/transpose_chain.loops.mlir`（代码第 396–404 行），这两个文件实际存在于仓库 outputs/ 目录，但标注“全部真实输出”的清单里没有它们。属文档清单不完整，不影响正确性。
- **置信度**：高（目录实际内容与代码写盘路径核对）。

---

### 附：已核实无误的重点结论（供后续维护参考）
- 组合方向 `r[i] = p[q[i]]`（内层先作用）与恒等判据 `q == inv(p) ⟺ compose(p,q) == 恒等`：36 对 3 元排列 numpy 全量对拍复现通过；与上游 `FoldTransposeWithTranspose` 的组合方向一致。
- `p=(1,2,0)` 阶 3、`p²=(2,0,1)=inv(p)`、`L mod 阶` 消长规律、E1 表（L=1..8 剩 0/1 交替）、三连链“第 1 轮 P2 合并、第 2 轮 P1 消除、第 3 轮不动点”（rounds=3、applied=2）及轮间 IR：全部复现一致。
- MLIR 侧（LLVM 18.1.8）：`--canonicalize` 原样保留（memref 与 tensor 两种写法均实测）、`--convert-linalg-to-loops` 6 层 scf.for、2 行 load、2 行 store（48 读 + 48 写）、单转置对照 3 层循环 1 行 load、`out_shape[i] = in_shape[perm[i]]` 与 LLVM 18 `TransposeOp::verify` 的官方语义一致：均复现/核对无误。
- 图 2 的 strides 数据（A(2,3,4) strides (12,4,1)；转置后 (3,4,2) strides (4,1,12)）：与 numpy 转置视图的 strides 排列规则 `out_strides[i] = in_strides[perm[i]]`（元素单位）一致。
- 主实验 16/16、验收测试 33/33、“19 万倍”引用（第 64 天实测 0.22 µs vs 42.293 ms ≈ 1.9×10⁵）、Day 52/25/66/68 交叉引用：均复现或核对一致。
