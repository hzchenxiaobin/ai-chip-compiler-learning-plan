// CSE 探针：同一个 (a, b) 乘两遍、同一个 relu 也上两遍，
// 再各自 add + return。mini.matmul / mini.add / mini.relu 都带 Pure trait
// （无副作用），理论上 -cse 应该把重复计算合并。
// 看点：%m2、%r2 这两行会不会从输出里消失。
module {
  func.func @dup() -> (tensor<2x2xf32>, tensor<2x2xf32>) {
    %a = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %b = mini.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %m1 = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %m2 = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %bias = mini.constant dense<[[-100.0, 0.0], [-1.0, -200.0]]> : tensor<2x2xf32>
    %s1 = mini.add %m1, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r1 = mini.relu %s1 : tensor<2x2xf32> -> tensor<2x2xf32>
    %s2 = mini.add %m2, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %s2 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r1, %r2 : tensor<2x2xf32>, tensor<2x2xf32>
  }
}
