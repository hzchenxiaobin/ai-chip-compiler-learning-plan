// 第 48 天上游探针：同样的级联问题，交给 mlir-opt-18 -canonicalize。
// 上游 arith 的常量折叠链：((1.0 + 2.0) + 1.0) 应在一趟内塌缩成
// 单个 arith.constant 4.0——见证“贪婪驱动迭代到不动点”是 MLIR
// 通用机制，不是 mini 的私货。
//
// CHECK-LABEL: func.func @chain(
// CHECK: %[[C:.*]] = arith.constant 4.000000e+00 : f32
// CHECK: return %[[C]] : f32
// CHECK-NOT: arith.addf
module {
  func.func @chain() -> f32 {
    %c1 = arith.constant 1.0 : f32
    %c2 = arith.constant 2.0 : f32
    %a1 = arith.addf %c1, %c2 : f32
    %a2 = arith.addf %a1, %c1 : f32
    func.return %a2 : f32
  }
}
