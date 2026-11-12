// 5.4 对照实验：把 K 从 3 改成 4（A 变 2×4，B 变 4×2）
// 高层只改两行字面量，循环层的 k 上界会自动跟着变（%c3 → %c4）
// 预测 C[1][0] ＝ 5·7＋6·9＋7·11＋8·13 ＝ 270
module {
  func.func @main() -> i32 {
    %A = arith.constant dense<[[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]> : tensor<2x4xf32>
    %B = arith.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0], [13.0, 14.0]]> : tensor<4x2xf32>
    %zero = arith.constant 0.0 : f32
    %C = tensor.empty() : tensor<2x2xf32>
    %Cf = linalg.fill ins(%zero : f32) outs(%C : tensor<2x2xf32>) -> tensor<2x2xf32>
    %R = linalg.matmul ins(%A, %B : tensor<2x4xf32>, tensor<4x2xf32>) outs(%Cf : tensor<2x2xf32>) -> tensor<2x2xf32>
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %e = tensor.extract %R[%c1, %c0] : tensor<2x2xf32>
    %r = arith.fptosi %e : f32 to i32
    return %r : i32
  }
}
