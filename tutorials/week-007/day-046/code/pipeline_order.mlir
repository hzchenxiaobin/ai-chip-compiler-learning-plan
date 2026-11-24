// 第 46 天主线实验：目标图 MatMul → Add(全零 bias) → ReLU → ReLU，
// 同一个文件跑三种 Pass 顺序，观察"优化前后 IR"和"顺序的代价"：
//
//   (a) -canonicalize
//       matmul 的结果类型是 ?x2，add 的 lhs 是 ?x2、结果却是 2x2——
//       Verifier 眼里"保守相等"，类型系统眼里是两个类型。类型护栏
//       拦下重写：add 保留，只有 relu(relu(x)) 塌缩。
//   (b) -mini-infer-shape -canonicalize
//       shape 推导先把 ?x2 细化成 2x2，护栏两侧类型一致，add 消失，
//       全零 bias 连带出局——整张图只剩 matmul + 单个 relu。
//   (c) -canonicalize -mini-infer-shape
//       先 canonicalize 再推导：护栏拦下时没人细化类型，推导做完
//       也不会回头再跑一遍 canonicalize——优化机会永久错过。
//       （Day 48 的"组合运行优化 Pass / 不动点"就来解决这个问题。）
//
// 数值约定（手算，供 Day 124 之后对答案）：
//   A·B = [[58,64],[139,154]]，加全零 bias 不变，relu 一次与两次相同。
//
// 本文件的 CHECK 行对应 (b) 的期望；(a)/(c) 由 run_all.sh 用
// grep -c mini.add 分别断言为 1（add 还在）。
// CHECK-LABEL: func.func @target(
// CHECK: %[[M:.*]] = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
// CHECK: %[[R:.*]] = mini.relu %[[M]]
// CHECK: return %[[R]]
// CHECK-NOT: mini.add
// CHECK-NOT: mini.constant
// CHECK-NOT: mini.relu
module {
  func.func @target(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    %z = mini.constant dense<-0.0> : tensor<2x2xf32>
    %s = mini.add %m, %z : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r1 = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r2 : tensor<2x2xf32>
  }
}
