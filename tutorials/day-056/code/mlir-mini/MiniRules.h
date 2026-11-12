#ifndef MINI_RULES_H
#define MINI_RULES_H

// MiniRules.h —— 「规则物理共享」头文件（第 53 天立、第 55 天沿用）：
// Verifier 和 Pattern 都要用的形状规则只写一份。
//
//   classifyBias      bias 相对输出的形状三分类
//   verifyMatmul2D    rank-2 f32 matmul 的规则
//   verifyBias        融合算子的 bias 规则（基于三分类）
//
// 第 56 天（复盘）的两处口径调整——让「带 ? 的一张图」能走完四站：
//   1. classifyBias：同秩逐维比较时，任一侧是 ? 记「可能 Same」
//      （第 39 天「对动态维度保守处理」的延续）。真假由 Shape 推导
//      站细化之后自然揭晓；广播分支不做 ? 通配（本壳不出现该组合）。
//   2. verifyMatmul2D：操作数仍要求全静态；结果的维允许写 ?
//      （数字必须等于期望的 [M,N]）——? 的含义是「待推导」，
//      不是「任意」。静态维与 ? 维的区分是第 61 天的话题。

#include "llvm/ADT/ArrayRef.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Operation.h"

namespace mini {

enum class BiasKind { Same, BroadcastOnly, Mismatch };

inline BiasKind classifyBias(mlir::Type biasT, mlir::Type outT) {
  auto bias = biasT.dyn_cast<mlir::RankedTensorType>();
  auto out = outT.dyn_cast<mlir::RankedTensorType>();
  if (!bias || !out)
    return BiasKind::Mismatch;
  if (bias.getShape() == out.getShape())
    return BiasKind::Same;
  auto bs = bias.getShape(), os = out.getShape();
  if (bs.size() == 1 && !os.empty() && bs[0] == os.back())
    return BiasKind::BroadcastOnly;
  // 第 56 天：同秩且逐维「相等或一侧是 ?」→ 可能 Same，保守放行。
  if (bs.size() == os.size()) {
    bool maybe = true;
    for (size_t i = 0; i < bs.size(); ++i)
      if (bs[i] != os[i] && !mlir::ShapedType::isDynamic(bs[i]) &&
          !mlir::ShapedType::isDynamic(os[i]))
        maybe = false;
    if (maybe)
      return BiasKind::Same;
  }
  return BiasKind::Mismatch;
}

// rank-2 f32 matmul：lhs (M,K) · rhs (K,N) -> res (M,N)。
// 操作数要求静态；结果维允许 ?（待推导），是数字就必须等于 [M,N]。
// 返回 failure 前自己 emitOpError。
inline mlir::LogicalResult verifyMatmul2D(mlir::Operation *op,
                                          mlir::Type lhsT, mlir::Type rhsT,
                                          mlir::Type resT) {
  auto fail = [&](auto &&msg) { return op->emitOpError(msg); };
  auto lhs = lhsT.dyn_cast<mlir::RankedTensorType>();
  auto rhs = rhsT.dyn_cast<mlir::RankedTensorType>();
  auto res = resT.dyn_cast<mlir::RankedTensorType>();
  if (!lhs || !rhs || !res)
    return fail("操作数与结果必须是 ranked tensor");
  if (lhs.getRank() != 2 || rhs.getRank() != 2 || res.getRank() != 2)
    return fail("本教程壳只支持 rank-2 张量（完整规则见第 37/39 天）");
  if (!lhs.getElementType().isF32() || !rhs.getElementType().isF32() ||
      !res.getElementType().isF32())
    return fail("元素类型必须是 f32");
  for (auto t : {lhs, rhs})
    for (auto d : t.getShape())
      if (mlir::ShapedType::isDynamic(d))
        return fail("操作数只支持静态维度（完整保守处理见第 39 天）");
  int64_t m = lhs.getShape()[0], k = lhs.getShape()[1];
  int64_t k2 = rhs.getShape()[0], n = rhs.getShape()[1];
  if (k != k2)
    return fail("内维不匹配: lhs 是 [") << m << "," << k << "]，rhs 是 ["
              << k2 << "," << n << "]";
  auto expected = mlir::RankedTensorType::get({m, n}, lhs.getElementType());
  auto es = expected.getShape(), rs = res.getShape();
  for (int i = 0; i < 2; ++i)
    if (rs[i] != es[i] && !mlir::ShapedType::isDynamic(rs[i]))
      return fail("结果 shape 应为 [") << es[0] << "," << es[1]
                << "]（维写 ? 视为待推导），实际 ["
                << rs[0] << "," << rs[1] << "]";
  return mlir::success();
}

// 融合算子的 bias 规则：今天只放行 Same（含 ? 保守放行的 Same）。
inline mlir::LogicalResult verifyBias(mlir::Operation *op, mlir::Type biasT,
                                      mlir::Type resT) {
  BiasKind kind = classifyBias(biasT, resT);
  if (kind == BiasKind::Same)
    return mlir::success();
  if (kind == BiasKind::BroadcastOnly)
    return op->emitOpError("bias 需要广播到结果形状（第 40 天起故意不支持，"
                            "第 60 天放行）");
  return op->emitOpError("bias shape 与结果 shape 连广播都对不上");
}

} // namespace mini

#endif // MINI_RULES_H
