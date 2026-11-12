// 第 33 天主例子：用 linalg.matmul 替身出演 mini.matmul
// 语义：C = A(2×3) × B(3×2)，取 C[1][0] 转成 i32 返回
// 五个方言共住：builtin(module) · func · arith · tensor · linalg
module {
  func.func @main() -> i32 {
    // arith 方言：常量（值住在 value 属性里，Day 32）
    %A = arith.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %B = arith.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %zero = arith.constant 0.0 : f32
    // tensor 方言：未初始化的张量"格子"
    %C = tensor.empty() : tensor<2x2xf32>
    // linalg 方言：先把格子清零——matmul 是累加语义（outs 既当输入又当输出），
    // tensor.empty 的内容未定义，不清零就是读垃圾（见教程 6.1 的翻车现场）
    %Cf = linalg.fill ins(%zero : f32) outs(%C : tensor<2x2xf32>) -> tensor<2x2xf32>
    // 一条 op ＝ 一次完整矩阵乘：mini.matmul 将来的样子
    %R = linalg.matmul ins(%A, %B : tensor<2x3xf32>, tensor<3x2xf32>) outs(%Cf : tensor<2x2xf32>) -> tensor<2x2xf32>
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %e = tensor.extract %R[%c1, %c0] : tensor<2x2xf32>
    %r = arith.fptosi %e : f32 to i32
    return %r : i32
  }
}
