//===- MatmulRules.h - mini.matmul 形状规则的共享实现 -----------*- C++ -*-===//
//
// 第 50 天的主角之一：把 MatmulVerifier.cpp（Day 39）里的四条形状规则
// 提取成共享的 inline 函数 verifyMatmulShapes()。
//
// 为什么要提取？今天定义的融合算子 mini.fused_matmul_bias_relu 的
// 前半截语义就是一次矩阵乘法，它的 Verifier 必须逐条复用 matmul 的
// 全部规则——如果复制粘贴一份，规则将来改了（比如 Day 61 支持动态
// batch 维的符号推导）就得改两处，漏一处融合算子就成了“规则弱化版”。
// 共享函数让“融合不放松验证”从口头承诺变成物理事实：
//   mini.matmul 的 verify()            → verifyMatmulShapes(...)  4 条
//   mini.fused_matmul_bias_relu 的 verify() → verifyMatmulShapes(...) 4 条
//                                          + bias 同形状规则（各自实现）
//
// 四条规则原文照抄 Day 39（教程编号沿用）：
//   规则 1  lhs / rhs / res 三个秩相等；
//   规则 2  batch 维（前 rank-2 维）三方逐维对齐；
//   规则 3  内维匹配：lhs 最后一维 == rhs 倒数第二维；
//   规则 4  输出 shape：res 最后两维 == [lhs 的 M, rhs 的 N]。
//
// 动态维（?）的裁判也照抄：任一方动态 → 保守放行，绝不误拒合法 IR。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_MATMULRULES_H
#define MINI_MATMULRULES_H

#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Operation.h"

#include <string>

namespace mini {

//===----------------------------------------------------------------------===//
// 维度工具（原 MatmulVerifier.cpp 匿名命名空间的两个 helper 平移至此）
//===----------------------------------------------------------------------===//

// 两个维度“静态兼容”吗？只比较双方都静态已知的维度：
//   * 都静态且相等   → 兼容；
//   * 都静态但不等   → 铁证非法，必须报错；
//   * 任一方是动态维（写成 ? 的维度）→ 编译期无法判定，保守放行。
// “保守”的准确含义：Verifier 只拦“能证明非法”的 IR；证明不了的，
// 交给 Shape 推导（Day 43/44）或运行期。绝不能反过来：
// 把“不知道”当成“非法”去误拒合法 IR。
inline bool staticallyCompatible(int64_t a, int64_t b) {
  if (mlir::ShapedType::isDynamic(a) || mlir::ShapedType::isDynamic(b))
    return true;
  return a == b;
}

// 把维度打印成用户看得懂的样子：动态维显示为 "?"，
// 而不是内部哨兵值 kDynamicSize（一个巨大的负数，只会吓到人）。
inline std::string dimToString(int64_t d) {
  return mlir::ShapedType::isDynamic(d) ? "?" : std::to_string(d);
}

//===----------------------------------------------------------------------===//
// 四条 matmul 形状规则。报错挂在调用方传入的 op 上（emitOpError 自动
// 带 'mini.matmul' op 或 'mini.fused_matmul_bias_relu' op 前缀——
// 错误消息的“姓氏”跟着调用者走，规则本体不分家）。
//===----------------------------------------------------------------------===//

inline mlir::LogicalResult verifyMatmulShapes(mlir::Operation *op,
                                              mlir::RankedTensorType lhs,
                                              mlir::RankedTensorType rhs,
                                              mlir::RankedTensorType res) {
  using namespace mlir;

  // 规则 1：秩一致。ODS 只保证“各自 >= 2”，没保证“互相相等”。
  if (lhs.getRank() != rhs.getRank() || lhs.getRank() != res.getRank())
    return op->emitOpError("requires the same rank for both operands and the "
                           "result")
           << ", but got ranks " << lhs.getRank() << ", " << rhs.getRank()
           << " and " << res.getRank() << " for " << lhs << ", " << rhs
           << " and " << res;

  const int64_t rank = lhs.getRank();

  // 规则 2：batch 维逐维对齐（lhs==rhs 且 lhs==res，传递覆盖 rhs==res）。
  for (int64_t i = 0; i < rank - 2; ++i) {
    if (!staticallyCompatible(lhs.getDimSize(i), rhs.getDimSize(i)))
      return op->emitOpError("batch dimensions must agree between operands")
             << ": dim #" << i << " is " << lhs.getDimSize(i) << " in " << lhs
             << ", but " << rhs.getDimSize(i) << " in " << rhs;
    if (!staticallyCompatible(lhs.getDimSize(i), res.getDimSize(i)))
      return op->emitOpError("batch dimensions of the result must match the "
                             "operands")
             << ": dim #" << i << " is " << lhs.getDimSize(i) << " in " << lhs
             << ", but " << res.getDimSize(i) << " in " << res;
  }

  const int64_t m = lhs.getDimSize(rank - 2);
  const int64_t kL = lhs.getDimSize(rank - 1);
  const int64_t kR = rhs.getDimSize(rank - 2);
  const int64_t n = rhs.getDimSize(rank - 1);

  // 规则 3：内维匹配。lhs 是 [..., M, K]，rhs 必须是 [..., K, N]。
  if (!staticallyCompatible(kL, kR))
    return op->emitOpError("requires matching inner dimensions")
           << ": lhs " << lhs << " ends in " << kL << ", but rhs " << rhs
           << " has second-to-last dim " << kR
           << " (expected lhs [..., M, K] times rhs [..., K, N])";

  // 规则 4：输出 shape。res 必须是 [..., M, N]。
  // 注意消息里用 dimToString：触发本分支时 m / n 可能是动态维
  // （另一维不匹配才进的来），直接打印会泄漏内部哨兵值。
  if (!staticallyCompatible(m, res.getDimSize(rank - 2)) ||
      !staticallyCompatible(n, res.getDimSize(rank - 1)))
    return op->emitOpError("result shape must be [M, N] derived from the "
                           "operands")
           << ": expected [..., " << dimToString(m) << ", " << dimToString(n)
           << "] from lhs " << lhs << " and rhs " << rhs << ", but got " << res;

  return success();
}

} // namespace mini

#endif // MINI_MATMULRULES_H
