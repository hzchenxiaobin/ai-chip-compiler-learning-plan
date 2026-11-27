# 第 60 天技术校对报告

校对范围：`tutorials/week-009/day-060/` 的 README.md、`code/` 全部代码与冻结输出、`images/` 全部 4 张 SVG。所有可运行论断均在本机复现：Python 3.11.4 / numpy 1.26.4 / Ubuntu LLVM 18.1.8（`mlir-opt-18`、`mlir-cpu-runner-18`）/ Linux aarch64，与教程声明的环境一致。`broadcast_lab.py` 9/9、`test_broadcast.py` 48/48、`run_all.sh` 七步（含 canonicalize 折叠、loops 降级、cpu-runner 33/25/101/206、bad_broadcast exit=1）、第 7 节两道练习的预期值（`(8,1000,256)`、`(1,0)`）与选做挑战的预测（报错 `inferred ... to be 2, but found 3`；修好后 13/25/101/206）全部复现通过。MLIR shape 方言语义核对自 llvm-project release/18.x 分支源码 `mlir/include/mlir/Dialect/Shape/IR/ShapeOps.td`（与本机 18.1.8 同线）。判定表 16 组、S/U 用例、错误消息逐字对拍均与冻结输出一致；未发现概念定义层面的错误。以下为具体发现。

## 【错误】

#### 1. 开篇把 `np.broadcast_shapes` 的推导侧报错安到了 `+` 加法运算符头上

- **原文**：“从一个每个推理框架都要回答的问题开始：全连接层前面有一步 bias 相加，`logits (8, 1000, 256) + bias (256,)`。两个形状完全不同的张量相加，框架**既没报错也没复制 256 份 bias**——输出形状 `(8, 1000, 256)` 是推导出来的。但你把 bias 写成 `(256, 1)`（同样有 256！），同一行加法立刻爆炸（本机 numpy 1.26.4 实测）：”
- **依据**：本机 numpy 1.26.4 实测：`np.zeros((8,1000,256),dtype=np.float32) + np.zeros((256,1),dtype=np.float32)` 抛出的是 `operands could not be broadcast together with shapes (8,1000,256) (256,1)`（执行口径）；紧跟其后的代码块引用的 `shape mismatch: objects cannot be broadcast to a single shape. Mismatch is between arg 0 with shape (8, 1000, 256) and arg 1 with shape (256, 1).` 是 `np.broadcast_shapes((8,1000,256),(256,1))`（推导口径）的消息，不是加法运算符的报错。教程自身在两处写对了这条区别——5.2 节“numpy 有两条口径——推导侧（`np.broadcast_shapes`）说 `shape mismatch: ...`，执行侧（`a + d`）说 `operands could not be broadcast ...`”，第 6 节错误 1 引用的正是执行口径原文——开篇这段与两处自相矛盾，读者拿这句消息去框架里对不上号。图 2（images/02-mechanism.svg）的“翻车现场”一栏标注“（真实报错）”后引用同一句推导口径消息，是同一处错误的图内复制。
- **置信度**：高。本机逐字复现两种报错；教程内部 5.2 节与错误 1 可互证。

#### 2. 图 2 把 `(100000, 3)` 的 f32 逻辑量写成「12 MiB」，与正文「约 1.2 MB」相差约 10 倍

- **原文**：“- **对应到技术上是**：第 57 天的偏移公式 `物理偏移 = Σ idx×stride` 里，广播维的 stride 记 **0**——下标怎么变，地址都不动。`b (3,)` 当 `(2,3)` 用：新 strides `(0, 1)`，`偏移 = i×0 + j×1`；本机实测 `np.broadcast_to(b, (2,3)).strides == (0, 8)` bytes，且 `np.shares_memory` 为 True。把 `b` 广播成 `(100000, 3)`（约 1.2 MB 的 f32 逻辑量），底层仍只有 3 个元素的家。”
- **依据**：正文与实验代码（`broadcast_lab.py` 用 `np.zeros(3, dtype=np.float32)`）均为 f32：100000×3×4 B = 1,200,000 B ≈ 1.2 MB（≈ 1.14 MiB）。但 images/02-mechanism.svg 底部“关键结论”一栏（生成脚本 `code/make_images.py:349`）写的是“b 的 12 MiB 版本 (100000,3) 与 3 个元素共享存储（实测）”——即使按 f64（2.4 MB）也对不上，12 MiB ≈ 12,582,912 B，约 10 倍偏差。读者按图估算广播省下的内存会错一个量级，恰好削弱该图要论证的「扩展零拷贝」结论的直观冲击力（1.2 MB 视图只占 12 B 存储，本身已足够震撼，无需夸大）。注意：错误在 SVG 及其生成脚本里，正文这行本身是对的。
- **置信度**：高。算术可复核；SVG 原文与生成脚本已逐字定位。

## 【存疑】

#### 3. 「错误要等运行期才暴露」——按 shape 方言规范，失配结果是「错误形状」值，不是保证运行期抛错

- **原文**：“2. **失配的形状却静态不报错（缺口）**。`(2,3)` 与 `(4,)` 的 `shape.broadcast` 在 canonicalize 后**原样保留**、exit=0——错误要等运行期才暴露。numpy 和 mini.broadcast 都是静态拦的（`ValueError` / `BroadcastError`），这个缺口和昨天 `memref.reshape` 放行元素数违规是同一类问题：**静态可见的失配，就该在 Verifier 静态拦住**。”
- **依据**：可验证的部分全部属实（本机复现：Verifier 放行、`--canonicalize` 不折叠、exit=0）。但按 LLVM release/18.x `ShapeOps.td` 中 `shape.broadcast` 的规范原文：“In case the resulting shape is undefined, i.e. if corresponding extents are different from each other but none is 1, the result is an error shape. ... If the result type is an extent tensor (and can therefore not hold the error value) the behavior may be undefined.”——失配时该 op 的结果是一个**错误形状值**（错误以值的形式沿数据流传播，`!shape.shape` 类型可承载它），并非保证在运行期“报错”；若结果类型是 extent tensor（`tensor<?xindex>`），规范甚至写明行为可能未定义。本教程的结果类型是 `!shape.shape`，所以更准确的说法是“求值结果是错误形状，何时变成可见错误取决于消费方”。“才暴露”的措辞容易被读成“运行期会抛异常”，与规范有出入；图 4 ②同句复制。列为存疑而非错误，是因为把“错误形状的产生”推迟到求值期说成“运行期才暴露”是可接受的通俗简化，且教程并未展开运行期行为的具体主张。
- **置信度**：中。规范原文来自 release/18.x 分支源码（与本机 18.1.8 同线，已逐字核对）；不确定点仅在于“暴露”一词是否足以构成误导，属程度判断。

## 【建议】

#### 4. 增强赋值的输出形状判据可写得更准——「不小于」只是必要条件，输出本身参与广播

- **原文**：“- **原因**：广播维 stride 0——10 万个逻辑行指着同一排 3 个格子，写哪个都说不清，所以 numpy 把广播视图设成只读；增强赋值要求输出形状**不小于**广播形状，`(3,)` 装不下 `(4,3)`。”
- **依据**：本机 numpy 1.26.4 实测：输出操作数本身参与广播，最终广播形状必须与输出形状完全一致。「不小于」只描述了必要方向：`np.add(np.ones(3), np.ones(3), out=np.full((2,3), -1.))` 合法（输出比输入广播形状 (3,) 大，输入被广播放大）；但 `np.add(np.ones((4,3)), np.ones((4,3)), out=np.zeros((5,4)))` 报错——“大了”却不可达，报错消息 `operands could not be broadcast together with shapes (4,3) (4,3) (5,4)` 本身就把 out 当作第三个广播操作数列出。`(4,1) += (4,3)` 与 `(3,) += (4,1)` 均如正文所述报 `non-broadcastable output operand`。建议把判据改成「输出形状必须恰为全体操作数（含输出自身）广播后的形状：可以更大（如 `(2,3)` 可作 `(3,)+(3,)` 的输出），但不能不可达」，对写编译器的人更可迁移。现有措辞不影响本例解释的正确性。
- **置信度**：高。三个方向（更小、恰好、更大可达/不可达）均已实测。

#### 5. 「Verifier 缺口」讨论可补充 shape 方言自带的相容性约束 op

- **原文**：“2. **失配的形状却静态不报错（缺口）**。`(2,3)` 与 `(4,)` 的 `shape.broadcast` 在 canonicalize 后**原样保留**、exit=0——错误要等运行期才暴露。numpy 和 mini.broadcast 都是静态拦的（`ValueError` / `BroadcastError`），这个缺口和昨天 `memref.reshape` 放行元素数违规是同一类问题：**静态可见的失配，就该在 Verifier 静态拦住**。”
- **依据**：shape 方言其实为这个缺口提供了官方机制：`shape.cstr_broadcastable`（返回 witness，规范写明“"cstr" operations represent runtime assertions”，配合 `shape.assuming` 使用）与 `shape.is_broadcastable`（返回 i1 谓词，“This broadcastable follows the same logic as what shape.broadcast documents”，两者均存在于 release/18.x 源码且本机 `mlir-opt-18` 可解析）。本机实测 `shape.is_broadcastable [2,3],[4]` 在 18.1.8 下不被 `--canonicalize` 折成常数，所以它不能替代静态 Verifier，但把这两个 op 点一句，能让“缺口怎么补”的讨论从“该静态拦”的倡议落到 MLIR 已有的 witness/断言机制上，也为 Day 61 的动态 Shape 约束（cstr_* 正是那时会遇到的 op）埋好伏笔。纯增补，不影响现有论述正确性。
- **置信度**：高。op 存在性与语义出自 release/18.x 源码原文；18.1.8 不折叠 const 情形为本机实测。

#### 6. 5.4 节循环「真实输出」节选把两段循环各取一行拼成连续行，且 `%8` 出现两次

- **原文**：“      %8 = memref.load %2[%arg0, %c0] : memref<2x1xf32>        // c：d1 钉死 0”
- **依据**：`code/outputs/broadcast_add_loops.mlir` 中该行（第 28 行）来自第二个 `scf.for` 嵌套，而同块上方 `%8 = memref.load %1[%arg1] : memref<3xf32>`（第 20 行）来自第一个嵌套，两者之间隔着完整的第二组循环头与 store；且两个 `%8` 在 SSA 中是不同 loop body 里的不同值。README 该代码块以上下文“（真实输出，已存 `code/outputs/`）”引入，虽有 `...` 标示省略、注释也标明了来源，但拼排后形似一段连续输出，仔细的读者可能误以为 `%8` 被定义了两次、或两行在同一次循环里执行。每行引文本身逐字真实。建议在图注或行间加一句「两段循环各取一行」的说明。
- **置信度**：高。与冻结输出逐行核对。

#### 7. 正文与图 1/图 3 引用的随机对拍统计（ok=178、error=122）不在任何冻结输出里

- **原文**：“1. **mini 与 numpy 的判定完全等价**：16 组判定表 + 300 组随机对拍（ok=178、error=122）零失配，连 4 组错误消息都逐字相同——右对齐补 1 后逐维三态，就是对 `np.broadcast_shapes` 的复刻。”
- **依据**：数值本身无误——本机按种子 60 重跑同一随机流程，得 ok=178、error=122，与正文及图 1、图 3 一致。但 `broadcast_lab.py` 的 `check()` 只在 FAIL 时打印 detail（`suffix = f"  ({detail})" if detail and not cond else ""`），故 `code/outputs/broadcast_lab.txt` 第 71 行只有「[PASS] 300 组随机形状推导全部一致」，两处统计数字无法从冻结产物直接核对（对比：`71 组` strides 统计就在输出里）。建议让这组统计在 PASS 时也落进输出（例如单独 print 一行），使图文引用全部可由 `outputs/` 复核。不影响正确性。
- **置信度**：高。统计已复算一致；缺失情况由输出文件直接确认。

---

补充说明：以下高频论断均已逐项核实无误，未列入上文——`(256,)`/`(256,1)`/`(8,1,1)` 三组的推导与预期输出；`np.broadcast_shapes((2,3),(-1,))` 报 `negative dimensions are not allowed`（逐字）；`(1,1)→(1,3,1)` 的 strides `(0,0,0)`；广播视图只读报 `assignment destination is read-only`；`bias.T`/`bias[:, 0]`/`bias[None, :]` 的形状；房间 2 单独验证的 `inferred ... to be 2, but found 3`；选做挑战修好后的 `13/25/101/206`；`shape.broadcast` 折叠/放行行为；图 2 三条 stride-0 物理条带与图 4 meet 真值表（其 None 规则与 `shape.broadcast` 规范公式 `result[i] = lhs[i] if rhs[i] == 1` 在未知维上一致）。图 3 对两条 numpy 报错口径的标注（推导口径/执行口径）是正确的，恰与发现 1 形成对照。
