// 探针 5：同样的输入（2x? · ?x2），结果类型的三种写法 ——
// 合并规则（refineShape）的对照实验，5.4 节的主角。
//
//   @res_dyn      结果写 ?x? ：M、N 都由推导补上      -> 2x2
//   @res_m_known  结果写 2x? ：M 已有承诺（保留），N 补 -> 2x2
//   @res_full     结果写 2x2 ：一维都不缺，Pass 不碰 IR  -> 2x2（统计 0）
//
// 三种写法全部合法（Verifier 对 ? 保守放行），最终也都停在 2x2 ——
// 区别只在"哪几维是推导补的、统计表里记几笔"。

func.func @res_dyn(%a: tensor<2x?xf32>, %b: tensor<?x2xf32>) {
  %0 = mini.matmul %a, %b : tensor<2x?xf32>, tensor<?x2xf32> -> tensor<?x?xf32>
  func.return
}

func.func @res_m_known(%a: tensor<2x?xf32>, %b: tensor<?x2xf32>) {
  %0 = mini.matmul %a, %b : tensor<2x?xf32>, tensor<?x2xf32> -> tensor<2x?xf32>
  func.return
}

func.func @res_full(%a: tensor<2x?xf32>, %b: tensor<?x2xf32>) {
  %0 = mini.matmul %a, %b : tensor<2x?xf32>, tensor<?x2xf32> -> tensor<2x2xf32>
  func.return
}
