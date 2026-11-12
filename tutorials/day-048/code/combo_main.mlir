// 第 48 天主线实验：一张图上同时埋好四种优化机会，等组合管道来收。
//
//   %za, %zb : 两个 -0.0 常量          → Fold 机会（Day 47）：
//               %z = add(%za, %zb) 折叠成一个 -0.0 常量
//               （IEEE：-0.0 + -0.0 = -0.0，物化后仍是合法的加零 bias）
//   %m       : matmul 结果类型 ?x2     → Shape 推导机会（Day 44）：
//               细化成 2x2——它同时是 %s 能否被代数化简的前置条件
//   %s       : add(%m, %z)             → 代数化简机会（Day 46）：
//               类型护栏要求 lhs/res 同型，所以推导必须先行；
//               %z 被折叠成常量后 rhs 才满足常量匹配
//   %r1, %r2 : 双层 relu               → 结构化简机会（Day 45）
//
// 观察点（run_all.sh 4/7 节）：
//   (a) -canonicalize                ：bias 折叠了，但 %s 被类型护栏拦下
//   (b) -mini-combined                ：四种机会全部兑现，只剩 matmul+relu
//   (c) -canonicalize -mini-infer-shape：顺序换了，窗口错过，%s 永久留存
//   (d) -canonicalize -mini-infer-shape -canonicalize：手动多轮救回
//
// 本文件的 CHECK 行对应 (b) 的期望输出；(a)/(c)/(d) 由 run_all.sh 用
// grep -c mini.add 分别断言为 1 / 1 / 0。
//
// CHECK-LABEL: func.func @target(
// CHECK: %[[M:.*]] = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
// CHECK: %[[R:.*]] = mini.relu %[[M]] : tensor<2x2xf32> -> tensor<2x2xf32>
// CHECK: return %[[R]] : tensor<2x2xf32>
// CHECK-NOT: mini.add
// CHECK-NOT: mini.constant
module {
  func.func @target(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    %za = mini.constant dense<-0.0> : tensor<2x2xf32>
    %zb = mini.constant dense<-0.0> : tensor<2x2xf32>
    %z = mini.add %za, %zb : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m, %z : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r1 = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r2 : tensor<2x2xf32>
  }
}
