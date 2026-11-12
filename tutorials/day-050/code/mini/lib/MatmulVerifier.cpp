//===- MatmulVerifier.cpp - mini.matmul 手写 Verifier ----------*- C++ -*-===//
//
// 第 39 天的主角：mini.matmul 的 C++ 侧 verify()。
//
// MiniOps.td 里 Mini_MatmulOp 打开了 hasVerifier = 1，tblgen 生成的
// MiniOps.h.inc 会声明  ::mlir::LogicalResult mini::MatmulOp::verify();
// 并让 verifyInvariants() 在跑完 ODS 约束之后调用它——函数本体就在这里。
//
// 第 50 天重构：四条形状规则原样搬进 MatmulRules.h 的
// verifyMatmulShapes()——因为今天的融合算子 mini.fused_matmul_bias_relu
// 必须逐条复用同一套规则（融合不放松验证）。本文件从此只剩
// “取三个类型 + 转发”，规则本体一处维护。
//
// 行为零变化：规则内容、报错文案、动态维保守策略逐字符照搬 Day 39，
// 重构后 Day 39 的全部 13 个测试原样通过（见当日教程 5.3 节）。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"
#include "MatmulRules.h"

#include "mlir/IR/BuiltinTypes.h"

using namespace mlir;

LogicalResult mini::MatmulOp::verify() {
  // ODS 约束已在 verifyInvariants 的前半段跑完，这里可以放心 cast。
  auto lhs = llvm::cast<RankedTensorType>(getLhs().getType());
  auto rhs = llvm::cast<RankedTensorType>(getRhs().getType());
  auto res = llvm::cast<RankedTensorType>(getRes().getType());

  // 四条规则（秩相等 / batch 对齐 / 内维匹配 / 输出 [M,N]）
  // 全部住在 MatmulRules.h 里，与融合算子共享同一份实现。
  return mini::verifyMatmulShapes(getOperation(), lhs, rhs, res);
}
