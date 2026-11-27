# 第 59 天技术校对报告

## 【错误】
#### 1. 开篇对 `col` 执行 `reshape(12)` 的结局写错：实际是元素数报错，不是静默拷贝
- **原文**：“对这四个对象各执行一次 `reshape(12)`，预期三种结局（本机真实运行）：`x` 得到零拷贝视图；`xT` 与 `col` 的读序非等差、无法仿射表达，numpy 静默拷贝（mini.reshape 判 reject）；`z` 虽然不连续，但读序是步长 2 的等差数列，照样零拷贝——这就是「判据是仿射性不是连续性」的最小反例集。”
- **依据**：`col = x[:, :2]` 的形状是 (3,2)，只有 6 个元素，不是 12 个。本机实测（numpy 1.26.4）：`col.reshape(12)` 抛出 `ValueError: cannot reshape array of size 6 into shape (12,)`；`mini_reshape(col, (12,))` 同样返回 `('error', 'cannot reshape array of size 6 into shape (12,)')`，即 mini 判的是 error 而非 reject。`col` 落入「numpy 静默拷贝 / mini 判 reject」那一档的前提是拍扁目标为 `(6,)`（判定表 C11 正是这么写的，reject/copy 对拍 ok，见 `code/outputs/reshape_lab.txt`）。因此本句在 `reshape(12)` 目标下把 `col` 归入 copy/reject 组是错的：它的真实结局是第一关元素数报错，「numpy 静默拷贝」「mini.reshape 判 reject」两个断言对 col 均不成立。
- **置信度**：高。已在环境（Python 3.11.4 / numpy 1.26.4，与教程声明版本一致）实际运行验证，且与冻结输出中 C11 用例的目标形状互相印证。

#### 2. 三条报错消息并非「逐字抄自 numpy」，且判定表并未对拍消息文本
- **原文**：“- **报错口径与 numpy 完全一致**：`infer_shape` 的三条消息逐字抄自 numpy 的 `ValueError`（判定表 C14/C15 对拍的就是这两边），读者拿报错信息就能和真实框架互相印证。”
- **依据**：在教程声明的环境（numpy 1.26.4）实测，numpy 的真实报错为：`(5,3)` → `cannot reshape array of size 12 into shape (5,3)`（逗号后无空格）；`(-1,5)` → `cannot reshape array of size 12 into shape (5)`（显示的形状里根本没有 -1，只打印已知维）；只有 `can only specify one unknown dimension` 一条逐字一致。而 mini/README 展示的是 `... into shape (5, 3)`（Python 元组 repr，带空格）与 `... into shape (-1, 5)`——前两条与 numpy 文本均不相同，第二条差异实质性。另外「C14/C15 对拍的就是这两边」也不成立：`reshape_lab.py` 判定表对 error 用例只比较结论（`if v1 == "error" and v2 == "error": ok = True`），从不比较消息文本。「读者拿报错信息就能和真实框架互相印证」恰好会在第二条上让读者对不上。
- **置信度**：高。已对 numpy 1.26.4 实测三种输入的完整报错文本，并与 `code/outputs/reshape_lab.txt` 第 21/23/25 行的 mini 消息逐字符比对。

#### 3. 选做练习第 1 条预测错误：把目标类型改成 `3x2x2` 实际能通过验证
- **原文**：“1. 把 `@expand_wrong_group` 的目标类型从 `3x3x2` 改成 `3x2x2`，先预测 `mlir-opt` 的行为（预期：通过，因为 3×2 = 6？不——源第 1 维是 4，3×2=6 ≠ 4 仍应被拒；再改成 `2x2` 才对）；”
- **依据**：用 mlir-opt-18（LLVM 18.1.8，与教程环境一致）实测：`memref.expand_shape %arg0 [[0], [1, 2]] : memref<3x4xf32> into memref<3x2x2xf32>` 通过验证（exit=0）。原因：reassociation 组 `[1,2]` 的乘积 2×2=4 恰好等于源第 1 维大小 4，合法——这与 `reshape_views.mlir` 里本来就合法的 `@expand_metadata`/`@roundtrip` 完全同款。原文的「3×2=6」把组乘积算错了维度（那是原 `3x3x2` 的组 3×2），推出的「仍应被拒」与实测相反；且「再改成 `2x2` 才对」指的组 2×2 正就是 `3x2x2` 这一步，整句自相矛盾。按原文操作的学生会预测「被拒」，实测却通过，练习目标（训练预测能力）落空。
- **置信度**：高。已把该函数单独提取为 MLIR 文件并用 mlir-opt-18 实际运行验证（exit=0）。

## 【存疑】
#### 1. 「报错文本直指打包条件——这与 try_view 的判定完全同口径」过于绝对，三个房间的判据并不相同
- **原文**：“3. **Verifier 拦对了什么、漏了什么**。`bad_reshape.mlir` 的三个房间（非连续源合维 / reshape 吃非 identity 源 / 分组尺寸 4≠3×2）全部被静态拒绝，报错文本直指打包条件——这与 `try_view` 的判定完全同口径；但 `reshape_gap.mlir`（`3×4 → 5×3`，静态可见的 12≠15）**通过了**。mini.reshape 的 `infer_shape` 必须补上这一关，而且要放在 try_view 之前（便宜的事先做）。”
- **依据**：逐房间实测（LLVM 18.1.8）的真实报错文本：房间 1 是 `'memref.collapse_shape' op invalid source layout map or collapsing non-contiguous dims`（确属打包条件）；房间 2 是 `'memref.reshape' op source memref type should have identity affine map`（identity 布局要求，不是打包条件）；房间 3 是 `'memref.expand_shape' op collapsed dim size (4) must equal reassociation group size (6)`（分组尺寸检查，也不是打包条件），「直指打包条件」只对房间 1 成立。「完全同口径」有可复现反例：`memref.reshape` 对 z 型源 `memref<2x6xf32, strided<[12, 2]>>` 直接拒绝（实测 exit=1，同样报 identity affine map 错误），而 `try_view` 判 (2,6)/(12,2)→(12,) 是 view（判定表 C12）——MLIR 的 `memref.reshape` 要求源为 identity 布局，严格强于 try_view 的仿射可表达性；两者只是在这三个样例上结论恰好一致。图 2 的注脚反而写对了（「memref.reshape 要求源是 identity 布局」），建议正文向注脚口径收敛。
- **置信度**：高（所有反例均用 mlir-opt-18 实测）；归为存疑而非错误，是因为该句是对「判据等价性」的概括性表述，其中房间 1 的判据确实与 try_view 同口径，房间 3 的检查也确实是元素数守恒的静态版。

#### 2. README 引用的计时数字与「已存 code/outputs/」的冻结输出不一致
- **原文**：“以下均为**本机真实执行结果**（2026-11-12，Python 3.11.4 / numpy 1.26.4 / LLVM 18.1.8，输出已存 `code/outputs/`）。先看四个对象的元信息与读序：”
- **依据**：README 5.3 节的计时块（及第 256 行「16 MiB 输入实测 **42.133 ms**」、第 263–268 行的 42.133 ms / 41.909 ms / 123605 倍）与 `code/outputs/reshape_lab.txt` 不一致：冻结文件里是 41.897 ms / 41.819 ms / 123588 倍（仅 0.34 µs 一致）。我在同一环境复跑得 41.973 ms，同量级，说明两组数字都是真实测量、但来自不同批次——更像冻结输出在 README 定稿后被重新生成过，导致「输出已存 code/outputs/」的对应关系过期。图片 03（`images/03-three-fates.svg`）也带着与 README 相同的 42.133 / 41.909 / 123605。需要核实并择一处理：要么重跑后同步 README、SVG 与冻结文件三处数字，要么在 5.3 节注明「计时随每次运行浮动，以量级为准」。
- **置信度**：高（不一致本身可逐字符核对冻结文件确认）；对「哪一组来自哪次运行」的成因推断为中等置信。

## 【建议】
#### 1. `--expand-strided-metadata` 的描述与本例真实输出不完全相符
- **原文**：“1. **元数据是编译期常数，检查零成本**。`--canonicalize` 把 `expand_shape` 的视图折叠成 `(0,3,2,2,4,2,1)`——offset、sizes、strides 全是字面常数，与我们装箱算法手算的 `(4,2,1)` 逐位一致；`collapse_metadata` 折出 `(0,6,2)`，正是 `z` 型跨步视图的 `strided<[2]>`。`--expand-strided-metadata` 则把视图彻底展开成基址 + 偏移运算（`memref.reinterpret_cast` + index 乘加），这就是后端真正消费视图的方式。”
- **依据**：查看冻结输出 `code/outputs/reshape_views_expanded.mlir`（并复跑确认）：本例中该 pass 的产物全是静态参数的 `memref.reinterpret_cast`（`offset: [0], sizes: [3,2,2], strides: [4,2,1]` 等字面常数），没有任何 index 乘加运算（元数据全静态时直接折成常数）；且 `memref.reshape` 不被该 pass 展开、原样保留在输出第 36 行。「index 乘加」只在元数据含动态值时出现，「彻底展开」对本例过强。建议补一句限定（如「本例元数据全静态，折成常数参数的 reinterpret_cast；memref.reshape 不经此 pass 展开」），避免读者对照输出时找不到 index 乘加。
- **置信度**：高。依据为冻结输出与复跑结果。

#### 2. `infer_shape` 对 -1 以外的负维不设防，与 numpy 在此边界上行为分叉
- **原文**：“    """第一关：元素数量检查 + -1 推断。失败抛 ValueError（口径与 numpy 一致）。"""”
- **依据**：numpy 1.26.4 实测把负维当作待推断维处理：`np.arange(12).reshape(2,-6)` 返回形状 (2,6)；而 `infer_shape((2,-6), 12)` 因 `math.prod((2,-6)) = -12 ≠ 12` 抛「cannot reshape array of size 12 into shape (2, -6)」。两端对 (2,-6) 这类输入一个成功一个报错，「口径与 numpy 一致」在该边界不成立。该边界不在判定表与 200 组随机对拍的生成范围内（除 -1 外不会产生负维），不影响教程主线的正确性；建议在 `infer_shape` 加一行负维检查或在注释中注明此边界差异。另注：numpy 文档只承诺 -1 的语义，负维被推断属实现行为，未在其他 numpy 版本上核实。
- **置信度**：高（两侧行为均在本机实测）；其作为「建议」而非错误，是因为该边界超出教程自身声称并测试的范围。

#### 3. 练习第 2 条直接跑 `mlir-opt bad_reshape.mlir` 看不到房间 3 的报错文本
- **原文**：“2. 跑 `mlir-opt bad_reshape.mlir` 验证预测，注意报错文本 `collapsed dim size (4) must equal reassociation group size` 里的两个数字；”
- **依据**：mlir-opt 遇到第一个验证失败即停止（`bad_reshape.mlir` 文件头注释自己也写明「mlir-opt 遇到第一个错误即停止」），实际运行整份文件只会打印房间 1 的 collapse_shape 错误——冻结输出 `code/outputs/bad_reshape.txt` 也只有这一条。要看到房间 3 的 `collapsed dim size (4) must equal reassociation group size (6)`（我把该函数单独提出来实测确认过此报错确实存在），读者必须先修复/隔离房间 1、2。建议在练习中提示「把三个房间拆成独立文件逐个验证」，否则按字面执行永远到不了那条报错。
- **置信度**：高。整文件运行输出与单函数隔离实测互相印证。

#### 4. 「对多维目标连方向都不对」缺乏可核实的技术含义
- **原文**：“- **常见误解/类比边界**：「源连续才能 view」对一维目标恰好大致成立，但对多维目标连方向都不对——反过来，「源不连续就不能 view」被 `z` 直接证伪。正确的心智模型永远是：**问新读序，不问源连续**。”
- **依据**：「源连续才能 view」只在必要性方向失效（非连续源也可能 view），且失效方向对一维目标（z→(12,)，C12）与多维目标（C8/C9/C13）完全一致；充分性方向（C 连续源对任意同元素数目标都能 view）永远成立，不存在哪个目标维度上「方向反过来」的反例。一维与多维的真实差别是误解失手的频率（多维目标下能保住 view 的非连续源更多，如插 size-1 维）。本段的核心结论「问新读序，不问源连续」正确，建议把「连方向都不对」改为频率式表述（如「多维目标下失效得更频繁」），以免较真的读者找不到「方向相反」的反例。
- **置信度**：中。对措辞意图的判断基于我的读法，不排除原作者另有所指；但所引用的技术事实（充分性恒成立、必要性被 z/C8/C9/C13 证伪）均已通过对拍输出核实。
