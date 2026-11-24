// dyn_dims.mlir —— 动态维的运行期真相
// ? 不是「任意」，而是「编译期不知道、运行期才知道」；
// 想知道具体数值，用 tensor.dim 在运行期问，结果类型是 index
func.func @numel(%x: tensor<?x?xf32>) -> index {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  // tensor.dim：张量维度的运行期取值入口，第二个操作数是维度编号（index）
  %d0 = tensor.dim %x, %c0 : tensor<?x?xf32>
  %d1 = tensor.dim %x, %c1 : tensor<?x?xf32>
  %n = arith.muli %d0, %d1 : index
  return %n : index
}

// 混合维：第 0 维静态（2），第 1 维动态——两个世界可以共存
func.func @mixed(%x: tensor<2x?xf32>) -> index {
  %c0 = arith.constant 0 : index
  // 第 0 维是静态的 2，但照样可以用 tensor.dim 问（结果还是 index）
  %d0 = tensor.dim %x, %c0 : tensor<2x?xf32>
  return %d0 : index
}
