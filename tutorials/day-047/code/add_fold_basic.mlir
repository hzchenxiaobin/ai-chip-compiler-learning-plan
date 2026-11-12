// 第 47 天主角用例：常量碰常量，编译期把和算出来。
//
// 命令：mini-opt -canonicalize add_fold_basic.mlir | FileCheck-18 add_fold_basic.mlir
//
// 期望：
//   @scalar   ：Add(1.0, 2.0) → mini.constant 3.0，add 与两个旧常量一起消失；
//   @tensor23 ：非 splat 的 2x3 常量逐元素相加 → dense<[[1.5, 2.5, 3.5], [4.5, 5.5, 6.5]]>；
//   @bias     ：全 0.5 的 splat bias 加到常量矩阵上 → 每个元素 +0.5（mini-opt
//               实际打印会把 splat 结果展开成完整 2x2 列表，见 CHECK）。
//
// 三个函数的共同点：fold 返回的是"值"（dense 属性），图上的新 mini.constant
// 节点由驱动调用 MiniDialect::materializeConstant 物化——这正是今天的主题。
// CHECK-LABEL: func.func @scalar(
// CHECK: %[[S:.*]] = mini.constant dense<3.000000e+00> : tensor<f32>
// CHECK: return %[[S]] : tensor<f32>
// CHECK-NOT: mini.add
// CHECK-LABEL: func.func @tensor23(
// CHECK: mini.constant dense<{{\[\[1\.500000e\+00, 2\.500000e\+00, 3\.500000e\+00\], \[4\.500000e\+00, 5\.500000e\+00, 6\.500000e\+00\]\]}}> : tensor<2x3xf32>
// CHECK-NOT: mini.add
// CHECK-LABEL: func.func @bias(
// CHECK: mini.constant dense<{{\[\[1\.500000e\+00, 1\.500000e\+00\], \[2\.500000e\+00, 2\.500000e\+00\]\]}}> : tensor<2x2xf32>
// CHECK-NOT: mini.add
module {
  func.func @scalar() -> tensor<f32> {
    %a = mini.constant dense<1.0> : tensor<f32>
    %b = mini.constant dense<2.0> : tensor<f32>
    %s = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s : tensor<f32>
  }
  func.func @tensor23() -> tensor<2x3xf32> {
    %a = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %b = mini.constant dense<[[0.5, 0.5, 0.5], [0.5, 0.5, 0.5]]> : tensor<2x3xf32>
    %s = mini.add %a, %b : tensor<2x3xf32>, tensor<2x3xf32> -> tensor<2x3xf32>
    func.return %s : tensor<2x3xf32>
  }
  func.func @bias() -> tensor<2x2xf32> {
    %a = mini.constant dense<[[1.0, 1.0], [2.0, 2.0]]> : tensor<2x2xf32>
    %b = mini.constant dense<0.5> : tensor<2x2xf32>
    %s = mini.add %a, %b : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
