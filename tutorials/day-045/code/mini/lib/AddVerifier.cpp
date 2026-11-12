//===- AddVerifier.cpp - mini.add 手写 Verifier -----------------*- C++ -*-===//
//
// 第 40 天的主角之二：mini.add 的 C++ 侧 verify()。
//
// 第 38 天给 Mini_AddOp 挂的 SameOperandsAndResultType trait 已经能查
// "三个类型字面相等"，为什么还要手写？两个原因（教程第 1、3 节展开）：
//   1. trait 的报错只有一句"必须同类型"，说不出"这是 shape 不匹配，
//      连广播都救不了"还是"差一个 broadcast，Day 60 再来"；
//   2. trait 只认字面相等，合法的细化 IR（?x3 + 2x3 -> 2x3）会被误拒；
//      手写可以像 Day 39 一样逐维保守判定。
//
// ODS 约束（Mini_F32Tensor）已经保证：lhs / rhs / res 都是
// RankedTensorType、元素都是 f32——这里不用再查。
// 我们要查的只有两条：
//   规则 1  lhs 与 rhs 的 shape 完全一致（动态维保守放行）；
//   规则 2  res 与 lhs 的 shape 完全一致。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"
#include "ShapeRelation.h"

#include "mlir/IR/BuiltinTypes.h"

using namespace mlir;

LogicalResult mini::AddOp::verify() {
  // ODS 约束已跑完（verifyInvariantsImpl 先于 verify()），放心 cast。
  auto lhs = llvm::cast<RankedTensorType>(getLhs().getType());
  auto rhs = llvm::cast<RankedTensorType>(getRhs().getType());
  auto res = llvm::cast<RankedTensorType>(getRes().getType());

  // 规则 1：两个操作数 shape 一致。拒绝时报错分两种口味
  // （BroadcastOnly / Mismatch），见 ShapeRelation.h。
  if (failed(verifyElementwiseOperands(getOperation(), lhs, rhs)))
    return failure();

  // 规则 2：结果 shape 必须与操作数一致。这里不用 broadcast 口味——
  // 操作数已经一致了，结果单独"想广播"没有语义，直接说人话。
  if (classifyShapePair(lhs, res) != ShapeRelation::Same)
    return emitOpError("result shape must equal the operand shape")
           << ": operands are " << lhs << " and " << rhs << ", but result is "
           << res;

  return success();
}
