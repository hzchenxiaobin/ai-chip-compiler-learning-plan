# 第 115 天：签名转换表（机器生成）

| # | 源签名 | 目标 llvm.func 签名 | 参数字节 | 结果字节 |
|---|---|---|---|---|
| S1 GEMM | `(memref<4x6xf32, strided<[6, 1]>>, memref<6x3xf32, strided<[3, 1]>>) -> (memref<4x3xf32, strided<[3, 1]>>)` | `llvm.func @s1_fn(%a0: !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, %a1: !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>` | 112 | 56 |
| S2 Relu | `(f32) -> (f32)` | `llvm.func @s2_fn(%a0: f32) -> f32` | 4 | 4 |
| S3 Add | `(f32, f32) -> (f32)` | `llvm.func @s3_fn(%a0: f32, %a1: f32) -> f32` | 8 | 4 |
| S4 init | `() -> ()` | `llvm.func @s4_fn()` | 0 | 0 |
| S5 scale | `(index, index) -> (f32)` | `llvm.func @s5_fn(%a0: i64, %a1: i64) -> f32` | 16 | 4 |
| S6 rank1 点积 | `(memref<5xf32, strided<[1]>>) -> (f32)` | `llvm.func @s6_fn(%a0: !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>) -> f32` | 40 | 4 |
| S7 rank3 求和 | `(memref<2x3x4xf32, strided<[12, 4, 1]>>) -> (f32)` | `llvm.func @s7_fn(%a0: !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)>) -> f32` | 72 | 4 |
| S8 双结果 | `(memref<4x3xf32, strided<[3, 1]>>, f32) -> (f32, f32)` | `llvm.func @s8_fn(%a0: !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, %a1: f32) -> !llvm.struct<(f32, f32)>` | 60 | 8 |
| S9 双 memref 结果 | `(memref<2x2xf32, strided<[2, 1]>>) -> (memref<2x2xf32, strided<[2, 1]>>, memref<2x2xf32, strided<[2, 1]>>)` | `llvm.func @s9_fn(%a0: !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>) -> !llvm.struct<(!llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>)>` | 56 | 112 |
| S10 混合标量 | `(f64, i32, f32) -> (i32)` | `llvm.func @s10_fn(%a0: f64, %a1: i32, %a2: f32) -> i32` | 16 | 4 |

打包规则：0 结果 -> void；1 结果 -> 兑换类型；≥2 结果 -> !llvm.struct<(...)>（真实 MLIR FuncToLLVM 同样打包多结果）。
字节账来自 DataLayout（TP1 与真机 LLVM 对账）。
