# mini.matmul → 循环表示：Lowering 设计文档（Day 85）

> 环境：Linux aarch64, Python 3.11.4, numpy 1.26.4；随机种子 85。本脚本是 MLIR DialectConversion 的角色仿真，
> 不依赖 MLIR，也不伪造 MLIR 的行为。

## 1. 目标与输入

- **源图（S0）**：`func @main(%x: tensor<4x6xf32>, %w: tensor<6x3xf32>) -> tensor<4x3xf32>`，
  体内一个 `mini.matmul`——第三阶段图优化器交付的"干净图"（形状沿用 Day 83 终图的 GEMM）。
- **目标（S4）**：只含 `scf` / `memref` / `arith` 的循环表示，`mini` 方言整体消失。

## 2. 路线（S0 → S4）

| 阶段 | 做什么 | 谁负责 | 产出状态 |
|---|---|---|---|
| S0 原图 | — | — | tensor 世界，`mini.matmul` 声明式描述"做什么" |
| S1 签名降级 | 函数入参 tensor→memref | TypeConverter（convertType） | 入参已是 memref，体内还没动 |
| S2 核心改写 | `mini.matmul` → alloc+三重循环+load/store | ConversionPattern（matchAndRewrite 读源写目标） | 体内只剩目标 op |
| S3 边界缝合 | return 需要的 tensor 用 to_tensor 物化 | TypeConverter（物化钩子） | 中途的"半 tensor 半 memref"被缝上 |
| S4 合法性验收 | 终图 ∩ 非法集 = ∅ | ConversionTarget + 驱动器 | 降级完成（或 full 模式整体失败） |

## 3. 三张任务清单

### 3.1 类型任务（TypeConverter）

| 值 | 源类型 | 目标类型 | strides | 大小 | 来源 |
|---|---|---|---|---|---|
| %x | tensor<4x6xf32> | memref<4x6xf32, strided<[6, 1]>> | [6, 1] | 96 B | 签名降级 |
| %w | tensor<6x3xf32> | memref<6x3xf32, strided<[3, 1]>> | [3, 1] | 72 B | 签名降级 |
| %c | tensor<4x3xf32> | memref<4x3xf32, strided<[3, 1]>> | [3, 1] | 48 B | Pattern 内 alloc |

### 3.2 索引任务（地址与边界）

| 访问 | 多下标 | 线性地址公式 | 循环边界 | 边界来源 |
|---|---|---|---|---|
| A[i,k] | (i,k) | 6·i + 1·k | i ∈ [0,4) | A.shape[0] |
| B[k,j] | (k,j) | 3·k + 1·j | j ∈ [0,3) | B.shape[1] |
| C[i,j] | (i,j) | 3·i + 1·j | k ∈ [0,6) | A.shape[1]==B.shape[0]（内维契约，Day 12/83 闸0 已验） |

### 3.3 输出初始化任务（alloc 不清零！）

| 方案 | 做法 | 额外访存流量 | 位等价 |
|---|---|---|---|
| A：fill + 读改写 | `memref.fill(%c, 0.0)`，k 循环外先 load C[i,j] | +2×M×N×4 = 96 B | ✓（TP3 实测） |
| B：iter_args（**选定**） | `%acc` 从常量 0.0 起步，C 每元素只写一次 | +0 B | ✓（TP3/TP6 实测） |
| 什么都不做 | 读改写从垃圾值起步 | — | ✗ 未定义行为（探针 P2 实测翻车） |

## 4. 角色职责（源 op 与目标 op）

| 角色 | 一句话职责 | 今天仿真里的对应 |
|---|---|---|
| ConversionTarget | 定义"什么算降级完成"（合法性清单） | `TARGET_LEGAL` 集合 |
| TypeConverter | 类型降级 + 中途缝合（物化钩子） | §3.1 类型表 + to_tensor/to_memref |
| ConversionPattern | 读源 op 语义，写等价目标 op 序列 | `PATTERNS["mini.matmul"]` |
| 驱动器 | 反复改写直到没有非法 op，或整体失败 | `apply_conversion(full/partial)` |

- **源 op（`mini.matmul`）的职责**：提供完整语义——操作数类型/shape、内维契约、结果类型，
  Pattern 靠这些决定怎么翻；转换完成后被替换、擦除，不再出现。
- **目标 op（`scf.for`/`memref.*`）的职责**：①在 ConversionTarget 里合法；
  ②类型经过 TypeConverter 认可；③组合起来与源 op 数值等价（交给测试计划验收）。

## 5. 合法性规则

- 合法（终图允许）：arith.addf, arith.constant, arith.mulf, bufferization.to_memref, bufferization.to_tensor, func.func, func.return, memref.alloc, memref.fill, memref.load, memref.store, scf.for, scf.yield
- 非法（必须消失）：mini.add, mini.conv, mini.matmul, mini.relu, mini.reshape, mini.transpose（整个 mini 方言标非法）
- 驱动器两种模式：`full` = 只要剩一个非法 op 就整体失败（applyFullConversion）；
  `partial` = 允许残留给后续 Pass（applyPartialConversion）。

## 6. 边界与失败模式

1. **物化钩子**：签名/外部契约还是 tensor 时，return 处用 `bufferization.to_tensor`
   把 memref 缝回 tensor（源物化）；反向是 `to_memref`（目标物化）。不设钩子 →
   "半 tensor 半 memref"的中途状态类型断裂（TP5）。
2. **无 Pattern 的非法 op**：`mini.conv` 目前没有规则——full 模式整体失败并指名 op；
   partial 模式显式残留（TP4）。**这是设计决定，不是 bug**。
3. **静态 shape 前提**：循环边界全部编译期已知。若 shape 动态，常量边界换成
   `memref.dim`——今天不处理，留给动态 shape 专题。

## 7. 测试计划

| 检查 | 问题 | 方法 | 通过标准 |
|---|---|---|---|
| TP1 | 类型表完整、strides 正确？ | 表 vs 行主序计算值 | 全部一致 |
| TP2 | 索引公式算的地址对吗？ | 抽样 (i,j,k) vs `np.ravel_multi_index` | 全部相等 |
| TP3 | 输出初值显式且正确？ | 三种策略执行 vs 同序参考 | 位等价 + 策略显式 |
| TP4 | 转换收敛且失败模式正确？ | op 级仿真（主图 + conv 变体 × 两种模式） | 无残留非法 / 按预期失败 |
| TP5 | 边界缝合有钩子？ | to_tensor 插入 vs 无钩子诊断 | 有钩子合法、无钩子可诊断 |
| TP6 | 执行结果等价？ | 解释执行循环 IR vs 同序 fp32 参考 | 逐位相等 |

## 8. 执行结果（真实运行）

| 检查 | 结果 |
|---|---|
| TP1 类型完整性 | 通过 |
| TP2 索引探针 | 通过 |
| TP3 输出初始化 | 通过 |
| TP4 合法性收敛 | 通过 |
| TP5 边界缝合 | 通过 |
| TP6 执行等价 | 通过 |

探针矩阵（TP1/TP2/TP3/TP6；TP4/TP5 为结构性检查，不适用）：

| 探针 | TP1 | TP2 | TP3 | TP6 |
|---|---|---|---|---|
| P1（B 的 strides 写成 [1, 3]，行主序算反） | 红 | 红 | 红 | 红 |
| P2（忘掉输出初始化任务，读改写从垃圾值起步） | 绿 | 绿 | 红 | 红 |
| P3（内维 K 的循环上界误用 N） | 绿 | 绿 | 红 | 红 |

['  方案 B：iter_args 从 0 起步（设计选定）: max|diff| = 0.000000e+00  ← 位等价', '  方案 A：fill 0 + 读改写: max|diff| = 0.000000e+00  ← 位等价', '  A′：什么都不做（探针 P2）: max|diff| = 7.770001e+02  ← 不等价（未定义行为）', '  流量账：方案 A 比 B 多付 2×M×N×4 = 96 B 的读写', '  循环 IR vs np.matmul: max|diff| = 2.384e-07（顺序不同，只记录）']

## 9. 设计备注

1. **与 Day 83/84 的衔接**：图优化终图剩下的 `reshape((24,)→(4,6))` 在 Lowering 里是
   免费的——24 元素连续存储，重排成 (4,6) 只是"strides=[6,1] 的元信息改写"，
   零数据搬运（Day 84 补讲 1 的 `shares_memory=True` 已证明）。
   对应规则：`mini.reshape` → 产出同存储的 memref 视图（选做挑战）。
2. **Day 86 待办**：把 §2 的 S2 从"规则表"变成真正的 ConversionPattern 骨架
   （ConversionPatternRewriter 的原子提交、失败处理）——今天的三张任务清单就是它的填空题。

## 附：降级后的循环 IR

```mlir
// 生成自 lowering_design.py（Day 85）——mini.matmul 的循环表示
// 形状 A(4,6) @ B(6,3) -> C(4,3)；循环边界全部来自静态 shape，编译期已知
// 任务标注：[类型] [索引] [初始化] 对应设计文档 §3 的三张任务清单
func @main(%a: memref<4x6xf32, strided<[6, 1]>>,
           %b: memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32> {
  %c = memref.alloc() : memref<4x3xf32, strided<[3, 1]>          // [类型] 结果缓冲，48 B
  %zero = arith.constant 0.0 : f32
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %c4 = arith.constant 4 : index                               // [索引] M 来自 A.shape[0]
  %c3 = arith.constant 3 : index                               // [索引] N 来自 B.shape[1]
  %c6 = arith.constant 6 : index                               // [索引] K 来自 A.shape[1]==B.shape[0]
  scf.for %i = %c0 to %c4 step %c1 {
    scf.for %j = %c0 to %c3 step %c1 {
      %acc = scf.for %k = %c0 to %c6 step %c1
                  iter_args(%acc = %zero) -> (f32) {               // [初始化] 方案 B：iter_args 从 0 起步
        %xa = memref.load %a[%i, %k]     // addr = 6*%i + 1*%k   // [索引]
        %xb = memref.load %b[%k, %j]     // addr = 3*%k + 1*%j   // [索引]
        %p  = arith.mulf %xa, %xb : f32
        %s  = arith.addf %acc, %p : f32
        scf.yield %s : f32
      }
      memref.store %acc, %c[%i, %j]      // addr = 3*%i + 1*%j   // [索引]
    }
  }
  return %c : memref<4x3xf32>
}
```
