// 探针 3：batch 维一侧未知（3D 输入，前 1 维是 batch）。
// lhs batch 是 ?、rhs batch 是 4 —— 规则 R1"取已知一侧"：
// 结果 ?x?x? 应细化成 4x2x2（batch 补 4，M=2，N=2）。

func.func @batch_take_known(%a: tensor<?x2x3xf32>, %b: tensor<4x3x2xf32>) {
  %0 = mini.matmul %a, %b : tensor<?x2x3xf32>, tensor<4x3x2xf32> -> tensor<?x?x?xf32>
  func.return
}
