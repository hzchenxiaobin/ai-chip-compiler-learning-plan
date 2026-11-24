// 探针 6：静态承诺冲突（预期失败，rc=1）。
//
// lhs batch 是 ?、rhs batch 是 4、结果 batch 却写死了 2。
// Verifier 拦不住它：batch 检查是"lhs vs rhs"和"lhs vs res"，
// lhs 那一侧是 ?，两两都"无法反驳"，保守放行。
//
// 推导 R1 却能算：batch = rhs 的 4。合并时 old=2（静态承诺）
// 对上 inferred=4 —— 数字对数字，冲突！Pass 的处理不是"改写成 4"，
// 而是当场报错：已有静态维是写 IR 的人的承诺，Pass 无权推翻。

func.func @batch_conflict(%a: tensor<?x2x3xf32>, %b: tensor<4x3x2xf32>) {
  %0 = mini.matmul %a, %b : tensor<?x2x3xf32>, tensor<4x3x2xf32> -> tensor<2x2x2xf32>
  func.return
}
