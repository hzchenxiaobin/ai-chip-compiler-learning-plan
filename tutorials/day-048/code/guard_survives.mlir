// 第 48 天负例：组合管道威力再大，安全边界一个都不许丢。
// Day 46 论证过的两条否决（+0.0 不许消、混合零不许消）在“四种能力
// 组合运行”之后必须依然成立——这是组合测试的核心回归点：
// 管道顺序可以变，数值安全不能变。
//
//   @plus_zero_bias：bias 是全体 +0.0。Shape 推导照样把 ?x2 细化成
//   2x2（类型护栏两侧同型了！），但代数化简的值判定 isNegZero(+0.0)
//   = false——x = -0.0 时 (+0.0) 会翻符号位，Day 46 的否决继续有效。
//   add 必须原样留存。
//
//   @mixed_zero_bias：bias 是 dense<[[-0.0, +0.0], [+0.0, -0.0]]>。
//   “每个元素都是零”≠splat：+0.0 与 -0.0 位模式不同，没有单一恒等
//   值。Shape 推导同样已把 ?x2 细化，类型护栏放行，但常量匹配的
//   isSplat() 判定不过——add 必须原样留存。
//
// 注意 CHECK 里的 2x2：两个函数的 matmul 结果都应已被细化成静态
// shape（推导照跑），只是 add 之后的化简不许发生。
//
// CHECK-LABEL: func.func @plus_zero_bias(
// CHECK: %[[P:.*]] = mini.constant dense<0.000000e+00> : tensor<2x2xf32>
// CHECK: %[[M1:.*]] = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
// CHECK: %[[S1:.*]] = mini.add %[[M1]], %[[P]] : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
// CHECK: %[[R1:.*]] = mini.relu %[[S1]] : tensor<2x2xf32> -> tensor<2x2xf32>
// CHECK: return %[[R1]] : tensor<2x2xf32>
//
// CHECK-LABEL: func.func @mixed_zero_bias(
// CHECK: %[[Z:.*]] = mini.constant dense<{{\[\[-0\.000000e\+00, 0\.000000e\+00\], \[0\.000000e\+00, -0\.000000e\+00\]\]}}> : tensor<2x2xf32>
// CHECK: %[[M2:.*]] = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
// CHECK: %[[S2:.*]] = mini.add %[[M2]], %[[Z]] : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
// CHECK: %[[R2:.*]] = mini.relu %[[S2]] : tensor<2x2xf32> -> tensor<2x2xf32>
// CHECK: return %[[R2]] : tensor<2x2xf32>
module {
  func.func @plus_zero_bias(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    %p = mini.constant dense<0.0> : tensor<2x2xf32>
    %s = mini.add %m, %p : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
  func.func @mixed_zero_bias(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    %z = mini.constant dense<[[-0.0, 0.0], [0.0, -0.0]]> : tensor<2x2xf32>
    %s = mini.add %m, %z : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
