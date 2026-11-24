//===- MatmulVerifier.cpp - mini.matmul 手写 Verifier ----------*- C++ -*-===//
//
// 第 39 天的主角：mini.matmul 的 C++ 侧 verify()。
//
// MiniOps.td 里 Mini_MatmulOp 打开了 hasVerifier = 1，tblgen 生成的
// MiniOps.h.inc 会声明  ::mlir::LogicalResult mini::MatmulOp::verify();
// 并让 verifyInvariants() 在跑完 ODS 约束之后调用它——函数本体就在这里。
//
// ODS 已经保证（我们不用再查）：
//   * lhs / rhs / res 都是 RankedTensorType；
//   * 元素类型都是 f32；
//   * 秩都 >= 2。
// 我们要查的是 ODS 表达不了的"跨操作数关系"：
//   规则 1  三个秩相等；
//   规则 2  batch 维（前 rank-2 维）对齐；
//   规则 3  内维匹配：lhs 最后一维 == rhs 倒数第二维；
//   规则 4  输出 shape：res 最后两维 == [lhs 的 M, rhs 的 N]。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"

#include "mlir/IR/BuiltinTypes.h"

#include <string>

using namespace mlir;

namespace {

// 两个维度"静态兼容"吗？只比较双方都静态已知的维度：
//   * 都静态且相等   → 兼容；
//   * 都静态但不等   → 铁证非法，必须报错；
//   * 任一方是动态维（写成 ? 的维度）→ 编译期无法判定，保守放行。
// "保守"的准确含义：Verifier 只拦"能证明非法"的 IR；证明不了的，
// 交给后面的 Shape 推导（Day 43/44）或运行期。绝不能反过来：
// 把"不知道"当成"非法"去误拒合法 IR。
bool staticallyCompatible(int64_t a, int64_t b) {
  if (ShapedType::isDynamic(a) || ShapedType::isDynamic(b))
    return true;
  return a == b;
}

// 把维度打印成用户看得懂的样子：动态维显示为 "?"，
// 而不是内部哨兵值 kDynamicSize（一个巨大的负数，只会吓到人）。
std::string dimToString(int64_t d) {
  return ShapedType::isDynamic(d) ? "?" : std::to_string(d);
}

} // namespace

LogicalResult mini::MatmulOp::verify() {
  // ODS 约束已在 verifyInvariants 的前半段跑完，这里可以放心 cast。
  auto lhs = llvm::cast<RankedTensorType>(getLhs().getType());
  auto rhs = llvm::cast<RankedTensorType>(getRhs().getType());
  auto res = llvm::cast<RankedTensorType>(getRes().getType());

  // 规则 1：秩一致。ODS 只保证"各自 >= 2"，没保证"互相相等"。
  if (lhs.getRank() != rhs.getRank() || lhs.getRank() != res.getRank())
    return emitOpError("requires the same rank for both operands and the "
                       "result")
           << ", but got ranks " << lhs.getRank() << ", " << rhs.getRank()
           << " and " << res.getRank() << " for " << lhs << ", " << rhs
           << " and " << res;

  const int64_t rank = lhs.getRank();

  // 规则 2：batch 维逐维对齐（lhs==rhs 且 lhs==res，传递覆盖 rhs==res）。
  for (int64_t i = 0; i < rank - 2; ++i) {
    if (!staticallyCompatible(lhs.getDimSize(i), rhs.getDimSize(i)))
      return emitOpError("batch dimensions must agree between operands")
             << ": dim #" << i << " is " << lhs.getDimSize(i) << " in " << lhs
             << ", but " << rhs.getDimSize(i) << " in " << rhs;
    if (!staticallyCompatible(lhs.getDimSize(i), res.getDimSize(i)))
      return emitOpError("batch dimensions of the result must match the "
                         "operands")
             << ": dim #" << i << " is " << lhs.getDimSize(i) << " in " << lhs
             << ", but " << res.getDimSize(i) << " in " << res;
  }

  const int64_t m = lhs.getDimSize(rank - 2);
  const int64_t kL = lhs.getDimSize(rank - 1);
  const int64_t kR = rhs.getDimSize(rank - 2);
  const int64_t n = rhs.getDimSize(rank - 1);

  // 规则 3：内维匹配。lhs 是 [..., M, K]，rhs 必须是 [..., K, N]。
  if (!staticallyCompatible(kL, kR))
    return emitOpError("requires matching inner dimensions")
           << ": lhs " << lhs << " ends in " << kL << ", but rhs " << rhs
           << " has second-to-last dim " << kR
           << " (expected lhs [..., M, K] times rhs [..., K, N])";

  // 规则 4：输出 shape。res 必须是 [..., M, N]。
  // 注意消息里用 dimToString：触发本分支时 m / n 可能是动态维
  // （另一维不匹配才进的来），直接打印会泄漏内部哨兵值。
  if (!staticallyCompatible(m, res.getDimSize(rank - 2)) ||
      !staticallyCompatible(n, res.getDimSize(rank - 1)))
    return emitOpError("result shape must be [M, N] derived from the operands")
           << ": expected [..., " << dimToString(m) << ", " << dimToString(n)
           << "] from lhs " << lhs << " and rhs " << rhs << ", but got " << res;

  return success();
}
