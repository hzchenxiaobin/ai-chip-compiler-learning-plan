//===- ReluVerifier.cpp - mini.relu 手写 Verifier ----------------*- C++ -*-===//
//
// 第 40 天：mini.relu 的 C++ 侧 verify()。
//
// relu 只有一个操作数和一个结果，规则比 add 还短：input 和 res 的
// shape 必须一致（动态维保守放行）。它是"elementwise 恒等 shape"的
// 最小样本：同一套 classifyShapePair，只调用一次。
//
// 注意规则 2 依然只认 Same：relu 的结果"想广播"（如 2x3 -> 1x3）
// 没有任何合法语义，报错也不需要 broadcast 口味。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"
#include "ShapeRelation.h"

#include "mlir/IR/BuiltinTypes.h"

using namespace mlir;

LogicalResult mini::ReluOp::verify() {
  auto input = llvm::cast<RankedTensorType>(getInput().getType());
  auto res = llvm::cast<RankedTensorType>(getRes().getType());

  if (classifyShapePair(input, res) != ShapeRelation::Same)
    return emitOpError("result shape must equal the input shape")
           << ": input is " << input << ", but result is " << res;

  return success();
}
