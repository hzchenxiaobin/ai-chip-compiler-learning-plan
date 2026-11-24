//===- FusedAddReluVerifier.cpp - mini.fused_add_relu Verifier ---*- C++ -*-===//
//
// 第 50 天的主角之二：mini.fused_add_relu 的 C++ 侧 verify()。
//
// 融合算子的 Verifier 写法只有一句话：
//   成员算子的规则求并集，relu 恒等映射的除外（relu 不改变 shape，
//   所以它对 shape 没有任何要求）。
// 于是 fused_add_relu 的规则 = mini.add 的规则，一条不多一条不少：
//   规则 1  lhs 与 rhs 的 shape 完全一致（动态维保守放行）；
//   规则 2  res 与 lhs 的 shape 完全一致。
// 两条都直接复用 ShapeRelation.h 里 mini.add 在用的同一套 helper——
// 物理共享，不是抄一份。融合不能放松验证：如果这里图省事少查一条，
// Day 51 的 Pattern 把 Add+Relu 改写成 fused_add_relu 的瞬间，
// “改写前后 IR 等价”就少了一块基石。
//
// ODS 约束（Mini_F32Tensor）已经保证：lhs / rhs / res 都是
// RankedTensorType、元素都是 f32——这里不用再查。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"
#include "ShapeRelation.h"

#include "mlir/IR/BuiltinTypes.h"

using namespace mlir;

LogicalResult mini::FusedAddReluOp::verify() {
  // ODS 约束已跑完（verifyInvariantsImpl 先于 verify()），放心 cast。
  auto lhs = llvm::cast<RankedTensorType>(getLhs().getType());
  auto rhs = llvm::cast<RankedTensorType>(getRhs().getType());
  auto res = llvm::cast<RankedTensorType>(getRes().getType());

  // 规则 1（= mini.add 规则 1）：两个操作数 shape 一致。
  // 拒绝时报错同样分 BroadcastOnly / Mismatch 两种口味——
  // emitOpError 自动带 'mini.fused_add_relu' op 前缀，姓氏不同而已。
  if (failed(verifyElementwiseOperands(getOperation(), lhs, rhs)))
    return failure();

  // 规则 2（= mini.add 规则 2 ⊇ mini.relu 的规则）：结果 shape 与
  // 操作数一致。relu 的 shape 规则是恒等映射，被这条完全覆盖。
  if (classifyShapePair(lhs, res) != ShapeRelation::Same)
    return emitOpError("result shape must equal the operand shape")
           << ": operands are " << lhs << " and " << rhs << ", but result is "
           << res;

  return success();
}
