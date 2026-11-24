// mini-fuse.cpp —— 第 51 天核心示例：Add + Relu -> FusedAddRelu 融合 Pattern
//
// 用法: ./mini-fuse <input.mlir> [--broken=erase-order|no-guard]
//   默认打印融合前后 IR 并跑完校验；
//   --broken 两个模式故意写错，用来复现今天的常见错误。

#include "MiniDialect.h"

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/IR/Verifier.h"
#include "mlir/Parser/Parser.h"
#include "mlir/Support/LLVM.h"
#include "mlir/Transforms/GreedyPatternRewriteDriver.h"
#include "llvm/Support/raw_ostream.h"

using namespace mlir;

namespace {

// ================== 今天的核心：融合 Pattern ==================
// 匹配的链式结构（producer -> consumer）：
//   %t = mini.add %lhs, %rhs
//   %r = mini.relu %t
// 整个区域替换成：
//   %f = mini.fused_add_relu %lhs, %rhs
// 并保证 %r 原来的所有使用者都拿到 %f。
struct FuseAddReluPattern : OpRewritePattern<mini::ReluOp> {
  using OpRewritePattern<mini::ReluOp>::OpRewritePattern;

  LogicalResult matchAndRewrite(mini::ReluOp relu,
                                PatternRewriter &rewriter) const override {
    // (1) 沿操作数回溯：Relu 的输入必须由 mini.add 定义，才是 Add -> Relu 链
    Value t = relu.getX();
    auto add = t.getDefiningOp<mini::AddOp>();
    if (!add)
      return failure();

    // (2) 合法性前提：中间结果 %t 只被这一个 Relu 使用。
    //     有多个使用者时直接删除 Add 会破坏别人的输入，处理策略留到第 52 天。
    if (!t.hasOneUse())
      return failure();

    // (3) 在被匹配的 Relu 之前创建融合算子；此刻新旧算子并存，图仍然合法
    rewriter.setInsertionPoint(relu);
    auto fused = rewriter.create<mini::FusedAddReluOp>(
        relu.getLoc(), t.getType(), add.getLhs(), add.getRhs());

    // (4) %r 的全部使用者改接 %f，然后先擦消费者 Relu、再擦生产者 Add
    rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
    rewriter.eraseOp(relu);
    rewriter.eraseOp(add);
    return success();
  }
};

// ================== 故意写错的版本（复现常见错误用） ==================
struct BrokenFuseAddReluPattern : OpRewritePattern<mini::ReluOp> {
  using OpRewritePattern<mini::ReluOp>::OpRewritePattern;
  std::string mode; // "erase-order"：擦除顺序错误；"no-guard"：缺少单使用者检查

  BrokenFuseAddReluPattern(MLIRContext *ctx, std::string mode)
      : OpRewritePattern<mini::ReluOp>(ctx), mode(std::move(mode)) {}

  LogicalResult matchAndRewrite(mini::ReluOp relu,
                                PatternRewriter &rewriter) const override {
    Value t = relu.getX();
    auto add = t.getDefiningOp<mini::AddOp>();
    if (!add)
      return failure();
    if (mode == "erase-order" && !t.hasOneUse())
      return failure();
    // mode == "no-guard"：不做单使用者检查，强行融合

    rewriter.setInsertionPoint(relu);
    auto fused = rewriter.create<mini::FusedAddReluOp>(
        relu.getLoc(), t.getType(), add.getLhs(), add.getRhs());

    if (mode == "erase-order") {
      // 错误顺序：Add 的结果 %t 仍被 Relu 使用，就先擦掉生产者
      rewriter.eraseOp(add);
      rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
      rewriter.eraseOp(relu);
    } else {
      // no-guard：正常顺序，但没有确认 %t 只有一个使用者
      rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
      rewriter.eraseOp(relu);
      rewriter.eraseOp(add);
    }
    return success();
  }
};

} // namespace

int main(int argc, char **argv) {
  if (argc < 2) {
    llvm::errs() << "用法: " << argv[0]
                 << " <input.mlir> [--broken=erase-order|no-guard]\n";
    return 1;
  }
  std::string inputPath = argv[1];
  std::string broken;
  for (int i = 2; i < argc; ++i) {
    llvm::StringRef arg = argv[i];
    if (arg.starts_with("--broken="))
      broken = arg.substr(strlen("--broken=")).str();
  }

  DialectRegistry registry;
  registry.insert<mini::MiniDialect, func::FuncDialect>();
  MLIRContext context;
  context.appendDialectRegistry(registry);
  context.loadAllAvailableDialects();

  OwningOpRef<ModuleOp> module = parseSourceFile<ModuleOp>(inputPath, &context);
  if (!module) {
    llvm::errs() << "解析失败: " << inputPath << "\n";
    return 1;
  }

  llvm::outs() << "===== 融合前 =====\n";
  module->print(llvm::outs());
  llvm::outs() << "\n";
  llvm::outs().flush(); // 立即落盘，即使后面崩溃也能看到崩溃前的 IR

  RewritePatternSet patterns(&context);
  if (broken == "erase-order" || broken == "no-guard")
    patterns.add<BrokenFuseAddReluPattern>(&context, broken);
  else
    patterns.add<FuseAddReluPattern>(&context);

  // 逐个函数应用 Pattern；驱动器会迭代匹配直到不动点（今天只有一种 Pattern）
  FrozenRewritePatternSet frozen(std::move(patterns));
  module->walk([&](func::FuncOp fn) {
    applyPatternsAndFoldGreedily(fn, frozen, GreedyRewriteConfig());
  });

  if (failed(verify(module.get()))) {
    llvm::errs() << "融合后 IR 校验失败\n";
    return 1;
  }

  llvm::outs() << "===== 融合后 =====\n";
  module->print(llvm::outs());
  llvm::outs() << "\n";
  return 0;
}
