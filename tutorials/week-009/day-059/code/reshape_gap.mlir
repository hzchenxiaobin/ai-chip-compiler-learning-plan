// reshape_gap.mlir —— 第 59 天：Verifier 没拦住的错（本机 LLVM 18.1.8 实测通过）。
//
// 运行：mlir-opt reshape_gap.mlir   （注意：exit=0，它居然通过了！）
//
// 源是 3x4（12 个元素），结果类型静态写死 5x3（15 个元素）。
// 元素数量不守恒在两边类型上都是静态可见的，但 memref.reshape 的
// Verifier 并不检查它——真正的形状来自运行期 %shape 操作数，
// 类型里的 5x3 只是「声明」。如果运行期 %shape 真的给 [5,3]，
// 取数就会越界读别人的内存。
//
// 这正是学习计划要求 mini.reshape「增加元素数量和 Shape 检查」的原因：
// 静态可见的约束，应该在 Verifier 里静态拦住。
// （对照：expand_shape/collapse_shape 会静态检查分组尺寸，
//   见 bad_reshape.mlir 房间 3。）

func.func @reshape_wrong_count(%arg0: memref<3x4xf32>,
                               %shape: memref<2xindex>) -> memref<5x3xf32> {
  %0 = memref.reshape %arg0(%shape)
    : (memref<3x4xf32>, memref<2xindex>) -> memref<5x3xf32>
  return %0 : memref<5x3xf32>
}
