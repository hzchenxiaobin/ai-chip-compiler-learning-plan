// 第 48 天级联实验：一趟 -canonicalize 内部的工作表不动点。
//
// 链条：((((1+2)+3)+4)+1) —— 每层 add 的 lhs 都要等上一层折叠成常量后
// 才具备折叠条件；顶部再套 mul(x, 1.0) 和双层 relu。如果驱动只扫一遍
// IR 不回头，这些级联最多塌一层；实测（CHECK 行）全部塌缩：
// 四个 add + 一个 mul + 两层 relu → 一个常量 11.0 + 单层 relu。
//
// run_all.sh 5/7 节用 max-iterations 参数做对照：
//   max-iterations=0：零轮，一个字节都不动（真实输出见 run_all.sh）
//   max-iterations=1：与默认的 10 轮输出逐字节相同——删减型重写的级联
//                     在工作表的一轮排空里就能到底（教程 §4 解释）
//
// CHECK-LABEL: func.func @chain(
// CHECK: %[[C:.*]] = mini.constant dense<1.100000e+01> : tensor<f32>
// CHECK: %[[R:.*]] = mini.relu %[[C]] : tensor<f32> -> tensor<f32>
// CHECK: return %[[R]] : tensor<f32>
// CHECK-NOT: mini.add
// CHECK-NOT: mini.mul
module {
  func.func @chain() -> tensor<f32> {
    %c1 = mini.constant dense<1.0> : tensor<f32>
    %c2 = mini.constant dense<2.0> : tensor<f32>
    %c3 = mini.constant dense<3.0> : tensor<f32>
    %c4 = mini.constant dense<4.0> : tensor<f32>
    %c5 = mini.constant dense<1.0> : tensor<f32>
    %a1 = mini.add %c1, %c2 : tensor<f32>, tensor<f32> -> tensor<f32>
    %a2 = mini.add %a1, %c3 : tensor<f32>, tensor<f32> -> tensor<f32>
    %a3 = mini.add %a2, %c4 : tensor<f32>, tensor<f32> -> tensor<f32>
    %a4 = mini.add %a3, %c5 : tensor<f32>, tensor<f32> -> tensor<f32>
    %m = mini.mul %a4, %c5 : tensor<f32>, tensor<f32> -> tensor<f32>
    %r1 = mini.relu %m : tensor<f32> -> tensor<f32>
    %r2 = mini.relu %r1 : tensor<f32> -> tensor<f32>
    func.return %r2 : tensor<f32>
  }
}
