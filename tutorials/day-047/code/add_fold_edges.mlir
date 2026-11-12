// 第 47 天边界用例：fold 出来的就是运行期会算出的同一个位模式吗？
// 用 IEEE 754 的三个边角值做见证——fold 用 APFloat 逐元素加法
// （rmNearestTiesToEven），与运行期 f32 加法同一条标准。
//
// 命令：mini-opt -canonicalize add_fold_edges.mlir | FileCheck-18 add_fold_edges.mlir
//
// 期望（实测：MLIR 打印器对 NaN 输出十六进制位模式 0x7FC00000）：
//   @inf_sum   ：(+Inf) + (-Inf) = NaN（IEEE 规定，不许编出 ±Inf）；
//   @negneg    ：(-0.0) + (-0.0) = -0.0（同号零相加得同号零）；
//   @posneg    ：(+0.0) + (-0.0) = +0.0（异号零相加得 +0.0）。
//
// 这三个结果和 Day 46 的 IEEE 对照表同一张底片：fold 不是"近似计算"，
// 它复刻的就是硬件会做的每一位。
// CHECK-LABEL: func.func @inf_sum(
// CHECK: mini.constant dense<0x7FC00000> : tensor<f32>
// CHECK-NOT: mini.add
// CHECK-LABEL: func.func @negneg(
// CHECK: mini.constant dense<-0.000000e+00> : tensor<f32>
// CHECK-NOT: mini.add
// CHECK-LABEL: func.func @posneg(
// CHECK: mini.constant dense<0.000000e+00> : tensor<f32>
// CHECK-NOT: mini.add
module {
  func.func @inf_sum() -> tensor<f32> {
    %a = mini.constant dense<0x7F800000> : tensor<f32>   // +Inf
    %b = mini.constant dense<0xFF800000> : tensor<f32>   // -Inf
    %s = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s : tensor<f32>
  }
  func.func @negneg() -> tensor<f32> {
    %a = mini.constant dense<-0.0> : tensor<f32>
    %b = mini.constant dense<-0.0> : tensor<f32>
    %s = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s : tensor<f32>
  }
  func.func @posneg() -> tensor<f32> {
    %a = mini.constant dense<0.0> : tensor<f32>
    %b = mini.constant dense<-0.0> : tensor<f32>
    %s = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s : tensor<f32>
  }
}
