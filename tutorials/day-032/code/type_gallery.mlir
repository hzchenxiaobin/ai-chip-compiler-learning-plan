// type_gallery.mlir —— 类型画廊：今天的合法示例全家福（10 个，全部可解析可验证）
// 每个参数演示一类 Type；Day 30 的「类型巡游」只路过，今天逐个上户口
func.func @type_gallery(
  %sc_i32: i32,                  // 32 位有符号整数
  %sc_f32: f32,                  // 32 位浮点
  %sc_i1: i1,                    // 1 位整数：cmpi / cmpf 的结果类型
  %idx: index,                   // 宽度与目标相关的下标类型：循环边界、维度编号专用
  %t_static: tensor<2x3xf32>,    // 全静态维张量：2 行 3 列，编译期已写死
  %t_dyn: tensor<?x?xf32>,       // 全动态维张量：形状运行期才知道
  %t_mixed: tensor<2x?xf32>,     // 混合维：行数静态，列数动态
  %t_scalar: tensor<f32>,        // 0 维张量：形状是 []，恰好装 1 个数
  %m_strided: memref<2x3xf32, strided<[3, 1]>>, // 带物理布局的缓冲区视图（Day 57 深挖）
  %vec: vector<4xf32>            // 向量类型：长度固定，SIMD 的菜
) {
  return
}
