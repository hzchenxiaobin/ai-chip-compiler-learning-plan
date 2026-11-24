//===- Passes.h - mini pass declarations -----------------------*- C++ -*-===//
//
// mini 方言自己的 Pass 都在这里对外声明注册函数。
// 第 41 天：mini-count-ops（统计每个函数里的操作数）。
// 第 44 天：mini-infer-shape（mini.matmul 的输出 shape 推导）。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_PASSES_H
#define MINI_PASSES_H

namespace mlir {
namespace mini {

/// 把 mini-count-ops 注册进全局 PassRegistry。
/// mini-opt 的 main 里调用一次，命令行从此认识 -mini-count-ops。
void registerCountOpsPass();

/// 把 mini-infer-shape 注册进全局 PassRegistry（第 44 天）：
/// 对每个 mini.matmul 用操作数 shape 推导结果 shape，只细化 ? 不改数字。
void registerShapeInferencePass();

} // namespace mini
} // namespace mlir

#endif // MINI_PASSES_H
