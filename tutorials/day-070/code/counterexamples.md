# 反例集：看似能消除但实际不能消除（第 70 天产出）

> 命题：**图结构相同不代表内存语义相同**。结构账本（算子 + 连接 + 属性，
> `state_hash`）只回答「值怎么算」；内存账本（buffer / strides / offset /
> traffic / 写集合 / 副作用）回答「字节怎么搬、谁观察到了什么」。
> 下面 7 条反例，每条都是一次「结构账本说可以删、内存账本说不许动」的
> 现场实录。全部证据来自 2026-11-12 本机真实运行
> （Python 3.11.4 / numpy 1.26.4 / Ubuntu LLVM 18.1.8，
> 完整输出见 `outputs/counterexample_lab.txt`）。

---

## R1 精度语义：Cast f32→f16→f32 往返

- **图结构视角（诱人处）**：类型一进一出「对消」，输入输出 shape 相同，
  `f32→f16→f32` 看起来像恒等。
- **内存/数值语义（拒绝理由）**：f16 只有 10 位尾数（f32 有 23 位），
  往返必然丢位；单层 `f32→f16` 也不是改名——它把后续 buffer 从 24B
  缩到 12B，是「变窄」的物化点。
- **实测证据**：`(2,3)` 随机输入，roundtrip 后 **6/6 元素变值**
  （`x[0,0]=6.1210938` → `6.1211` 一类）；诱人改写（类型对消透传）后
  输出与原值 `array_equal` 为 False。
- **守卫**：Cast 只在 `src == dst` 时透传（Day 67）。对照实验：同 dtype
  Cast 消除后物理世界真省 48B。
- **MLIR 探针**：`arith.truncf` + `arith.extf` 在 `--canonicalize` 下
  **原样保留**（2 个 cast），stock 管道不折叠。

## R2 形状语义：Reshape(Reshape(x,t),t)

- **图结构视角**：外层目标 == 当前 shape，「看似透明」，整链像能透传成 x。
- **内存/数值语义**：代数事实 `Reshape(Reshape(x,t),t) = Reshape(x,t) ≠ x`
  （除非 t 恰好等于 `shape(x)`）。
- **实测证据**：`x:(6,)`、`t=(2,3)`，透传错版把 return 的 shape 从 `(2,3)`
  变成 `(6,)`；下游接一个 rank-1 转置时被 Verifier 拦截：
  **`[V1] %4 perm (0,) 对 rank 2 不合法`**（Day 69 压力对拍真实踩坑，
  今天复现）。
- **守卫**：合并永远替换为 `Reshape(x, 外层目标)`；「同 shape 才透传」
  交给 transparent 判据单独把关（Day 66）。
- **MLIR 探针**：`tensor.reshape` 链在 `--canonicalize` 下不合并
  （剩 2 个）——stock 不做不等于不能做，但做必须带守卫。

## R3 别名语义：copy(x) 消除

- **图结构视角**：copy 是值上的恒等映射，「看似冗余」。
- **内存/数值语义**：copy 划定了缓冲边界。消除后，把逐元素算子编成
  原地 kernel 的后端会直接写进源缓冲——**写集合从 buf1 漂移到 buf0**。
- **实测证据**：`return x, relu(copy(x))`，in-place 后端下：
  保留 copy：`输入被写 = 无`；消除 copy：`输入被写 = [-1]`，
  且 return 的 x 变成了 `relu(x)`（第一个输出被污染）。
  **纯函数 eval 完全看不见这个差别**（R3a：逐位相等）。
- **守卫**：copy 消除需要别名分析——「源缓冲此后只读」或
  「所有消费者都不原地写」才允许删（MLIR bufferization 的
  `bufferizesToMemoryWrite` 分析做的就是这件事）。
- **MLIR 探针**：`alloc + memref.copy + return` 在 `--canonicalize`
  和 `--cse` 下 **copy 都保留**——返回自己的 alloc 还是返回入参，
  对调用方是两种别名契约。

## R4 副作用语义：无使用者的 store

- **图结构视角**：store 没有任何使用者——DCE 的标准猎物。
- **内存/数值语义**：副作用对外部世界可观察（外部全局 G 的内容）。
- **实测证据**：完整执行 `G = [x 的 6 个值]`；naive DCE（Day 69 原样，
  只看 return 可达性）把 store 删掉后 `G = None`；带副作用模型的
  guarded DCE 保留 store。
- **守卫**：DCE 的活跃集 = return 可达 **∪ 副作用 op 集合**（今天补的）。
- **MLIR 探针**：同一函数里 `memref.store`（留）与无使用者的
  `arith.addf`（删）在 `--cse` / `--canonicalize 下都是**一删一留**——
  stock 编译器的副作用模型给出的正是这个答案。

## R5 布局语义：恒等排列的物理转置

- **图结构视角**：`perm=(0,1)` 值上什么都不做，「看似可消除」。
- **内存/数值语义**：在物理世界（Day 68 的 linalg 世界）它是
  **strided→连续 的物化点**，把布局转换摊销到所有消费者。
- **实测证据**（2×2 实验，双 reshape 消费者）：
  - 视图世界：保留 96B / 消除 96B → 消除免费（它本来就是 0 字节视图）；
  - 物化世界：保留 48B / 消除 **96B** → **traffic 翻倍**——拷贝没有
    消失，只是搬进每个消费者的实现里。
  - 四种执行的输出值全部逐位相等。
- **守卫**：看消费者数量与布局契约：单消费者时消除是 traffic 中性的
  （拷贝挪个地方）；多消费者时物化点摊销布局转换，删了翻倍
  （今天补的）。
- **MLIR 探针**：`linalg.transpose permutation=[0,1]`（strided 输入 →
  连续输出）在 `--canonicalize` / `--cse` 下都保留。

## R6 复制语义：多使用者传播

- **图结构视角**：`T(relu(x))`，和 Day 68 的传播模式同构。
- **内存/数值语义**：relu 的结果同时被 return 使用时，传播会把 relu
  复制一份——转置一个没少，逐元素计算翻倍。
- **实测证据**：`return relu(x), T(relu(x))`，强行传播（无视 C2）：
  op 2→3、元素计算 6→12、转置数 1→1；值仍然等价（错误不在正确性，
  在收益）；C2 守卫版拒绝触发。
- **守卫**：C2 唯一使用者门（Day 68）——不是官僚作风，是收益边界。

## R7 算子语义：T(reduce_sum(x)) 推不过去

- **图结构视角**：还是「transpose 挂在算子上面」，和 `T(relu(x))` 同构。
- **内存/数值语义**：reduce 带轴语义，转置置换了维度，axis 必须跟着换：
  **新 axis = inv_perm[旧 axis]**（旧轴被 perm 挪到了哪一位；
  一般 perm 下不等于 perm[旧 axis]）。
- **实测证据**：`T(reduce_sum(x, axis=0))` 是 `(3,1)`；照抄传播得
  `reduce_sum(T(x), axis=0)` 是 `(1,2)`——shape 都不对；axis 换成 1
  之后才逐位相等。
- **守卫**：C1 白名单只放「逐位置不变」的算子（Day 68）；带轴语义的
  算子要传播，必须连带改写 axis——那是另一条 Pattern，不是免费 lunch。

---

## 守卫清单（每条 Pattern 的语义门 = 反例集的镜像）

| Pattern | 出处 | 语义门 |
| --- | --- | --- |
| merge_adjacent_transposes | D65 | 组合律 `r[i]=p1[p2[i]]` 数学恒等；恒等才透传 |
| merge_adjacent_reshapes | D66 | numel 守恒；只能并成 `Reshape(x, 外层目标)` |
| eliminate_transparent_reshape | D66 | 目标 shape == 输入 shape 才透传 |
| eliminate_noop_cast | D67 | src dtype == dst dtype |
| push_transpose C1 | D68 | 白名单：只放逐位置不变的算子 |
| push_transpose C2 | D68 | T 是 E 结果的唯一使用者 |
| fuse_add_relu | D51/54 | add 的结果只有这一个 relu 在用 |
| DCE（D70 补） | D70 | 活跃集 = return 可达 ∪ 副作用 op |
| copy 消除（D70 补） | D70 | 别名分析：源缓冲此后无人原地写 / 只读 |
| 恒等转置消除（D70 补） | D70 | 看消费者数量与布局契约（物化点摊销布局转换） |

## 带走的三句话

1. 结构账本只回答「值怎么算」，内存账本回答「字节怎么搬」——
   同一张图在视图世界和物理世界是两种程序（48B vs 144B）。
2. 每条消除/传播规则的守卫，都是某个反例的墓碑——守卫不是官僚作风，
   是语义边界。
3. 值等价是改写的必要条件，不是充分条件：别名、布局、副作用、精度、
   轴语义都住在值世界看不见的地方。
