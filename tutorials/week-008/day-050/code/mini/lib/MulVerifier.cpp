//===- MulVerifier.cpp - mini.mul 手写 Verifier -----------------*- C++ -*-===//
//
// 第 42 天（第 6 周复盘）的主角：mini.mul 的 C++ 侧 verify()。
//
// 复盘题：mini.mul 的 shape 规则和 mini.add 一模一样——那直接把
// SameOperandsAndResultType trait 挂回去，零行 C++ 不香吗？
// Day 40 已经用 mini.add 答过一遍，今天换 mul 再答一次：
//   1. trait 只认字面类型相等，合法的细化 IR（?x3 * 2x3 -> 2x3）
//      会被误拒；手写可以逐维保守判定（? = 无法反驳，先放行）；
//   2. trait 的报错只有一句"必须同类型"，说不出"这是 shape 永久
//      不匹配"还是"差一个 broadcast，Day 60 再来"。
// 同族算子应该共享裁判而不是各写一套：本文件的全部逻辑都是
// ShapeRelation.h 的复用——第 40 天埋下的接缝今天第一次兑现。
//
// ODS 约束（Mini_F32Tensor）已经保证：lhs / rhs / res 都是
// RankedTensorType、元素都是 f32——这里不用再查。
// 我们要查的只有两条（与 AddVerifier.cpp 逐行同构）：
//   规则 1  lhs 与 rhs 的 shape 完全一致（动态维保守放行）；
//   规则 2  res 与 lhs 的 shape 完全一致。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"
#include "ShapeRelation.h"

#include "mlir/IR/BuiltinTypes.h"

using namespace mlir;

LogicalResult mini::MulOp::verify() {
  // ODS 约束已跑完（verifyInvariantsImpl 先于 verify()），放心 cast。
  auto lhs = llvm::cast<RankedTensorType>(getLhs().getType());
  auto rhs = llvm::cast<RankedTensorType>(getRhs().getType());
  auto res = llvm::cast<RankedTensorType>(getRes().getType());

  // 规则 1：两个操作数 shape 一致。verifyElementwiseOperands 会自动带上
  // 'mini.mul' op 前缀（emitOpError 挂在本 op 上，名字随 op 走），
  // 拒绝时报错分两种口味（BroadcastOnly / Mismatch），见 ShapeRelation.h。
  if (failed(verifyElementwiseOperands(getOperation(), lhs, rhs)))
    return failure();

  // 规则 2：结果 shape 必须与操作数一致。操作数已经一致了，
  // 结果单独"想广播"没有语义，直接说人话。
  if (classifyShapePair(lhs, res) != ShapeRelation::Same)
    return emitOpError("result shape must equal the operand shape")
           << ": operands are " << lhs << " and " << rhs << ", but result is "
           << res;

  return success();
}
