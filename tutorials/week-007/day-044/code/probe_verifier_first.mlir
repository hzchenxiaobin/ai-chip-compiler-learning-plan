// 探针 8：Verifier 先拦的对照（预期失败，rc=1，且加不加 Pass 都一样）。
//
// 2x? · ?x2，结果却写 ?x3：N 的来源（rhs 最后一维）是静态的 2，
// 结果里的 N 也是静态的 3 —— 两个数字对不上，这是 Verifier 规则 4
// "输出 shape 必须是 [M, N]"能直接证明的非法，解析阶段就被拦下，
// 根本轮不到 -mini-infer-shape 出场（连不加 Pass 也一样报错）。
//
// 与 probe_conflict.mlir 对照：那边 Verifier 看不见（lhs batch 是 ?，
// 两两比较都"无法反驳"），只有推导 R1 算出 batch=4 后冲突才暴露 ——
// 一个是"质检拦下"，一个是"推导发现"，分工就在这条线上。

func.func @verifier_owns(%a: tensor<2x?xf32>, %b: tensor<?x2xf32>) {
  %0 = mini.matmul %a, %b : tensor<2x?xf32>, tensor<?x2xf32> -> tensor<?x3xf32>
  func.return
}
