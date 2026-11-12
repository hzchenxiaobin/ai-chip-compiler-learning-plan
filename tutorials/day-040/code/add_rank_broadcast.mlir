// 负例 2：秩不同——1x2x3 + 2x3。从右往左对齐，缺位当作隐式 1：
//   维对齐 (1,2,3) 对 (·,2,3) -> 3v3、2v2、1v缺位1，全部过得去，
//   但秩不同本身就意味着"必须广播" -> BroadcastOnly。
// 这个文件同时是"sawBroadcastDim 忘了秩初始化"bug 的照妖镜（教程错误 3）。
module {
  func.func @add_rank_broadcast(%a: tensor<1x2x3xf32>, %b: tensor<2x3xf32>) -> tensor<1x2x3xf32> {
    %s = mini.add %a, %b : tensor<1x2x3xf32>, tensor<2x3xf32> -> tensor<1x2x3xf32>
    func.return %s : tensor<1x2x3xf32>
  }
}
