#include "MiniDialect.h"

#include "MiniRules.h"

#include "mlir/IR/DialectImplementation.h"

using namespace mlir;

// TableGen 生成：MiniDialect 构造函数、类型注册
#include "MiniDialect.cpp.inc"

// TableGen 生成：五个算子的 parse/print/verify/build 实现
#define GET_OP_CLASSES
#include "MiniOps.cpp.inc"

// 注册本 Dialect 的全部算子：解析器和 Pattern 驱动靠这里认识 mini.* 操作
void mini::MiniDialect::initialize() {
  addOperations<mini::MatmulOp, mini::AddOp, mini::ReluOp,
                mini::FusedMatmulBiasOp, mini::FusedMatmulBiasReluOp>();
}

// ===================== 手写 Verifier：规则来自 MiniRules.h =====================

LogicalResult mini::MatmulOp::verify() {
  return verifyMatmul2D(getOperation(), getLhs().getType(),
                        getRhs().getType(), getRes().getType());
}

LogicalResult mini::AddOp::verify() {
  // rhs 相对 lhs 三分类（add 对称，bias 在哪侧都行——先按 rhs 报，
  // 报错文案只说形状不说左右，两侧交换后读者自己能对上）
  mlir::Type lhsT = getLhs().getType(), rhsT = getRhs().getType();
  auto lhs = lhsT.dyn_cast<mlir::RankedTensorType>();
  auto rhs = rhsT.dyn_cast<mlir::RankedTensorType>();
  if (!lhs || !rhs)
    return emitOpError("操作数必须是 ranked tensor");
  switch (classifyBias(rhsT, lhsT)) {
  case mini::BiasKind::Same:
    break;
  case mini::BiasKind::BroadcastOnly:
    return emitOpError("rhs shape 对 lhs 需要广播——第 40 天起故意不支持"
                       "（第 60 天放行）");
  case mini::BiasKind::Mismatch:
    return emitOpError("两个操作数 shape 不匹配");
  }
  if (getRes().getType() != lhsT)
    return emitOpError("结果类型必须等于 lhs 类型");
  return success();
}

LogicalResult mini::FusedMatmulBiasOp::verify() {
  if (failed(verifyMatmul2D(getOperation(), getLhs().getType(),
                            getRhs().getType(), getRes().getType())))
    return failure();
  return verifyBias(getOperation(), getBias().getType(), getRes().getType());
}

LogicalResult mini::FusedMatmulBiasReluOp::verify() {
  if (failed(verifyMatmul2D(getOperation(), getLhs().getType(),
                            getRhs().getType(), getRes().getType())))
    return failure();
  return verifyBias(getOperation(), getBias().getType(), getRes().getType());
}
