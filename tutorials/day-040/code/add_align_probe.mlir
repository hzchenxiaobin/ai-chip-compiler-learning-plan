// 负例 3：右对齐探针——3x2x4 + 2x4。
//   右对齐（正确）：4v4、2v2、3v缺位1 -> BroadcastOnly；
//   左对齐（错误）：3v2 开局就撞 -> 误判 Mismatch，把"能广播"说成
//   "永久不匹配"，报错口径完全跑偏（教程错误 4 的照妖镜）。
// broadcast 规则从右往左比，不是从左往左——这个文件钉死它。
module {
  func.func @add_align_probe(%a: tensor<3x2x4xf32>, %b: tensor<2x4xf32>) -> tensor<3x2x4xf32> {
    %s = mini.add %a, %b : tensor<3x2x4xf32>, tensor<2x4xf32> -> tensor<3x2x4xf32>
    func.return %s : tensor<3x2x4xf32>
  }
}
