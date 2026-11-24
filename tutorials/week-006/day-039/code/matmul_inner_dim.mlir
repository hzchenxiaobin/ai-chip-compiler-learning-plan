// 负例 1（Day 37 埋下、Day 38 依旧放行、今天终于被拦的探针）：
//   内维不匹配：2x3 · 2x3 -> 2x3
//   lhs 最后一维是 3，rhs 倒数第二维是 2，K 对不上。
//   ODS 视角：三个类型都是"秩>=2 的 f32 张量"，全部合法；
//   Verifier 视角：3 != 2，铁证非法。
module {
  func.func @matmul_inner_dim(%a: tensor<2x3xf32>, %b: tensor<2x3xf32>) -> tensor<2x3xf32> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<2x3xf32> -> tensor<2x3xf32>
    func.return %c : tensor<2x3xf32>
  }
}
