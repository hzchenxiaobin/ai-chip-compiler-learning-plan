// mini-fuse-multi.cpp —— 第 52 天核心示例：多使用者中间结果的处理策略
//
// 用法: ./mini-fuse-multi <input.mlir> [--strategy=reject|keep] [--broken=rewire]
//   --strategy=reject  默认。中间结果多使用者时拒绝融合，图保持原样
//   --strategy=keep    融合 Relu 分支、保留 mini.add 给其他使用者（合法，Add 被算 2 次）
//   --broken=rewire    错误示范：把 %t 的其他使用者改接到融合结果
//                      —— 图结构合法、verify 通过，但语义悄悄改变
//
// 每次匹配都会向 stderr 打一行决策日志，明确「为什么融合 / 为什么不融合」。

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

#include <cstring>
#include <string>

using namespace mlir;

namespace {

// ================== 今天的核心：带策略的融合 Pattern ==================
// 匹配的链式结构（producer -> consumer）：
//   %t = mini.add %lhs, %rhs
//   %r = mini.relu %t          // %t 可能还有其他使用者！
struct FuseAddReluMultiPattern : OpRewritePattern<mini::ReluOp> {
  using OpRewritePattern<mini::ReluOp>::OpRewritePattern;

  enum class Strategy { Reject, Keep };  // 保守拒绝 / 融合但保留中间节点
  Strategy strategy;
  bool brokenRewire;                     // 错误示范：改接 %t 的其他使用者

  FuseAddReluMultiPattern(MLIRContext *ctx, Strategy strategy, bool broken)
      : OpRewritePattern<mini::ReluOp>(ctx), strategy(strategy),
        brokenRewire(broken) {}

  LogicalResult matchAndRewrite(mini::ReluOp relu,
                                PatternRewriter &rewriter) const override {
    // (1) 沿操作数回溯：Relu 的输入必须由 mini.add 定义
    Value t = relu.getX();
    auto add = t.getDefiningOp<mini::AddOp>();
    if (!add)
      return failure();

    // (2) 记录使用者数量 —— 后面的改写会改变它，必须先存下来
    bool singleUse = t.hasOneUse();
    unsigned numUses = std::distance(t.use_begin(), t.use_end());

    if (brokenRewire && !singleUse) {
      // 错误示范：把 %t 的其他使用者改接到融合结果。
      // 每一步改写本身都合法（verify 能通过），但 %t 的语义是 add(a+b)，
      // 改接之后其他使用者拿到的是 relu(a+b) —— 语义悄悄改变。
      llvm::errs() << "  [broken=rewire] 匹配 Relu(%t)：使用者 " << numUses
                   << " -> 强行融合并改接 %t 的其他使用者（语义错误！）\n";
      rewriter.setInsertionPoint(relu);
      auto fused = rewriter.create<mini::FusedAddReluOp>(
          relu.getLoc(), t.getType(), add.getLhs(), add.getRhs());
      rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
      rewriter.eraseOp(relu);
      rewriter.replaceAllUsesWith(t, fused.getResult());
      rewriter.eraseOp(add);
      return success();
    }

    // (3) 默认策略：多使用者时拒绝融合，图保持原样（失败必须无副作用）
    if (!singleUse && strategy == Strategy::Reject) {
      llvm::errs() << "  [reject] 匹配 Relu(%t)：使用者 " << numUses
                   << " -> 拒绝融合，保留 mini.add 和 mini.relu\n";
      return failure();
    }

    // (4) 创建融合算子，改接 %r 的全部使用者，先擦消费者 Relu
    rewriter.setInsertionPoint(relu);
    auto fused = rewriter.create<mini::FusedAddReluOp>(
        relu.getLoc(), t.getType(), add.getLhs(), add.getRhs());
    rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
    rewriter.eraseOp(relu);

    // (5) 生产者 Add：单使用者 -> 一并删除（第 51 天的原样行为）
    //     多使用者 + keep -> 保留，%t 继续喂给其他使用者
    if (singleUse) {
      rewriter.eraseOp(add);
      llvm::errs() << "  [fuse] 匹配 Relu(%t)：使用者 1 -> 融合，删除 mini.add\n";
    } else {
      llvm::errs() << "  [keep] 匹配 Relu(%t)：使用者 " << numUses
                   << " -> 融合 Relu 分支，保留 mini.add（加法将执行 2 次）\n";
    }
    return success();
  }
};

} // namespace

int main(int argc, char **argv) {
  if (argc < 2) {
    llvm::errs() << "用法: " << argv[0]
                 << " <input.mlir> [--strategy=reject|keep] [--broken=rewire]\n";
    return 1;
  }
  std::string inputPath = argv[1];
  std::string strategy = "reject";
  bool brokenRewire = false;
  for (int i = 2; i < argc; ++i) {
    llvm::StringRef arg = argv[i];
    if (arg.starts_with("--strategy="))
      strategy = arg.substr(strlen("--strategy=")).str();
    if (arg == "--broken=rewire")
      brokenRewire = true;
  }

  FuseAddReluMultiPattern::Strategy strat =
      FuseAddReluMultiPattern::Strategy::Reject;
  if (strategy == "keep")
    strat = FuseAddReluMultiPattern::Strategy::Keep;
  else if (strategy != "reject") {
    llvm::errs() << "未知策略: " << strategy << "（可选 reject / keep）\n";
    return 1;
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
  llvm::outs().flush(); // 立即落盘，即使后面出错也能看到出错前的 IR

  llvm::errs() << "决策日志（策略 = "
               << (brokenRewire ? "broken=rewire" : strategy) << "）：\n";
  RewritePatternSet patterns(&context);
  patterns.add<FuseAddReluMultiPattern>(&context, strat, brokenRewire);

  FrozenRewritePatternSet frozen(std::move(patterns));
  module->walk([&](func::FuncOp fn) {
    applyPatternsAndFoldGreedily(fn, frozen, GreedyRewriteConfig());
  });

  if (failed(verify(module.get()))) {
    llvm::errs() << "融合后 IR 校验失败\n";
    return 1;
  }
  llvm::errs() << "verify: 通过（注意：这只代表结构合法，不代表语义没变）\n";

  llvm::outs() << "===== 融合后 =====\n";
  module->print(llvm::outs());
  llvm::outs() << "\n";
  return 0;
}
