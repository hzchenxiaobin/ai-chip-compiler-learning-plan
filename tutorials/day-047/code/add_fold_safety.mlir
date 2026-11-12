// 第 47 天负例合集：三道护栏各拦一个——IR 一个字节不许变。
//
// 命令：mini-opt -canonicalize add_fold_safety.mlir | FileCheck-18 add_fold_safety.mlir
//
//   @from_arg   ：操作数是函数入口参数，FoldAdaptor 里没有 dense 属性
//                 （常量匹配失败）——运行时可能恰好传 1.0 和 2.0，
//                 但编译器无法证明"永远是"，不许动手；
//   @from_relu  ：操作数是 mini.relu 的结果（非常量定义者），同上；
//   @typeguard  ：结果类型 ?x3 与操作数 2x3 不一致（类型护栏）——
//                 Day 40 的 Verifier 对动态维保守放行，这种 IR 合法，
//                 但物化出的常量类型是静态 2x3，顶替 ?x3 的结果会让
//                 使用者类型对不上（Day 46 同款教训，今天在 fold 复现）；
//   @bigtensor  ：64x64 = 4096 个元素 > kMaxFoldElements(1024)
//                 （尺寸护栏）——编译期展开的代价可能超过省下的
//                 运行期开销，直接拒绝（5.6 节实测这个代价有多大）。
// CHECK-LABEL: func.func @from_arg(
// CHECK: mini.add %arg0, %arg1 : tensor<f32>, tensor<f32> -> tensor<f32>
// CHECK-LABEL: func.func @from_relu(
// CHECK: %[[R:.*]] = mini.relu %arg0 : tensor<f32> -> tensor<f32>
// CHECK: mini.add %[[R]], %arg1 : tensor<f32>, tensor<f32> -> tensor<f32>
// CHECK-LABEL: func.func @typeguard(
// CHECK: mini.add %{{.*}}, %{{.*}} : tensor<2x3xf32>, tensor<2x3xf32> -> tensor<?x3xf32>
// CHECK: return
// CHECK-LABEL: func.func @bigtensor(
// CHECK: mini.add %{{.*}}, %{{.*}} : tensor<64x64xf32>, tensor<64x64xf32> -> tensor<64x64xf32>
// CHECK: return
module {
  func.func @from_arg(%arg0: tensor<f32>, %arg1: tensor<f32>) -> tensor<f32> {
    %s = mini.add %arg0, %arg1 : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s : tensor<f32>
  }
  func.func @from_relu(%arg0: tensor<f32>, %arg1: tensor<f32>) -> tensor<f32> {
    %r = mini.relu %arg0 : tensor<f32> -> tensor<f32>
    %s = mini.add %r, %arg1 : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s : tensor<f32>
  }
  func.func @typeguard() -> tensor<?x3xf32> {
    %a = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %b = mini.constant dense<[[0.5, 0.5, 0.5], [0.5, 0.5, 0.5]]> : tensor<2x3xf32>
    %s = mini.add %a, %b : tensor<2x3xf32>, tensor<2x3xf32> -> tensor<?x3xf32>
    func.return %s : tensor<?x3xf32>
  }
  func.func @bigtensor() -> tensor<64x64xf32> {
    %a = mini.constant dense<1.0> : tensor<64x64xf32>
    %b = mini.constant dense<2.0> : tensor<64x64xf32>
    %s = mini.add %a, %b : tensor<64x64xf32>, tensor<64x64xf32> -> tensor<64x64xf32>
    func.return %s : tensor<64x64xf32>
  }
}
