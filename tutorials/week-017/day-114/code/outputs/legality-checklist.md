# 第 114 天：最终 Lowering 合法性清单（机器生成）

输入：GEMM A(4×6)@B(6×3) 的循环 IR（`loop_ir.mlir`）。每个源 op 一行：终态判定、负责的模式、目标 op 序列、实现排期。

## 一、源 op → 目标（对照实验 A/B 之外，全部由驱动器逐 op 记账）

| 源 op（本例出现次数） | 源方言 | 终态判定 | 模式 | 目标 op 序列 | 排期 |
|---|---|---|---|---|---|
| `func.func`（1） | func | 非法，必须转换 | F1 | llvm.func | D115 |
| `func.return`（1） | func | 非法，必须转换 | R1 | llvm.return | D115 |
| `arith.constant`（6） | arith | 非法，必须转换 | A1 | llvm.mlir.constant | D115 |
| `arith.muli / arith.addi`（0） | arith | 非法，必须转换 | A2 | llvm.mul / llvm.add | D116 |
| `arith.mulf / arith.addf`（2） | arith | 非法，必须转换 | A3 | llvm.fmul / llvm.fadd | D116 |
| `scf.for（含体内 scf.yield）`（4） | scf | 非法，必须转换 | C1 | llvm.br + llvm.icmp + llvm.cond_br + llvm.add（含块参数） | D117 |
| `memref.load`（2） | memref | 非法，必须转换 | M1 | llvm.extractvalue×4 + llvm.mul×2 + llvm.add×2 + llvm.getelementptr + llvm.load | D116 |
| `memref.store`（1） | memref | 非法，必须转换 | M2 | llvm.extractvalue×4 + llvm.mul×2 + llvm.add×2 + llvm.getelementptr + llvm.store | D116 |
| `memref.alloc`（1） | memref | 非法，必须转换 | M3 | llvm.call @malloc + llvm.mlir.undef + llvm.insertvalue×7 | D116 |
| `mini.*`（0） | mini | 非法，必须转换 | （无） | 无模式——残留并报错 | 不做 |
| `vector.*`（0） | vector | 非法，必须转换 | （无） | 无模式——明确暂不支持 | 不做 |

## 二、终态合法集（目标形态里实际出现的 llvm.* op，机器统计）

- `llvm.br` × 6
- `llvm.call @malloc` × 1
- `llvm.cond_br` × 3
- `llvm.mlir.constant` × 12
- `llvm.extractvalue` × 12
- `llvm.getelementptr` × 3
- `llvm.mul / llvm.add / llvm.fmul / llvm.fadd` × 17
- `llvm.icmp` × 3
- `llvm.insertvalue` × 7
- `llvm.load` × 2
- `llvm.return` × 1
- `llvm.store` × 1
- `llvm.mlir.undef` × 1

## 三、类型兑换表（TypeConverter）

| 源类型 | 目标类型 | 说明 |
|---|---|---|
| `index` | `i64` | 位宽随目标指针宽度（64 位目标），LLVM 方言没有 index |
| `f32` | `f32` | 原样（LLVM 方言兼容类型） |
| `i32` | `i32` | 原样 |
| `memref<4x6xf32, strided<[6,1]>>` | `!llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>` | 五字段描述符：allocated/aligned/offset/sizes/strides，按值传递，64 位目标上 56 字节 |
| `tensor<...>` | 拒收 | 管道纪律：必须先 bufferize（D85~D105） |
| `memref<?x?xf32>` | 拒收 | 动态 shape 暂不支持（'暂不支持'第 1 条） |

## 四、暂不支持清单（残留报告里它们的理由）

1. **动态 shape／动态 strides／动态 offset**：运行时才知道 sizes/strides，描述符填充必须搬到运行期；本周所有 shape 静态已知。
2. **tensor 残留**：兑换表拒收（管道纪律），报'类型转换失败'。
3. **`mini.*` 残留**：终态非法且无模式——必须在第一段 Lowering 处理。
4. **`vector.*`**：本周 IR 不会出现，出现即出界输入，残留报告'明确暂不支持'。
5. **`memref.dealloc`**：源 IR 不生成（D105 的计划式内存不做逐点释放）；模式 M4（llvm.call @free）列入清单但排期'本周不做'。
6. **f64／f16／混合精度**：类型表只收 f32 与整型；扩展=加一行兑换+核对目标支持。
7. **对齐处理**：描述符保留 aligned_ptr 字段（与真实 MLIR 一致），本周 allocated == aligned；真实 MemRefToLLVM 会做对齐偏移。
