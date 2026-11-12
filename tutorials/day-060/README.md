# 第 60 天：Broadcast 规则——两边形状不同，怎么凑到同一张输出表上

> **今日目标**：完成本教程后，你能为任意一组输入形状推导出 Broadcast 的输出形状（从右对齐比较维度、维度为 1 的扩展、未知维度的 meet 规则三条规则出发）；能说清「扩展」不是拷贝数据而是 stride 0 的地址映射；能解释为什么 `(8,1000,256) + (256,)` 合法而 `(8,1000,256) + (256,1)` 报错；并能在 MLIR 里用 `shape.broadcast` 看到编译期形状折叠、用 `linalg.generic` 的 indexing map 看到广播降级成「少一个下标」的循环，最后用 `mlir-cpu-runner` 真实算出结果。
> **预计时间**：学习 40 分钟＋实践 45 分钟
> **前置准备**：第 57 天的 Shape / Stride / Offset 词汇表（偏移公式 `Σ idx×stride`）；第 59 天的 `infer_shape` 校验思路（今天直接复用它的「两形状 → 一形状」推导范式）；Python 3.10+ 与 numpy（本机 3.11.4 / 1.26.4）；`mlir-opt`（本机为 Ubuntu LLVM 18.1.8，另有 `mlir-cpu-runner` 可真实执行）。不需要 NPU。
> **今日产出**：一个 Broadcast 推导器（`code/broadcast_lab.py`，9/9 断言通过，含 16 组判定表、10 组 stride-0 视图对拍、10 组未知维度用例与 300 组随机对拍）、一组独立验收测试（`code/test_broadcast.py`，48/48 通过）、一份 MLIR 双视角示例（shape dialect 编译期折叠 + linalg 广播加法真实执行）、一个 Verifier 错误现场（`code/bad_broadcast.mlir`）以及 4 张示意图。

## 1. 今天解决什么问题？

从一个每个推理框架都要回答的问题开始：全连接层前面有一步 bias 相加，`logits (8, 1000, 256) + bias (256,)`。两个形状完全不同的张量相加，框架**既没报错也没复制 256 份 bias**——输出形状 `(8, 1000, 256)` 是推导出来的。但你把 bias 写成 `(256, 1)`（同样有 256！），同一行加法立刻爆炸（本机 numpy 1.26.4 实测）：

```text
ValueError: shape mismatch: objects cannot be broadcast to a single shape.
 Mismatch is between arg 0 with shape (8, 1000, 256) and arg 1 with shape (256, 1).
```

为什么 `(256,)` 行而 `(256, 1)` 不行？因为 Broadcast 比较形状的方式**不是「两边都有 256 就能配」，而是从最右维对齐、逐位比较**：`(256,)` 右对齐后是 `(1, 1, 256)`，三个位置分别是 `1 vs 8`、`1 vs 1000`、`256 vs 256`，全部相容；`(256, 1)` 右对齐后是 `(1, 256, 1)`，第 1 维 `256 vs 1000` 既不相等也没有 1——失配。

这就是今天的核心问题：**Broadcast 的输出 Shape 推导是一套纯静态的算法（右对齐比较、维度为 1 的扩展、未知维度处理），但它背后还藏着一个物理事实——「扩展」从来不是复制数据，而是 stride 0 的地址映射。** 你在给 mini 编译器写形状推导时，两件事都得管：算不出输出形状，后面的算子无法链接；把「扩展」误解成拷贝，要么浪费内存要么写出错误的访存。

还有一个和昨天 (Day 59) 形成对照的语义分歧：reshape 的 `-1` 表示「这一维帮我算」，很多同学想当然地把 `-1` 也当作广播里的未知维度——本机实测 `np.broadcast_shapes((2, 3), (-1,))` 报的是 `negative dimensions are not allowed`：**在广播里 `-1` 就是负数维度，直接非法**。未知维度需要另一套表示（本文用 `None`，MLIR 用 `?`），这正是明天动态 Shape 的入口。

用一个贯穿全文的小例子（与 MLIR 侧 `broadcast_add.mlir` 用同一份数据，值肉眼可核对）：

```text
a = [[1, 2, 3],       b = [10, 20, 30],   c = [[100],        d = [1, 2, 3, 4]
     [4, 5, 6]]                             [200]]

a(2,3) + b(3,)  → (2,3)，值 [[11,22,33],[14,25,36]]   b 沿行广播
a(2,3) + c(2,1)  → (2,3)，值 [[101,102,103],[204,205,206]]  c 沿列广播
a(2,3) + d(4,)   → error（3 vs 4，既不相等也没有 1）
```

## 2. 先看全貌：今天的内容位于哪里？

![第 60 天全貌：六阶段里程碑、第 9 周日程与 Broadcast 推导在编译链路中的位置](images/01-overview.svg)

**图 1**：三栏从上往下看——今天的课程位置（阶段三·第 9 周第 4 天）、昨天到今天的衔接、Broadcast 推导发生在编译链路的哪一站。

用 4 步把全局串起来：

1. **前 59 天**：阶段一、二打完 C++ 与 MLIR 基础；第 57 天给了 Shape / Stride 词汇表，第 58 天验证了「换元信息免费、换物理要搬家」，第 59 天给 reshape 写了两关 Verifier——`infer_shape` 的「输入形状 → 输出形状」推导范式今天直接复用。
2. **今天把视角从单张量换成两张量**：两个形状不同的操作数凑到一起，输出形状是什么、什么时候非法、「扩展」在内存里到底发生了什么。这是 mini 编译器里算子链接（上一个算子的输出形状喂给下一个算子）的基础检查。
3. **推导是编译期的，物理是运行期的，但都静态可查**：输出形状由 IR 里两个输入类型静态推出（今天用 `mlir-opt --canonicalize` 亲眼看到 `shape.broadcast` 把 `[2,3]` 与 `[3]` 折成 `[2, 3]`）；「扩展」降成循环后只是**少一个下标**（`memref.load %b[%arg1]`），stride 0 是它唯一的物理痕迹。
4. **后续都站在这套规则之上**：明天 (Day 61) 的动态 Shape 把 `None` 换成符号维度；Day 62 的形状特化把 `None` 替换成具体值；融合 Pass 判断两个算子能否共享迭代空间，用的也是「形状能不能广播到一起」。


## 3. 核心概念：先用直觉，再给准确定义

先给一个贯穿的类比：**Broadcast 像竖式加法**。小学做加法 `123 + 7`，从来不是把 7 对到 1 上，而是个位对个位、十位补零——右对齐，缺的位按 0 处理。形状 `(256,)` 对 `(8, 1000, 256)`，就是把 `256` 对到最右边的 `256` 上，前面缺的位补「中性值」。对应到技术上是：**短的形状在左侧补 1（不是补 0），补出来的维参与比较但不贡献地址**——类比到「补 0」就止步了，0 在广播里是一个合法但危险的尺寸（`(0,)` 是空张量），中性值是 1。

### 3.1 右对齐比较维度

- **一句通俗解释**：比较两个形状从最右维开始，短的形状左边当作全是 1；每个位置要么相等、要么一方是 1、要么失配。
- **类比**：竖式加法右对齐个位。
- **对应到技术上是**：`rank = max(len(a), len(b))`，对第 `k` 个位置（从右往左数），`a` 没有这一维就取 1。`(3,)` 对 `(2, 3)`：位置 1 是 `3 vs 3` ✓，位置 0 是 `1 vs 2`（补出来的）→ 2。
- **最小例子**：`(8,1000,256)` 与 `(256,)` → 逐位 `(1,1,256)` → `(8,1000,256)`；与 `(256,1)` → `(1,256,1)` → 位置 1 失配。
- **常见误解**：「形状里有公共数字就能广播」。`(256, 1)` 里明明有 256，照样非法——**位置比数值更重要**；反过来 `(8, 1, 1)` 一个 256 都没有，却能与 `(8,1000,256)` 广播成 `(8,1000,256)`。

### 3.2 维度为 1 的扩展：stride 0，不是拷贝

- **一句通俗解释**：某一维尺寸为 1 的操作数，在这一维上「要几份读几遍同一份」——逻辑上被拉长，物理上纹丝不动。
- **类比**：复读机。你订 100000 期「每日一句」，它还是只有一句，每天读同一句。
- **对应到技术上是**：第 57 天的偏移公式 `物理偏移 = Σ idx×stride` 里，广播维的 stride 记 **0**——下标怎么变，地址都不动。`b (3,)` 当 `(2,3)` 用：新 strides `(0, 1)`，`偏移 = i×0 + j×1`；本机实测 `np.broadcast_to(b, (2,3)).strides == (0, 8)` bytes，且 `np.shares_memory` 为 True。把 `b` 广播成 `(100000, 3)`（约 1.2 MB 的 f32 逻辑量），底层仍只有 3 个元素的家。
- **最小例子**：`np.broadcast_to(np.arange(3), (7, 3))` 与源共享存储；MLIR 里同一个事实写作 indexing map `affine_map<(d0, d1) -> (d1)>`——`d0` 被丢掉，等价于 stride 0。
- **常见误解/类比边界**：「扩展 = 复制」会推出两个错误结论。第一，以为广播费内存（不费，是视图）；第二，以为能写广播结果——**不能**，两个逻辑位置指着同一格，写哪个都说不清（numpy 实测：`assignment destination is read-only`）。另外「1 与任何维相容」也不是取最大值：`(0,)` 与 `(1,)` 广播结果是 `(0,)` 不是 `(1,)`——三态规则是「一方为 1 → 取**另一方**」，0 尺寸维按普通维参与判定。

### 3.3 未知维度：None 的 meet 规则

- **一句通俗解释**：形状里有些维编译期还不知道（动态 Shape），推导输出时要「已知碰已知照常判、已知碰未知听已知的（当它大于 1）、未知碰 1 仍是未知」。
- **类比**：拼图。缺的那块（未知）和已完成的边（已知 d>1）拼，轮廓由已知边定；但缺的那块和「只有一格宽的边」（1）拼，拼完多宽仍取决于缺的那块。
- **对应到技术上是**：逐维做一个 meet（取两者汇合结果）运算，mini 的约定是——`已知 d>1 vs 已知 e>1`：相等取 d、否则失配；`任意已知 vs 1`：取非 1 方；`None vs 已知 d>1`：取 d（运行期该维必须是 d 或 1，这个约束留给 Day 61 的符号推理）；`None vs 1`：**None**（结果维跟随未知方：未知若是 7，`1 vs 7` 的结果是 7）；`None vs None`：None。
- **最小例子**：`(None, 3)` 与 `(5, 3)` → `(5, 3)`；`(None,)` 与 `(3,)` → `(3,)`；`(None, 1)` 与 `(1,)` → `(None, 1)`。
- **常见误解**：把 `-1` 当未知维度。reshape 的 `-1` 是「帮我算」，广播的 `-1` 是字面上的负数维度——`np.broadcast_shapes((2,3), (-1,))` 实测报 `negative dimensions are not allowed`。mini 用 `None` 表未知，把两套约定彻底分开（验收测试 E3 专门钉住这一点）。另一头，「None = 任意取值」也不对——None 是**还没定**的维度，取值仍受 `d 或 1` 的约束，这正是明天要展开的「未知 vs 任意」。

## 4. 图解核心机制

推导算法、逐维三态与 stride-0 的物理真相，如图 2：

![核心机制：右对齐比较 → 三态判定 → stride-0 地址映射](images/02-mechanism.svg)

**图 2**：上半部分是推导算法的四步（bias 例子）；中间是逐维三态规则与 `(256,1)` 的翻车现场；下半部分是三种广播维的物理条带——行向量、列向量、标量在内存里的真实读法。

按图中编号逐步讲：

1. **右对齐是第一步，也是最多 bug 的源头**。`(256,)` 必须先补成 `(1, 1, 256)` 再比较——如果按左对齐拿 `256` 去对 `8`，一切全错。补出来的维不仅参与比较时当作 1，在地址上也记 stride 0（它根本不存在于这个操作数里）。
2. **三态判定只看「相等 / 一方为 1 / 都不是」**，没有「取最大值」这回事：`1 vs 0 → 0`、`3 vs 4 → error`、`1000 vs 256 → error`。有 1 也救不了别的维——`(3, 1)` 对 `(2, 3)`，第 1 维的 1 让位给 3，第 0 维 `3 vs 2` 照样失配（判定表 C13，MLIR 侧 `bad_broadcast.mlir` 房间 2 的 Verifier 报错同款）。
3. **「扩展」= stride 0 的地址映射**。图 2 下半部分三条物理条带：`b (3,)` 的 3 格被两行逻辑行反复读（行 +1 走 0 步）；`c (2,1)` 的两格各自横着读三遍（列 +1 走 0 步）；标量更极端，两个方向都走 0 步——所以 `()` 是万能形状。对照第 57 天的 `Σ idx×stride`：广播没引入新机制，只是往公式里塞了几个 0。
4. **边界**：numpy 对 `in == out == 1` 的维也记 stride 0（实测 `(1,1) → (1,3,1)` 给 `(0,0,0)`）——size-1 维下标恒为 0，`0 × 任何步长 = 0`，stride 取 0 与继承值等价（和第 59 天判定表 C8 的 size-1 维 stride 不唯一是同一件事）。0 尺寸维则按普通维参与三态：`(0,) vs (1,) → (0,)`。


## 5. 动手实践：完成一个最小可运行例子

### 5.1 准备文件

```text
tutorials/day-060/
├── README.md
├── images/                    # 4 张示意图（本文图 1–4）
└── code/
    ├── broadcast_lab.py       # 主实验：推导器 + 判定表 + stride-0 + 未知维度 + 随机对拍（9 项断言）
    ├── test_broadcast.py      # 独立验收测试（48 个测试点，含 400 组随机对拍）
    ├── broadcast_shapes.mlir  # shape dialect：编译期形状折叠 + 失配缺口
    ├── broadcast_add.mlir     # linalg 广播加法：行/列两种姿态 + cpu-runner 真实执行
    ├── bad_broadcast.mlir     # 错误博物馆：Verifier 应拒的两间房
    ├── make_images.py         # 生成 4 张 SVG 的脚本
    ├── run_all.sh             # 一键复跑全部实验并保存真实输出
    └── outputs/               # 已保存的真实输出
```

运行方式（在 `code/` 目录下）：

```bash
bash run_all.sh
```

`run_all.sh` 先打印环境（本机实测：Python 3.11.4、numpy 1.26.4、Ubuntu LLVM 18.1.8 的 `mlir-opt` 与 `mlir-cpu-runner`、Linux aarch64），再依次跑 Python 实验、验收测试、shape 折叠、循环展开、真实执行、错误注入。没有 `mlir-opt` 也能跑前两步（Python 侧自包含）。

### 5.2 编写代码

完整代码见 `code/broadcast_lab.py`（可直接运行）。今天是三个函数，各管一条规则：

```python
def broadcast_shapes(*shapes):
    """Broadcast 输出 Shape 推导（与 np.broadcast_shapes 同口径）。

    规则只有两条：
      1) 右对齐：短形状左侧补 1（缺的维度按 1 参与）；
      2) 逐维比较：相等 → 保留；其中一方为 1 → 取另一方；两者都不是 → 失配报错。
    """
    shapes = [_clean(s) for s in shapes]        # 维度必须是自然数（-1 在这里就死掉）
    if not shapes:
        return ()
    rank = max(len(s) for s in shapes)
    out = [1] * rank
    setter = [-1] * rank                 # 该维的「非 1 值」来自哪个操作数（报错要引用）
    for k in range(1, rank + 1):         # 从最右维往左逐维比较
        pos = rank - k
        for i, s in enumerate(shapes):
            d = s[-k] if k <= len(s) else 1          # 右对齐：缺的维度 = 1
            if d == 1:
                continue                             # 1 与任何维兼容，且不占坑
            if out[pos] == 1:
                out[pos], setter[pos] = d, i         # 第一个非 1 维定下结果
            elif d != out[pos]:
                j = setter[pos]
                raise BroadcastError(
                    "shape mismatch: objects cannot be broadcast to a single "
                    f"shape.  Mismatch is between arg {j} with shape "
                    f"{shapes[j]} and arg {i} with shape {shapes[i]}.")
    return tuple(out)


def broadcast_strides(shape, strides, out_shape):
    """把 shape/strides 的张量当作 out_shape 使用时的元素 strides。

    输入维为 1（含右对齐补出来的维）→ stride 0（与 np.broadcast_to 同口径：
    in==out==1 时 numpy 也记 0——size-1 维下标恒 0，stride 取 0 与继承值等价）；
    其余维度相同则继承源 stride。这是 np.broadcast_to 的 mini 版：
    广播不是拷贝数据，是「这一维走 0 步」的地址映射。
    不可广播返回 None。
    """
    r = len(out_shape)
    if len(shape) > r:
        return None
    pad = r - len(shape)
    padded_s = (1,) * pad + tuple(shape)        # 右对齐补 1（shape 侧）
    padded_t = (0,) * pad + tuple(strides)      # 补出来的维 stride 直接记 0
    out = []
    for d_out, d_in, t in zip(out_shape, padded_s, padded_t):
        if d_in == 1:
            out.append(0)                       # 输入维为 1：0 步长（numpy 同款）
        elif d_in == d_out:
            out.append(t)                       # 维度相同：继承源 stride
        else:
            return None                         # 失配：不可广播
    return tuple(out)


def _meet(d1, d2):
    """两个维度的广播结果；None 表示未知。失配抛 BroadcastError。"""
    if d1 is None and d2 is None:
        return None
    if d1 is None:
        d1, d2 = d2, d1                       # 交换后 d1 一定是已知
    if d2 is None:
        return None if d1 == 1 else d1        # None 对 1 → None；None 对 d>1 → d
    if d1 == 1:
        return d2
    if d2 == 1:
        return d1
    if d1 == d2:
        return d1
    raise BroadcastError(f"shape mismatch with unknown dims: {d1} vs {d2}")
```

三点设计意图：

- **报错口径与 numpy 逐字一致**：`broadcast_shapes` 的失配消息抄自 `np.broadcast_shapes` 的 `ValueError`（连双空格都一样），判定表的 4 组 error 用例对拍的就是这两边；拿报错信息就能和真实框架互相印证。注意 numpy 有两条口径——推导侧（`np.broadcast_shapes`）说 `shape mismatch: ... Mismatch is between arg 0 ...`，执行侧（`a + d`）说 `operands could not be broadcast together with shapes (2,3) (4,)`——同一场失配，两处各报各的。
- **`out[pos] == 1` 的双关是故意的**：值为 1 的维「不占坑」——第一个非 1 的维定下结果，后面的非 1 维必须与它相等。这天然处理了 0 尺寸维（`1 vs 0 → 0`，不是取 max），也让 `setter` 能找到失配的两个操作数供报错引用。
- **裁判独立**：`numpy_broadcast` 直接调 `np.broadcast_shapes`，与 mini 的推导**互不引用**——判定表和 300 组随机对拍因此有意义（`test_broadcast.py` 把它扩成 400 组）。

`_meet` 有个实现细节值得点破：`broadcast_shapes_unknown` 里「这一维还没见过操作数」的空位**不能**用 `None` 表示——`None` 已经被未知维度占了。第一版就拿这里翻过车：`(None, 1) + (1,)` 推成了 `(None, None)`（第 1 维的 `1` 被「空位 None」吞掉），加了独立的 `_UNSET` 哨兵才修对。**哨兵和语义值撞车**是写推导器时最常见的暗坑之一。

MLIR 侧（`code/broadcast_add.mlir`）用 linalg 表达同一场加法，广播全在 indexing map 里：

```mlir
// 行向量（bias 姿态）：b(3,) 的映射丢掉 d0 —— d0 走 0 步
linalg.generic {
  indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                   affine_map<(d0, d1) -> (d1)>,        // ← 广播在这
                   affine_map<(d0, d1) -> (d0, d1)>],
  iterator_types = ["parallel", "parallel"]}
  ins(%a, %b : memref<2x3xf32>, memref<3xf32>)
  outs(%o1 : memref<2x3xf32>) { ... }

// 列向量姿态：c(2,1) 的映射把 d1 钉死在 0
                   affine_map<(d0, d1) -> (d0, 0)>,     // ← 广播在这
```

`code/broadcast_shapes.mlir` 则是 shape dialect 的纯形状版：`shape.const_shape [2,3]` 与 `[3]` 做 `shape.broadcast`，`--canonicalize` 负责把结果折成常数。

### 5.3 运行与观察

以下均为**本机真实执行结果**（2026-11-12，Python 3.11.4 / numpy 1.26.4 / LLVM 18.1.8，输出已存 `code/outputs/`）。先看贯穿例子：

```text
=== 1. 贯穿例子：a(2,3) 遇上三种对手 ===
  a (2, 3)  b (3,)  c (2, 1)  d (4,)
  a + b → 形状 (2, 3)，值 =
  [[11. 22. 33.]
   [14. 25. 36.]]
  a + c → 形状 (2, 3)，值 =
  [[101. 102. 103.]
   [204. 205. 206.]]
  a + d → error：shape mismatch: objects cannot be broadcast to a single shape.  Mismatch is between arg 0 with shape (2, 3) and arg 1 with shape (4,).

  numpy 的实测报错（逐字）：
    ValueError('operands could not be broadcast together with shapes (2,3) (4,) ')

  stride-0 证据（b 被当作 (2,3) 用，一行数据两行用，不搬家）：
    b 的 strides = (8,) bytes，广播视图的 strides = (0, 8) bytes（元素单位 (0, 1)）
    shares_memory = True，两行的第 2 列都是 30.0 / 30.0（同一格读两遍）
```

再看判定表（今日产出之一，16/16 对拍一致，完整表见 `code/outputs/broadcast_lab.txt`）：

```text
=== 2. 判定表：mini.broadcast 预测 vs numpy 实测 ===
  用例                输入                            mini            numpy           对拍
  C1  同形相加          (2, 3) + (2, 3)               (2, 3)          (2, 3)          ok
  C3  行向量（贯穿例子） (2, 3) + (3,)                 (2, 3)          (2, 3)          ok
  C5  bias 相加       (8, 1000, 256) + (256,)       (8, 1000, 256)  (8, 1000, 256)  ok
  C6  经典翻车 (256,1)  (8, 1000, 256) + (256, 1)     error           error           ok
  C9  0 尺寸维         (0,) + (1,)                   (0,)            (0,)            ok
  C12 -1 不是未知维度    (2, 3) + (-1,)                error           error           ok
  C13 维度 1 不豁免他维  (3, 1) + (2, 3)               error           error           ok
  C16 1×n 对 n×1     (1, 3) + (3, 1)               (3, 3)          (3, 3)          ok
  [PASS] 判定表 16 组全部一致（含 4 组错误消息逐字相同）
```

stride-0 视图与未知维度两段（真实输出节选）：

```text
=== 3. stride-0 视图：broadcast_strides vs np.broadcast_to 实测 ===
  S1  (3,)      (2, 3)          (0, 1)        (0, 1)        ok
  S3  (2, 1)    (2, 3)          (1, 0)        (1, 0)        ok
  S9  (256,)    (8, 1000, 256)  (0, 0, 1)     (0, 0, 1)     ok
  S10 (2, 3)    (4, 1, 2, 3)    (0, 0, 3, 1)  (0, 0, 3, 1)  ok
  [PASS] stride-0 视图 10 组逐位一致
  [PASS] 大输出不搬数据：100000x3 广播视图与 3 元素源共享存储

=== 4. 未知维度：None 的 meet 规则（numpy 没有对应物，期望手算）===
  U1  (None, 3) + (3,)            (None, 3)     最右维 3==3；None 对补 1 → 未知
  U2  (None, 3) + (5, 3)          (5, 3)        None 对已知 5 → 5（运行期须为 5 或 1）
  U6  (None, 1) + (1,)            (None, 1)     第 0 维 None 对补 1 → 未知；第 1 维 1==1
  U8  (None, 4) + (3,)            error         最右维 4 vs 3，都不是 1 → 失配
  [PASS] 未知维度 10 组与手算期望一致
```

判定表浓缩版、真实数值与对拍统计，如图 3：

![实例对照：判定表 16/16 全对拍，数值、strides 与错误消息逐字一致](images/03-example.svg)

**图 3**：上半部分是判定表浓缩版；中间把 `a + b` 的值、cpu-runner 真实执行的 4 个数、stride-0 视图对拍摆在一起；下半部分是四项对拍统计。

对着图读三个结论：

1. **mini 与 numpy 的判定完全等价**：16 组判定表 + 300 组随机对拍（ok=178、error=122）零失配，连 4 组错误消息都逐字相同——右对齐补 1 后逐维三态，就是对 `np.broadcast_shapes` 的复刻。
2. **「扩展」的账单是零**：`np.broadcast_to` 的 strides 实测 `(0,8)` bytes、共享存储、`100000x3` 只住 3 个元素的家——广播维 stride 0，读一万遍也不搬一次家。
3. **数值层面对得上**：`a+b` 的 `[[11,22,33],[14,25,36]]` 与 5.4 节 MLIR `cpu-runner` 打出的 33、25 逐位一致——Python 侧和 MLIR 侧跑的是同一场广播。

### 5.4 修改一个参数再观察：MLIR 四连与 Verifier 现场

现在做今天的对照实验：同一批形状，换四种方式「运行」，看编译器对广播的全部待遇（真实输出，已存 `code/outputs/`）：

```text
== 4. broadcast_shapes.mlir --canonicalize：兼容形状折成常数，失配原样留 ==
  func.func @bc_row()   → return shape.const_shape [2, 3]          // (2,3)+(3,) 折叠
  func.func @bc_bias()  → return shape.const_shape [8, 1000, 256]   // bias 例折叠
  func.func @bc_conflict() → 原样保留 shape.broadcast（exit=0，不报错）  // 缺口

== 5. broadcast_add.mlir --convert-linalg-to-loops：广播降成「少一个下标」==
  scf.for %arg0 = %c0 to %c2 step %c1 {
    scf.for %arg1 = %c0 to %c3 step %c1 {
      %7 = memref.load %0[%arg0, %arg1] : memref<2x3xf32>      // a：两个下标
      %8 = memref.load %1[%arg1] : memref<3xf32>               // b：一个下标！
      %9 = arith.addf %7, %8 : f32
      ...
      %8 = memref.load %2[%arg0, %c0] : memref<2x1xf32>        // c：d1 钉死 0

== 6. mlir-cpu-runner 真实执行 ==
  33     // o1[0,2] = 3 + 30   （b 沿行广播）
  25     // o1[1,1] = 5 + 20
  101    // o2[0,0] = 1 + 100  （c 沿列广播）
  206    // o2[1,2] = 6 + 200

== 7. bad_broadcast.mlir：Verifier 应拒绝（退出码 1）==
  bad_broadcast.mlir:32:5: error: 'linalg.generic' op inferred input/output
    operand #1 has shape's dimension #0 to be 3, but found 4
  房间 2 单独验证：(3,1)+(2,3) → error: ... dimension #0 to be 2, but found 3
```

未知维度规则与 MLIR 四项证据，如图 4：

![未知维度与 MLIR 对照：None 的 meet 规则；shape 折叠、linalg 映射与 Verifier 现场](images/04-unknown-and-mlir.svg)

**图 4**：左上是 meet 真值表（两条标红的 `None` 最容易看反）；右上是未知维度用例与 `-1` 的边界；下半部分是 MLIR 四项实测证据。

四个层次的结论：

1. **形状推导在编译期一次做完**。`shape.broadcast` 吃到两个 `const_shape`，`--canonicalize` 直接折成结果常数 `[2, 3]`、`[8, 1000, 256]`——与 mini 手推逐位一致。这就是 Shape 推导 Pass 的样子：纯元数据运算，不碰数据。
2. **失配的形状却静态不报错（缺口）**。`(2,3)` 与 `(4,)` 的 `shape.broadcast` 在 canonicalize 后**原样保留**、exit=0——错误要等运行期才暴露。numpy 和 mini.broadcast 都是静态拦的（`ValueError` / `BroadcastError`），这个缺口和昨天 `memref.reshape` 放行元素数违规是同一类问题：**静态可见的失配，就该在 Verifier 静态拦住**。
3. **广播在后端就是「少一个下标」**。`--convert-linalg-to-loops` 降出的循环里，`a` 用 `[%arg0, %arg1]` 寻址，`b` 只用 `[%arg1]`，`c` 用 `[%arg0, %c0]`——indexing map 丢掉/钉死的下标，就是 mini 说的 stride 0。**两套说法，一个事实**。`cpu-runner` 打出的 33/25/101/206 与 5.3 节 Python 侧数值逐位对上。
4. **Verifier 拦对了什么**。`bad_broadcast.mlir` 两间房都被静态拒绝：`(2,3)+(4,)` 报 `inferred ... dimension #0 to be 3, but found 4`；`(3,1)+(2,3)` 报 `inferred ... to be 2, but found 3`——报错文本说的正是三态判定的第三态，和 mini 的 `BroadcastError` 同口径。

## 6. 常见错误与排查

**错误 1：bias 写成 `(256, 1)`——「明明有 256 却报错」**

- **现象**：`logits (8,1000,256) + bias (256,1)` 训练脚本一跑就炸（真实报错）：`ValueError: operands could not be broadcast together with shapes (8,1000,256) (256,1)`；写成 `(256,)` 或 `(1,256)` 就好。
- **原因**：比较是**右对齐**的：`(256,1)` 补齐后是 `(1,256,1)`，第 1 维 `256 vs 1000` 既不相等也没有 1；`(256,)` 补齐后是 `(1,1,256)`，三个位置全部相容。脑子里按「左对齐」或「有公共数字就能配」直觉建模，就会写出这种形状。
- **定位**：报错文本里 shapes 的顺序就是操作数顺序；不确定时先用 `np.broadcast_shapes(a.shape, b.shape)` 预检（只推导不执行）。
- **修复**：bias 用 `(256,)` 或 `(1, 256)`；已有 `(256,1)` 想换位用 `bias.T`（得 `(1,256)`）或 `bias[:, 0]`（得 `(256,)`）——注意 `bias[None, :]` 得到的是 `(1,256,1)`，右对齐后第 1 维 `256 vs 1000` 照样失配，别顺手多套一层。

**错误 2：把广播当复制——往广播视图里写数据**

- **现象**：想就地更新 `v = np.broadcast_to(b, (100000, 3))`，报 `ValueError: assignment destination is read-only`；改用增强赋值 `x = np.zeros(3); x += np.ones((4, 1))`，又报 `ValueError: non-broadcastable output operand with shape (3,) doesn't match the broadcast shape (4,3)`（均为本机实测原文）。
- **原因**：广播维 stride 0——10 万个逻辑行指着同一排 3 个格子，写哪个都说不清，所以 numpy 把广播视图设成只读；增强赋值要求输出形状**不小于**广播形状，`(3,)` 装不下 `(4,3)`。
- **定位**：`v.flags.writeable` 一眼看出只读；增强赋值的报错会直接给出「广播形状 (4,3)」——那就是结果本该有的形状。
- **修复**：要真的落盘就显式物化 `np.broadcast_to(...).copy()`（此时才付出内存），或用 `np.add(a, b, out=形状匹配的缓冲)`；写编译器时把「广播视图只读」「输出形状 = 广播形状」当成 mini.broadcast Verifier 的两条硬规则。

**错误 3：拿 `-1` 当广播的未知维度**

- **现象**：给推导器传 `(2, 3)` 和 `(-1,)`，期望它像 reshape 一样「帮我算」，结果 `np.broadcast_shapes` 报 `ValueError: negative dimensions are not allowed`（本机实测）。
- **原因**：`-1` 是 reshape 语义里的「这一维自己算」（Day 59 的 `infer_shape`），广播语义里它就是字面上的负数维度——两套约定同名不同义。
- **定位**：想清楚你要的是「推导时缺一维」（reshape 的 `-1`）还是「编译期不知道这一维」（动态 Shape 的未知维度）。
- **修复**：未知维度用独立表示——本文 Python 侧用 `None`，MLIR 侧用 `?`（`tensor<?x3xf32>`）；Day 61 会把它们升级成符号维度。

**错误 4：以为「有 1 就万能」——`(3,1)` 配 `(2,3)` 照样翻车**

- **现象**：手写 linalg 时给 `(3,1)` 的操作数配了 `affine_map<(d0, d1) -> (d0, d1)>`（想当然「1 能扩展」），`mlir-opt` 直接拒绝（真实报错）：`error: 'linalg.generic' op inferred input/output operand #1 has shape's dimension #0 to be 2, but found 3`；Python 侧同样：`np.broadcast_shapes((3,1),(2,3))` 失配。
- **原因**：右对齐后 `(3,1)` 对 `(2,3)`：第 1 维 `1 vs 3` 没问题（1 让位），但第 0 维 `3 vs 2` 既不相等也没有 1——**1 只能救自己所在的维**。
- **定位**：报错里的 `inferred ... to be 2, but found 3` 说的是同一个维：indexing map 从迭代空间推断出该维应为 2，操作数实际是 3。
- **修复**：写 IR 前先在纸上（或用 `np.broadcast_shapes`）逐维过一遍三态判定；`(3,1)` 想配 `(2,3)` 要么改数据为 `(2,1)`/`(1,3)`，要么让 map 显式丢维 `(d0, d1) -> (d0)` 配 `(2,)`。

## 7. 今日练习

### 必做练习

拿 bias 例子练手算，**先笔算再跑**：

1. 手算三组：`(8,1000,256)` 分别与 `(256,)`、`(256,1)`、`(8,1,1)` 广播，写出右对齐补 1 后的逐维比较和输出形状（预期：`(8,1000,256)` / error / `(8,1000,256)`）；
2. 用一行命令验证第一组：`python3 -c "from broadcast_lab import broadcast_shapes; print(broadcast_shapes((8,1000,256),(8,1,1)))"`（在 `code/` 目录下，预期输出 `(8, 1000, 256)`）；
3. 把这三组写成新断言加进 `test_broadcast.py` 的 A 段（照抄现有用例的写法），跑 `python3 test_broadcast.py`，看总数从 48/48 涨上去；
4. 手算 `(5,1)` 与 `(1,4)` 的输出形状（预期 `(5,4)`，判定表 C7），再手算 `broadcast_strides((5,1), (1,1), (5,4))` 的返回值（预期 `(1,0)`：第 0 维 `5==5` 继承源 stride 1，第 1 维输入为 1 记 0），想清楚每一维为什么，再用 `python3 -c` 验证。

### 选做挑战

给 `broadcast_add.mlir` 做一次「改 map」手术：

1. 把 `@main` 里第一个 linalg.generic 的 `b` 映射从 `(d0, d1) -> (d1)` 改成 `(d0, d1) -> (d0)`，其余不动（`b` 仍是 `memref<3xf32>`）；
2. 先预测：`mlir-opt` 会报什么？报错里 `inferred` 的数字应该是多少（提示：`d0` 的迭代范围是 2，所以会看到 `inferred ... to be 2, but found 3`）；
3. 跑 `mlir-opt broadcast_add.mlir` 验证预测；然后修好它——把 `@gb` 的全局常量改成 `dense<[10.0, 20.0]>`，**两处**类型（`memref.global` 和 `memref.get_global`）都改成 `memref<2xf32>`，`ins` 里的类型同步改；此时 `b` 沿**列**广播（只按行号取数），预测四个打印值（提示：`o1[0,2] = 3 + b[0] = 3 + 10`），最后用 5.4 节的 cpu-runner 命令真实执行核对（实测输出 13 / 25 / 101 / 206，后两个是没动过的列向量那组）。

## 8. 今日验收

- [ ] 我能用自己的话说清 Broadcast 的两条规则——右对齐（缺的维按 1）与逐维三态（相等保留 / 一方为 1 取另一方 / 都不是报错），并解释 `(256,)` 能配 `(8,1000,256)` 而 `(256,1)` 不能；
- [ ] 我能说清「扩展」的物理含义是 stride 0 的地址映射不是数据复制，并给出证据：`np.broadcast_to` 的 strides `(0,8)`、共享存储、广播视图只读；
- [ ] 我能说清 `-1` 与 `None` 的区别（reshape 的帮我算 vs 广播的未知维度），以及 `None vs 1 → None`、`None vs d>1 → d` 这两条容易看反的 meet 规则；
- [ ] 我能独立运行 `bash code/run_all.sh`，复现 broadcast_lab 9/9、test_broadcast 48/48（含 400 组随机对拍）、canonicalize 折出 `[2,3]` 与 `[8,1000,256]`、cpu-runner 输出 33/25/101/206；
- [ ] 我能定位三类错误：`(256,1)` 型右对齐失配（错误 1）、往广播视图写数据（错误 2）、linalg map 与形状不一致被 Verifier 拒（错误 4 的 `inferred ... but found ...`）；
- [ ] 我保存了 Broadcast 推导器、验收测试、三个 MLIR 示例、错误现场和 4 张示意图（`tutorials/day-060/`）。

## 9. 一句话总结与明天预告

今天的问题始于「`(8,1000,256)` 加 `(256,)` 白拿白用，加 `(256,1)` 当场爆炸」。机制上，Broadcast 是一套纯静态的三步推导——右对齐补 1、逐维三态判定、输出形状取「第一个非 1 维」，而它的物理真相是 stride 0 的地址映射：广播维走 0 步、数据一格不搬、视图只读，MLIR 里同一个事实写作 indexing map 丢下标，降成循环就是 `memref.load %b[%arg1]` 那个「少一个下标」。实践中，我们给 mini.broadcast 写出了完整推导器，16 组判定表加 300 组随机对拍与 numpy 零失配（连错误消息都逐字相同），未知维度用 `None` 的 meet 规则补齐，`-1` 的越界用法被实测钉死；MLIR 侧四连验证了 `shape.broadcast` 编译期折叠、linalg 广播降级、cpu-runner 真实执行 33/25/101/206，也亲眼看到 `shape.broadcast` 对静态失配不报错的缺口——静态可见的失配，就该在 Verifier 静态拦住。

明天（Day 61）把今天的 `None` 正规化：动态 Shape 表示——动态维度、符号维度和运行期 Shape 参数，重点区分「未知」（编译期还不知道，但取值受约束）与「任意」（任何取值都合法）。今天 meet 规则里那句「运行期必须是 d 或 1」的口头约束，明天会变成 IR 里可检查的类型。
