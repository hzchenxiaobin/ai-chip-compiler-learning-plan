// 第 50 天回归测试 1：未融合的目标图必须原样通过（rc=0）。
// 这是第 13 天构造、第 41 天挂进 mini-opt 的 MatMul -> Add -> Relu 图。
// 今天定义了融合算子，但一个 Pattern 都还没写——图优化之前的世界
// 必须毫发无损。第 51 天起这张图才会被改写成融合形式。

func.func @target_graph(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
  %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %bias = mini.constant dense<[[0.5, -1.0], [-2.0, 3.5]]> : tensor<2x2xf32>
  %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
  return %r : tensor<2x2xf32>
}
