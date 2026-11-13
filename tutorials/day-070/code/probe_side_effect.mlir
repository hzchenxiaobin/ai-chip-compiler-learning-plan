// probe_side_effect.mlir —— 探针 4（反例 R4：副作用语义）
//
// 同一个函数里放两个「无使用者」的 op：
//   memref.store（有副作用：写外部内存）  ← 不能删
//   arith.addf  （纯计算，结果没人用）    ← 可以删
// 图结构上两者一样（都没有使用者），内存语义上一个是观察点、一个是死代码。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt probe_side_effect.mlir --cse          → store 留，addf 删
//   mlir-opt probe_side_effect.mlir --canonicalize → store 留，addf 删

func.func @side_effect(%x: memref<2x3xf32>, %v: f32, %a: f32, %b: f32) {
  %c0 = arith.constant 0 : index
  memref.store %v, %x[%c0, %c0] : memref<2x3xf32>
  %dead = arith.addf %a, %b : f32
  return
}
