// 冒烟测试：mini 还没有任何算子，所以这份 IR 里暂时看不到 mini.* ——
// 明天（Day 37）会出现第一行 %c = mini.matmul %a, %b ...
// 今天 mini-opt 的任务是：把 module/func 解析→验证→打印，一个字不差地还回来。
module {
  func.func @smoke(%x: tensor<2x3xf32>) -> tensor<2x3xf32> {
    return %x : tensor<2x3xf32>
  }
}
