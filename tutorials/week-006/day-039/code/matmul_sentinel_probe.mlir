// 5.4 节的对照实验用例：N 写错（2 vs 5），M 是动态维。
// 最初版本的报错把 M 打印成内部哨兵值 -9223372036854775808（kDynamicSize），
// 修复后显示为 "?"。拒绝本身从头到尾都是对的——变的是诊断质量。
module {
  func.func @matmul_sentinel_probe(%a: tensor<?x3xf32>, %b: tensor<3x2xf32>) -> tensor<?x5xf32> {
    %c = mini.matmul %a, %b : tensor<?x3xf32>, tensor<3x2xf32> -> tensor<?x5xf32>
    func.return %c : tensor<?x5xf32>
  }
}
