// 第 49 天（第 7 周复盘）的第二个组合用例：Shape 推导解锁 Pattern。
//
//   %c0, %c1 : 常量 0.5
//   %one     : add(0.5, 0.5)      —— fold 把它变成常量 1.0
//   %mm      : matmul(a, b) -> tensor<?x2xf32>
//              —— 结果类型故意写成 ?x2：ShapeInferencePass 才能把它细化成 2x2
//   %m       : mul(%mm, %one) -> 2x2
//              —— Pattern 的类型护栏要求 x 的类型 == 结果类型：
//                 %mm 是 ?x2 时护栏拦下；细化成 2x2 后才放行
//   %r1, %r2 : relu 链
//              —— 只有 %m 被改写成 %mm 后，Relu(Relu) 才能匹配
//
// 对照 combo.mlir：那边三种机制在同一个 -canonicalize 里就能接力；
// 这边多了一道“信息关卡”——不给 -mini-infer-shape，代数化简的类型
// 护卫永远过不去，canonicalize 跑到不动点也不是最简 IR。

func.func @combo_shape(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
  %c0 = mini.constant dense<0.5> : tensor<2x2xf32>
  %c1 = mini.constant dense<0.5> : tensor<2x2xf32>
  %one = mini.add %c0, %c1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %mm = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
  %m = mini.mul %mm, %one : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %r1 = mini.relu %m : tensor<2x2xf32> -> tensor<2x2xf32>
  %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
  return %r2 : tensor<2x2xf32>
}
