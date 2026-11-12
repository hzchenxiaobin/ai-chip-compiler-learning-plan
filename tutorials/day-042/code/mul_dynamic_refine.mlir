// 正例 3：动态维细化——?x3 * 2x3 -> 2x3。
// lhs 的 M 是 ?，右边是 2：手写 Verifier 的裁判说"无法反驳，放行"
// （结果比输入更具体是合法方向）。
// 看点：这个文件在"trait 版 mini.mul"（SameOperandsAndResultType）
// 下会被误拒——trait 只认三个类型字面相等。run_all.sh 的对照实验
// 会把它分别喂给两个版本。
func.func @mul_refine(%a: tensor<?x3xf32>, %b: tensor<2x3xf32>) -> tensor<2x3xf32> {
  %p = mini.mul %a, %b : tensor<?x3xf32>, tensor<2x3xf32> -> tensor<2x3xf32>
  func.return %p : tensor<2x3xf32>
}
