//===- Passes.h - mini pass declarations -----------------------*- C++ -*-===//
//
// mini 方言自己的 Pass 都在这里对外声明注册函数。
// 第 41 天只有一个：mini-count-ops（统计每个函数里的操作数）。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_PASSES_H
#define MINI_PASSES_H

namespace mlir {
namespace mini {

/// 把 mini-count-ops 注册进全局 PassRegistry。
/// mini-opt 的 main 里调用一次，命令行从此认识 -mini-count-ops。
void registerCountOpsPass();

} // namespace mini
} // namespace mlir

#endif // MINI_PASSES_H
