//===- ShapeInferencePass.cpp - mini.matmul 形状推导 Pass -------*- C++ -*-===//
//
// 第 44 天的主角：-mini-infer-shape。
//
// 昨天用 Python 写好的规则表 R0~R4（day-043/code/matmul_infer.py）今天
// 原样翻译成 C++，挂进 mini-opt 的 Pass 流水线。实现刻意拆成两层：
//
//   1. inferMatmulShape(lhs, rhs)  —— 纯函数：只看两个操作数类型，
//      算出“输出 shape 应该是什么”。不改 IR，不诊断，可以直接单测。
//      规则与 Python 版逐条对应：
//        R0  防御性前提（rank>=2、秩相等；正常管线里 ODS+Verifier 先拦）；
//        R1  batch 维取已知一侧：lhs 静态取 lhs，否则取 rhs，都 ? 才 ?；
//        R2  输出 M = lhs 倒数第 2 维（? 原样传播）；
//        R3  输出 N = rhs 倒数第 1 维（? 原样传播）；
//        R4  K 被消费、不进输出：2x? · ?x2 照样推出 2x2。
//   2. ShapeInferencePass —— 机械动作：遍历函数里的 mini.matmul，
//      用纯函数算出目标 shape，再与结果类型里已有的静态信息合并：
//        * old 是数字  → 保留。已有静态维是写 IR 的人对 Verifier 的承诺，
//                        Pass 无权改写（Verifier 规则 4 的地盘）；
//        * old 是 ?    → 采纳推导值（推导值本身也可能是 ?）。
//      合并结果与原 shape 相同就不碰 IR，否则 setType 写回。
//
// “只把 ? 细化成数字，绝不动已有数字”是整个 Pass 的安全边界：
// 细化是信息增量，语义必然保持；改写已有数字才可能制造新错误。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"
#include "mini/Passes.h"

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/Pass/Pass.h"

using namespace mlir;

namespace {

//===----------------------------------------------------------------------===//
// 1) 纯函数规则：Day 43 R0~R4 的 C++ 直译
//===----------------------------------------------------------------------===//

// 输入两个操作数类型，返回推导出的输出 shape（动态维用 kDynamicSize
// 表示，打印成 “?”）。返回 failure 表示结构性非法——正常管线里
// ODS（Mini_F32Tensor2DPlus）和 Verifier 规则 1/3 先行拦截，
// 这里只是被直接调用时的兜底，与 Python 版的防御语义一致。
FailureOr<SmallVector<int64_t, 4>> inferMatmulShape(RankedTensorType lhs,
                                                    RankedTensorType rhs) {
  // R0：秩必须相等（rank>=2 已由 ODS 保证，这里不再重复查）。
  if (lhs.getRank() != rhs.getRank())
    return failure();

  const int64_t rank = lhs.getRank();
  SmallVector<int64_t, 4> shape;

  // R1：batch 维（前 rank-2 维）取“已知一侧”。
  // 两侧都静态时 Verifier 规则 2 已保证相等，取谁都一样。
  for (int64_t i = 0; i < rank - 2; ++i) {
    int64_t l = lhs.getDimSize(i);
    shape.push_back(ShapedType::isDynamic(l) ? rhs.getDimSize(i) : l);
  }
  // R2：M 只看 lhs。R3：N 只看 rhs。? 原样传播，绝不发明数字。
  shape.push_back(lhs.getDimSize(rank - 2));
  shape.push_back(rhs.getDimSize(rank - 1));
  // R4：K 被消费，不进输出。
  return shape;
}

//===----------------------------------------------------------------------===//
// 2) 细化规则：old 与 inferred 逐维合并
//===----------------------------------------------------------------------===//

// 返回 nullopt 表示“推导值与已有静态维冲突”——这属于非法 IR，
// 但 Verifier 在 Pass 之前就该拦住，走到这里说明有人绕过了管线。
std::optional<SmallVector<int64_t, 4>>
refineShape(ArrayRef<int64_t> oldShape, ArrayRef<int64_t> inferred) {
  if (oldShape.size() != inferred.size())
    return std::nullopt;

  SmallVector<int64_t, 4> refined;
  for (auto [oldDim, newDim] : llvm::zip_equal(oldShape, inferred)) {
    if (ShapedType::isDynamic(oldDim)) {
      refined.push_back(newDim); // ? -> 数字，或 ? -> ?（保持不知道）
    } else if (!ShapedType::isDynamic(newDim) && oldDim != newDim) {
      return std::nullopt; // 数字对不上数字：结构性非法，交回诊断
    } else {
      refined.push_back(oldDim); // old 静态：用户的承诺优先，原样保留
    }
  }
  return refined;
}

//===----------------------------------------------------------------------===//
// 3) Pass 本体
//===----------------------------------------------------------------------===//

struct ShapeInferencePass
    : public PassWrapper<ShapeInferencePass, OperationPass<func::FuncOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(ShapeInferencePass)

  // --pass-statistics 会汇总：今天到底细化了几个结果类型。
  Pass::Statistic refinedResults{this, "refined-results",
                                 "Number of mini.matmul results refined"};

  void runOnOperation() override {
    func::FuncOp func = getOperation();

    // walk 默认 pre-order：SSA 直线代码里，定义先于使用被访问。
    // 链式 matmul（%1 = matmul(%0, ...)）一趟就能传播到底——
    // 访问第二个 matmul 时，%0 的类型已经细化过了。
    // 注意 ::mini:: 前缀：Passes.h 在 mlir::mini 里声明注册函数，
    // 加上开头的 using namespace mlir，裸写 mini:: 会同时命中
    // ::mini 和 mlir::mini 两个命名空间——day-044 交付的代码就
    // 栽在这一行（error: reference to 'mini' is ambiguous），
    // 今天开工前先补上这个修复。
    func->walk([&](::mini::MatmulOp op) {
      auto lhs = llvm::cast<RankedTensorType>(op.getLhs().getType());
      auto rhs = llvm::cast<RankedTensorType>(op.getRhs().getType());
      auto res = llvm::cast<RankedTensorType>(op.getRes().getType());

      FailureOr<SmallVector<int64_t, 4>> inferred = inferMatmulShape(lhs, rhs);
      if (failed(inferred))
        return; // R0 兜底：Verifier 已拦过的地方，Pass 不重复报错

      std::optional<SmallVector<int64_t, 4>> refined =
          refineShape(res.getShape(), *inferred);
      if (!refined) {
        op->emitOpError("shape inference conflicts with the statically known "
                        "result shape")
            << ": inferred " << *inferred << " but result type is " << res;
        return signalPassFailure();
      }

      // 一个 ? 都没细化：不碰 IR，避免“Pass 改了 IR”的假象
      // （完全静态的输入、或推导不出来的维度都会走到这里）。
      if (llvm::ArrayRef<int64_t>(*refined) == res.getShape())
        return;

      // 结果类型只改 shape，元素类型恒为 f32（ODS 保证，原样带过来）。
      // Value::setType 写的是值本身的类型：所有使用者看到同一个值，
      // 自动一起看到新类型——这正是“更新结果类型”的全部含义。
      op.getRes().setType(
          RankedTensorType::get(*refined, res.getElementType()));
      ++refinedResults;
    });
  }

  StringRef getArgument() const override { return "mini-infer-shape"; }
  StringRef getDescription() const override {
    return "Infer mini.matmul result shapes from operands; only refine "
           "dynamic dims, never overwrite static ones";
  }
};

} // namespace

namespace mlir {
namespace mini {

void registerShapeInferencePass() {
  registerPass([]() -> std::unique_ptr<Pass> {
    return std::make_unique<ShapeInferencePass>();
  });
}

} // namespace mini
} // namespace mlir
