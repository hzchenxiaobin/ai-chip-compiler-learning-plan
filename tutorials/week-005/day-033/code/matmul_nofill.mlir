// 探针⑦：故意去掉 linalg.fill——tensor.empty 的内容未定义，
// matmul 的累加语义会把垃圾加进结果：JIT 输出不确定（未初始化内存）
// 本机 2026-11-12 三连跑：139 / -2147483648 / -2147483648（偶然对 ≠ 正确）
module {
  func.func @main() -> i32 {
    %A = arith.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %B = arith.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %C = tensor.empty() : tensor<2x2xf32>
    %R = linalg.matmul ins(%A, %B : tensor<2x3xf32>, tensor<3x2xf32>) outs(%C : tensor<2x2xf32>) -> tensor<2x2xf32>
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %e = tensor.extract %R[%c1, %c0] : tensor<2x2xf32>
    %r = arith.fptosi %e : f32 to i32
    return %r : i32
  }
}
