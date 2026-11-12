//===- CountOpsPass.cpp - 第一个自定义 Pass -------------------*- C++ -*-===//
//
// mini-count-ops：遍历一个 func.func，按操作名统计数量，
// 用 remark 把结果挂在函数上，用 PassStatistic 汇总总操作数。
//
// 它是"只读分析 Pass"的最小样本：
//   * 不改任何 IR（runOnOperation 里没有 rewriter）；
//   * 不依赖失效管理（没有 getDependentDialects 之外的并发问题）；
//   * 但走的是和 CSE 完全相同的注册、调度和统计通道。
// 后面的 Shape 推导（Day 43）先按这个骨架写"只读"版本，
// 到 Day 45 的 RewritePattern 才引入真正改图的机制。
//
//===----------------------------------------------------------------------===//

#include "mini/Passes.h"

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/Operation.h"
#include "mlir/Pass/Pass.h"
#include "llvm/ADT/STLExtras.h"
#include "llvm/ADT/StringMap.h"
#include "llvm/Support/Debug.h"

using namespace mlir;

namespace {

struct CountOpsPass
    : public PassWrapper<CountOpsPass, OperationPass<func::FuncOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(CountOpsPass)

  // PassStatistic：--pass-statistics 打开的汇总表会用到。
  Pass::Statistic totalOps{this, "total-ops",
                           "Total number of operations (incl. func.return)"};

  void runOnOperation() override {
    func::FuncOp func = getOperation();

    // walk 按定义序访问函数内所有 Operation（含嵌套）。
    llvm::StringMap<unsigned> counts;
    unsigned total = 0;
    func->walk([&](Operation *op) {
      ++counts[op->getName().getStringRef()];
      ++total;
    });

    // 按名字排序，保证每次运行输出一致（StringMap 本身无序）。
    SmallVector<llvm::StringRef, 8> names;
    for (auto &kv : counts)
      names.push_back(kv.getKey());
    llvm::sort(names);

    std::string detail;
    for (auto name : names) {
      if (!detail.empty())
        detail += ", ";
      detail += (name + "=" + Twine(counts[name])).str();
    }

    // remark 挂在函数 Operation 上：带位置、可定位。
    func->emitRemark()
        << total << " ops in @" << func.getSymName() << " (" << detail << ")";
    totalOps = total;
  }

  // 命令行名字和描述：registerPass 靠这两个函数登记选项。
  StringRef getArgument() const override { return "mini-count-ops"; }
  StringRef getDescription() const override {
    return "Count operations per function and report via remark";
  }
};

} // namespace

namespace mlir {
namespace mini {

void registerCountOpsPass() {
  // 注册的是"名字 -> 构造函数"的映射：命令行解析到 -mini-count-ops 时
  // 才真正构造 Pass 实例，不跑就不付出构造代价。
  registerPass([]() -> std::unique_ptr<Pass> {
    return std::make_unique<CountOpsPass>();
  });
}

} // namespace mini
} // namespace mlir
