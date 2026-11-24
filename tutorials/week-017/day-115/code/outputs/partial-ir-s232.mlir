// 半转换产物（partial 模式）：F1/R1/A1 已转换，其余记入残账（排期 D116/D117）
// 第 2×3×2 GEMM 的循环形态（第 115 天输入，由本脚本生成）
llvm.func @gemm(%a: !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, %b: !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> {
  %a_m = builtin.unrealized_conversion_cast %a : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> memref<2x3xf32, strided<[3, 1]>>   // 胶水：入口参数已换新类型，残留 op 还要旧值
  %b_m = builtin.unrealized_conversion_cast %b : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> memref<3x2xf32, strided<[2, 1]>>   // 胶水：入口参数已换新类型，残留 op 还要旧值
  %c = memref.alloc() : memref<2x2xf32, strided<[2, 1]>>   // 残留：M3 排期 D116
  %zero = llvm.mlir.constant 0.0 : f32
  %c0 = llvm.mlir.constant 0 : i64
  %c0_i = builtin.unrealized_conversion_cast %c0 : i64 -> index   // 胶水：scf.for 还要 index
  %c1 = llvm.mlir.constant 1 : i64
  %c1_i = builtin.unrealized_conversion_cast %c1 : i64 -> index   // 胶水：scf.for 还要 index
  %cM = llvm.mlir.constant 2 : i64
  %cM_i = builtin.unrealized_conversion_cast %cM : i64 -> index   // 胶水：scf.for 还要 index
  %cN = llvm.mlir.constant 2 : i64
  %cN_i = builtin.unrealized_conversion_cast %cN : i64 -> index   // 胶水：scf.for 还要 index
  %cK = llvm.mlir.constant 3 : i64
  %cK_i = builtin.unrealized_conversion_cast %cK : i64 -> index   // 胶水：scf.for 还要 index
  scf.for %i = %c0_i to %cM_i step %c1_i {   // 残留：C1 排期 D117
    scf.for %j = %c0_i to %cN_i step %c1_i {   // 残留：C1 排期 D117
      %acc = scf.for %k = %c0_i to %cK_i step %c1_i   // 残留：C1 排期 D117
                  iter_args(%acc = %zero) -> (f32) {
        %xa = memref.load %a_m[%i, %k] : memref<2x3xf32, strided<[3, 1]>>   // 残留：M1 排期 D116
        %xb = memref.load %b_m[%k, %j] : memref<3x2xf32, strided<[2, 1]>>   // 残留：M1 排期 D116
        %p = arith.mulf %xa, %xb : f32   // 残留：A3 排期 D116
        %s = arith.addf %acc, %p : f32   // 残留：A3 排期 D116
        scf.yield %s : f32   // 残留：C1 排期 D117
      }
      memref.store %acc, %c[%i, %j] : memref<2x2xf32, strided<[2, 1]>>   // 残留：M2 排期 D116
    }
  }
  %c_d = builtin.unrealized_conversion_cast %c : memref<2x2xf32, strided<[2, 1]>> -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>   // 胶水：llvm.return 要新类型
  llvm.return %c_d : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
}
