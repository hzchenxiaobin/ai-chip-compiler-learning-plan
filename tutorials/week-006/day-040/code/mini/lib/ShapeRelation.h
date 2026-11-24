//===- ShapeRelation.h - 逐元素算子的 shape 关系判定 ------------*- C++ -*-===//
//
// 第 40 天的主角之一：mini.add / mini.relu 共用的 shape 分类器。
//
// classifyShapePair 把两个 shape 的静态关系分成三类：
//
//   Same           逐维相等（动态维 ? 视为"无法反驳"，保守算相等）
//                  → 今天接受
//   BroadcastOnly  逐维不相等，但在 NumPy 广播规则下相容
//                  （某维为 1、或秩不同缺位补 1 后相等）
//                  → 今天明确拒绝，报"暂不支持 broadcast"，Day 60 翻开关
//   Mismatch       广播规则也救不了（存在双方都静态且不等、又都不是 1 的维）
//                  → 永久非法，报"shape 不匹配"
//
// 这个三分类就是"Broadcast 扩展边界"的接缝：Day 60 支持广播时，
// 只需把验收政策从"只收 Same"放宽为"收 Same 和 BroadcastOnly"，
// 报错骨架和右对齐比较逻辑原样复用。
//
// 注意与 Day 39 MatmulVerifier 的 staticallyCompatible 的区别：
// matmul 没有"维为 1 可扩展"的概念，逐维只问"相等吗"；这里的裁判
// 多了一个"是不是 1"的出口。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_SHAPERELATION_H
#define MINI_SHAPERELATION_H

#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Operation.h"

namespace mini {

enum class ShapeRelation {
  Same,          // 静态逐维相等（含动态维保守放行）
  BroadcastOnly, // 只有广播规则能救（维为 1 / 秩不同缺位补 1）
  Mismatch,      // 广播规则也救不了
};

// 判定 a 和 b 的 shape 关系。只看静态信息，动态维（?）当作"无法反驳"。
//
// 比较方法与 Day 60 的 broadcast 规则同构：从右往左逐维对齐，
// 秩小的一方缺位当作隐式的 1：
//   * 一对维都静态且相等            → 继续下一对；
//   * 一对维里任一方是 ?            → 无法判定，跳过（保守）；
//   * 一对维相等之外有一方是 1      → 记为"出现过广播维"，继续；
//   * 一对维都静态、不等、且无 1    → 铁证 Mismatch；
//   * 两个秩不一样（必然缺位补 1）  → 至少 BroadcastOnly。
// 循环走完没遇到 Mismatch：出现过广播维（或秩不同）→ BroadcastOnly，
// 否则 → Same。
inline ShapeRelation classifyShapePair(mlir::RankedTensorType a,
                                       mlir::RankedTensorType b) {
  llvm::ArrayRef<int64_t> da = a.getShape();
  llvm::ArrayRef<int64_t> db = b.getShape();
  const int64_t rank = std::max<int64_t>(da.size(), db.size());

  bool sawBroadcastDim = da.size() != db.size(); // 缺位 = 隐式 1
  for (int64_t i = 0; i < rank; ++i) {
    // 从右往左数第 i 对维；缺位的那一侧当作 1。
    int64_t x = i < (int64_t)da.size() ? da[da.size() - 1 - i] : 1;
    int64_t y = i < (int64_t)db.size() ? db[db.size() - 1 - i] : 1;
    if (mlir::ShapedType::isDynamic(x) || mlir::ShapedType::isDynamic(y))
      continue; // 有 ? 就无法判定这一对，保守跳过
    if (x == y)
      continue;
    if (x == 1 || y == 1) {
      sawBroadcastDim = true;
      continue;
    }
    return ShapeRelation::Mismatch;
  }
  return sawBroadcastDim ? ShapeRelation::BroadcastOnly : ShapeRelation::Same;
}

// mini.add 的操作数检查：Same 放行；另外两类各给一条"说人话"的报错。
// 报错挂在 op 上（位置 + 'mini.add' op 前缀由 emitOpError 自动带）。
inline mlir::LogicalResult verifyElementwiseOperands(mlir::Operation *op,
                                                     mlir::RankedTensorType lhs,
                                                     mlir::RankedTensorType rhs) {
  switch (classifyShapePair(lhs, rhs)) {
  case ShapeRelation::Same:
    return mlir::success();
  case ShapeRelation::BroadcastOnly:
    return op->emitOpError("requires identical operand shapes, but got ")
           << lhs << " and " << rhs
           << ", which would broadcast; broadcasting is not supported yet"
              " (see Day 60) -- expand the smaller operand to the exact"
              " shape for now";
  case ShapeRelation::Mismatch:
    return op->emitOpError("requires identical operand shapes, but got ")
           << lhs << " and " << rhs
           << ", which do not match dimension by dimension and are not"
              " broadcast-compatible either";
  }
  llvm_unreachable("covered all shape relations");
}

} // namespace mini

#endif // MINI_SHAPERELATION_H
