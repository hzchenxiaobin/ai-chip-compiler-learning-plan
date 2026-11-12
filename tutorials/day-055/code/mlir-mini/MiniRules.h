#ifndef MINI_RULES_H
#define MINI_RULES_H

// MiniRules.h —— 第 53 天起「规则物理共享」的头文件（方法同第 50 天的
// MatmulRules.h）：Verifier 和 Pattern 都要用的形状规则只写一份。
//
//   classifyBias      bias 相对输出的形状三分类
//   verifyMatmul2D    rank-2 静态 matmul 的三条规则
//   verifyBias        融合算子的 bias 规则（基于三分类）
//
// 口径与第 40/50 天的 mini 工程完全一致；本壳限定 rank-2 静态 f32。

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
  return BiasKind::Mismatch;
}

// rank-2 静态 matmul：lhs (M,K) · rhs (K,N) -> res (M,N)。
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
  for (auto t : {lhs, rhs, res})
    for (auto d : t.getShape())
      if (mlir::ShapedType::isDynamic(d))
        return fail("本教程壳只支持静态维度（? 维度的保守处理见第 39 天）");
  int64_t m = lhs.getShape()[0], k = lhs.getShape()[1];
  int64_t k2 = rhs.getShape()[0], n = rhs.getShape()[1];
  if (k != k2)
    return fail("内维不匹配: lhs 是 [") << m << "," << k << "]，rhs 是 ["
              << k2 << "," << n << "]";
  auto expected = mlir::RankedTensorType::get({m, n}, lhs.getElementType());
  if (res != expected)
    return fail("结果 shape 应为 [") << m << "," << n << "]（跟 matmul 走），实际 ["
              << res.getShape()[0] << "," << res.getShape()[1] << "]";
  return mlir::success();
}

// 融合算子的 bias 规则：今天只放行 Same。
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
