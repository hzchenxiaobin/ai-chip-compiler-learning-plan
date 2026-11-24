//===- FusedMatmulBiasReluVerifier.cpp --------------------------*- C++ -*-===//
//
// 第 50 天的主角之三：mini.fused_matmul_bias_relu 的 C++ 侧 verify()。
//
// 规则还是那句口诀：成员算子的规则求并集，再叠上自己的增量。
//   规则 1～4（= mini.matmul 的全部规则，逐条照搬）
//       秩相等 / batch 对齐 / 内维匹配 / 输出 [M,N]——
//       一行 verifyMatmulShapes() 转发到 MatmulRules.h（今天刚从
//       MatmulVerifier.cpp 里提取出来的共享实现），物理复用。
//   规则 5（自己的增量：bias 的 shape）
//       bias 必须与结果 shape 完全一致（今天没有 broadcast）。
//       判定复用 ShapeRelation.h 的三分类：
//         Same           → 通过；
//         BroadcastOnly  → [N] 风格 bias（tensor<2xf32> 对 2x2），
//                          合法语义但今天不支持，报“Day 60 再来”；
//         Mismatch       → 谁也救不了（3x2 对 2x2），直接拦。
//
// 为什么 bias 对 res 比、而不是直接对 [M,N] 比？因为规则 4 刚刚
// 查过 res = [M,N]（静态维铁证），bias 与 res 一致就等价于与 [M,N]
// 一致——少抄一遍 M、N 的取数逻辑，两条规则的先后顺序也自然成立：
// res 写错先报 res（规则 4），res 对了才轮到 bias（规则 5）。
//
// ODS 约束已经保证：lhs / rhs / res 是秩 >= 2 的 f32 张量，bias 是
// 任意秩的 f32 张量（[N] 风格 bias 放进来，由规则 5 给出高质量报错）。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"
#include "MatmulRules.h"
#include "ShapeRelation.h"

#include "mlir/IR/BuiltinTypes.h"

using namespace mlir;

LogicalResult mini::FusedMatmulBiasReluOp::verify() {
  // ODS 约束已跑完（verifyInvariantsImpl 先于 verify()），放心 cast。
  auto lhs = llvm::cast<RankedTensorType>(getLhs().getType());
  auto rhs = llvm::cast<RankedTensorType>(getRhs().getType());
  auto bias = llvm::cast<RankedTensorType>(getBias().getType());
  auto res = llvm::cast<RankedTensorType>(getRes().getType());

  // 规则 1～4（= mini.matmul 全部规则）：转发给共享实现。
  // 报错前缀自动是 'mini.fused_matmul_bias_relu' op——同一个函数，
  // 两个姓氏。
  if (failed(mini::verifyMatmulShapes(getOperation(), lhs, rhs, res)))
    return failure();

  // 规则 5（自己的增量）：bias 与结果 shape 完全一致。
  // 三分类裁判与 mini.add 同款，但报错文案是 bias 专属的。
  switch (classifyShapePair(bias, res)) {
  case ShapeRelation::Same:
    return success();
  case ShapeRelation::BroadcastOnly:
    return emitOpError("requires bias to have exactly the result shape")
           << ": bias is " << bias << ", result is " << res
           << ", which would broadcast; broadcasting is not supported yet"
              " (see Day 60) -- tile the bias to the full result shape"
              " for now";
  case ShapeRelation::Mismatch:
    return emitOpError("requires bias to have exactly the result shape")
           << ": bias is " << bias << ", but result is " << res
           << ", which do not match dimension by dimension";
  }
  llvm_unreachable("covered all shape relations");
}
