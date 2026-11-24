// M08 f64_matmul_chain（负例·类型，对应 Python C14）——
// 全 f64 的 MatMul 链：matmul 的 Verifier 明确要求 f32，
// 在 parse + verify 这一层就拦下，Pattern 根本不会看到它。
// 期望判决 = verifier_reject（第一道闸门）
func.func @graph_f64_matmul(%arg0: tensor<2x3xf64>, %arg1: tensor<3x2xf64>) -> tensor<2x2xf64> {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf64>, tensor<3x2xf64> -> tensor<2x2xf64>
  %1 = mini.relu %0 : tensor<2x2xf64>
  return %1 : tensor<2x2xf64>
}
