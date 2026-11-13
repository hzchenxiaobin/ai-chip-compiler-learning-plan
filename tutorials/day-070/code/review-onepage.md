# 第 10 周一页复盘（Day 64–70：Layout 与冗余算子消除）

## 一句话命题

**图结构相同不代表内存语义相同**——结构账本（`state_hash`：算子 +
连接 + 属性）只回答「值怎么算」；内存账本（buffer / strides / offset /
traffic / 写集合 / 副作用）回答「字节怎么搬、谁观察到了什么」。

## 六天速查表

| 天 | 主题 | 一句话带走 | 关键守卫 |
| --- | --- | --- | --- |
| 64 | Transpose 语义 | 维度排列 / 视图 / 物理移动是三件事 | Verifier: perm 合法性 |
| 65 | 转置消除 | `r[i]=p1[p2[i]]`，恒等才透传 | 组合律数学恒等 |
| 66 | Reshape 合并 | `Reshape(Reshape(x,t),t)=Reshape(x,t)≠x` | numel 守恒 + 只并一层 |
| 67 | Cast 消除 | 只有 src==dst 是无操作 | 精度语义边界 |
| 68 | Layout 传播 | T(E(x))→E(T(x)) 只对逐元素成立 | C1 白名单 + C2 唯一使用者 |
| 69 | 组合测试 | 不动点 / 振荡 / 顺序；守卫是语义边界 | 规范化哈希 + 单调配度 |
| 70 | 复盘 | 7 条「看似能消除但不能消除」反例 | 见反例集 |

## 两本账本的机器可检形式（今天的核心实验）

同一条 4-op 链 `arg→transpose→relu→reshape`（state_hash 相同）：

| 世界 | traffic | 中间分配 | 输出值 |
| --- | --- | --- | --- |
| 视图（框架前端） | 48B | 1 | 逐位相等 |
| 物理（降级后端） | 144B | 3 | 逐位相等 |

三明治 `T(relu(T(x)))→relu(x)`（值等价改写）在两个世界的账单：
物理世界省 96B（两个转置 × 48B）；视图世界省 0B，但输出布局从
`(1,2)` 变 `(3,1)`（连续化）——下游零拷贝权利改变。

## 反例集速查（详见 counterexamples.md，7 条 ≥ 计划要求 5 条）

| # | 反例 | 拒绝理由（语义维度） | 实测证据 |
| --- | --- | --- | --- |
| R1 | Cast f32→f16→f32 | 精度 | 6/6 元素变值；MLIR 不折叠 |
| R2 | 双层同目标 Reshape | 形状 | V1 拦截；shape (2,3)→(6,) |
| R3 | copy(x) 消除 | 别名 | 写集合 buf1→buf0；输入被污染 |
| R4 | 无使用者的 store | 副作用 | naive DCE 删掉后 G 变空 |
| R5 | 恒等排列物理转置 | 布局 | 双消费者消除 traffic 48→96B |
| R6 | 多使用者传播 | 复制 | op 2→3；元素计算 6→12 |
| R7 | reduce 传播 | 轴语义 | shape (3,1)→(1,2)；axis=inv_perm[旧] |

MLIR stock 管道对五个案子的裁决（全部实测）：
truncf/extf 不折叠、reshape 链不合并、memref.copy 不删、
死 addf 删 / store 留、恒等排列 linalg.transpose 不删。

## 测试汇总（全部真实复跑，2026-11-12）

| 套件 | 测试点 |
| --- | --- |
| Day 64 test_transpose.py | 63 PASS |
| Day 65 test_transpose_elim.py | 33 PASS |
| Day 66 test_reshape_merge.py | 30 PASS |
| Day 67 test_cast_elim.py | 39 PASS |
| Day 68 test_layout_prop.py | 37 PASS |
| Day 69 test_combo_lab.py | 51 PASS |
| Day 70 test_counterexamples.py | 33 PASS |
| **合计** | **286 PASS / 0 FAIL / 0 SKIP** |

主实验 counterexample_lab.py：39/39（两本账本 + 7 反例 + 5 探针）。

## 带走的三句话

1. 判断一次改写「动没动存储」，依据是第 9 周的偏移公式和本周的内存账本，
   不是图长相。
2. 每条守卫都是一个反例的墓碑：守卫不是官僚作风，是语义边界。
3. 值等价是改写的必要条件，不是充分条件——别名、布局、副作用、精度、
   轴语义都住在值世界看不见的地方。
