// mini-fuse-bias.cpp —— 第 53 天核心示例：MatMul + Bias 融合 Pattern
//
// 用法: ./mini-fuse-bias <input.mlir> [--strategy=reject|keep]
//   --strategy=reject  默认。乘积 %m 多使用者时拒绝融合，图保持原样
//   --strategy=keep    融合分支、保留 mini.matmul 给其他使用者
//                      （合法，但整次 matmul 将重算——比 Day 52 重算加法贵得多）
//
// Pattern 匹配的链（§ 与教程图 3 的编号一致）：
//   %m = mini.matmul %a, %b            // 乘积：本 Pattern 的中间值
//   %s = mini.add     %m, %bias        // bias 在左右两侧都认
//   %r = mini.relu    %s               // 可选：%s 的唯一使用者时直接吸收
//
// 每次匹配都会向 stderr 打一行决策日志，明确「为什么融合 / 为什么不融合」。
// 输入 IR 先过一遍 verify 再进 Pattern：bias 形状非法的图根本轮不到融合。

#include "MiniDialect.h"
#include "MiniRules.h"

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/IR/Verifier.h"
#include "mlir/Parser/Parser.h"
#include "mlir/Support/LLVM.h"
#include "mlir/Transforms/GreedyPatternRewriteDriver.h"
#include "llvm/Support/raw_ostream.h"

#include <string>

using namespace mlir;

namespace {

// ================== 今天的核心：MatMul + Bias 融合 Pattern ==================
struct FuseMatmulBiasPattern : OpRewritePattern<mini::AddOp> {
  using OpRewritePattern<mini::AddOp>::OpRewritePattern;

  enum class Strategy { Reject, Keep };
  Strategy strategy;

  FuseMatmulBiasPattern(MLIRContext *ctx, Strategy strategy)
      : OpRewritePattern<mini::AddOp>(ctx), strategy(strategy) {}

  LogicalResult matchAndRewrite(mini::AddOp add,
                                PatternRewriter &rewriter) const override {
    // (1) 找乘积：先看 lhs，再看 rhs；两侧都是 matmul → 没有 bias 可言
    Value lhs = add.getLhs(), rhs = add.getRhs();
    auto lmm = lhs.getDefiningOp<mini::MatmulOp>();
    auto rmm = rhs.getDefiningOp<mini::MatmulOp>();
    if (lmm && rmm) {
      llvm::errs() << "  [reject] 匹配 Add：两侧都是 mini.matmul —— "
                     "分不清谁是 bias，拒绝融合\n";
      return failure();
    }
    mini::MatmulOp mm = lmm ? lmm : rmm;
    if (!mm)
      return failure();               // 没有链，安静返回（不是错误）
    Value bias = lmm ? rhs : lhs;      // 另一侧就是 bias，左右都认
    Value m = mm.getRes();             // 乘积 %m：本 Pattern 的中间值

    // (2) Bias Shape 三分类 —— 输入图已过 mini.add 的 Verifier，这里
    //     是第二道防线（规则与 Verifier 物理共享，MiniRules.h）
    mini::BiasKind kind = mini::classifyBias(bias.getType(), m.getType());
    if (kind != mini::BiasKind::Same) {
      llvm::errs() << "  [reject] 匹配 Add：bias 对乘积需要"
                   << (kind == mini::BiasKind::BroadcastOnly
                           ? "广播（第 60 天放行前 Pattern 不碰它）"
                           : "广播也对不上（shape 永久不匹配）")
                   << "，拒绝融合\n";
      return failure();
    }

    // (3) 乘积 %m 的使用者数量 —— 改写会改变它，必须先采样（Day 52 错误 3）
    bool singleUse = m.hasOneUse();
    unsigned numUses = std::distance(m.use_begin(), m.use_end());

    // (4) 可选 Relu：加法结果 %s 的唯一使用者是 mini.relu 时才能吸收；
    //     %s 还有别的使用者时吸收 = 把人家的 A·B+bias 换成 relu(A·B+bias)
    mini::ReluOp relu;
    if (add.getRes().hasOneUse())
      if (auto r = dyn_cast<mini::ReluOp>(*add.getRes().user_begin()))
        relu = r;

    if (!singleUse && strategy == Strategy::Reject) {
      llvm::errs() << "  [reject] 匹配 Add：乘积 %m 使用者 " << numUses
                   << " -> 拒绝融合（Day 52 规则原样适用），保留整条链\n";
      return failure();
    }

    // (5) 改写。结果类型跟 matmul 走（m.getType() = [M,N]）——
    //     不跟 bias、更不跟「第一个操作数」（lhs 是 [M,K]）。
    rewriter.setInsertionPoint(add);
    if (relu) {
      auto fused = rewriter.create<mini::FusedMatmulBiasReluOp>(
          add.getLoc(), m.getType(), mm.getLhs(), mm.getRhs(), bias);
      rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
      rewriter.eraseOp(relu);           // 先擦最上层消费者
      llvm::errs() << "  [fuse3] 匹配 MatMul + Add + Relu（乘积使用者 "
                   << numUses << "）-> fused_matmul_bias_relu，Relu 直接吸收\n";
      rewriter.replaceAllUsesWith(add.getResult(), fused.getResult());
      rewriter.eraseOp(add);
      finishProducer(rewriter, mm, singleUse, numUses);
      return success();
    }
    auto fused = rewriter.create<mini::FusedMatmulBiasOp>(
        add.getLoc(), m.getType(), mm.getLhs(), mm.getRhs(), bias);
    llvm::errs() << "  [fuse2] 匹配 MatMul + Add（乘积使用者 " << numUses
                << "）-> fused_matmul_bias\n";
    rewriter.replaceAllUsesWith(add.getResult(), fused.getResult());
    rewriter.eraseOp(add);
    finishProducer(rewriter, mm, singleUse, numUses);
    return success();
  }

private:
  // (6) 生产者 MatMul：乘积独占 → 一并删除；多使用者 + keep → 保留重算
  void finishProducer(PatternRewriter &rewriter, mini::MatmulOp mm,
                      bool singleUse, unsigned numUses) const {
    if (singleUse) {
      rewriter.eraseOp(mm);
      return;
    }
    llvm::errs() << "  [keep] 乘积还有 " << numUses
                 << " 个使用者，保留 mini.matmul —— "
                    "整次 matmul 将在融合算子里重算（2·M·N·K 次乘加，"
                    "比 Day 52 重算一次加法贵得多）\n";
  }
};

} // namespace

int main(int argc, char **argv) {
  if (argc < 2) {
    llvm::errs() << "用法: " << argv[0]
                 << " <input.mlir> [--strategy=reject|keep]\n";
    return 1;
  }
  std::string inputPath = argv[1];
  std::string strategy = "reject";
  for (int i = 2; i < argc; ++i) {
    llvm::StringRef arg = argv[i];
    if (arg.starts_with("--strategy="))
      strategy = arg.substr(strlen("--strategy=")).str();
  }

  FuseMatmulBiasPattern::Strategy strat =
      FuseMatmulBiasPattern::Strategy::Reject;
  if (strategy == "keep")
    strat = FuseMatmulBiasPattern::Strategy::Keep;
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
    // 注意：MLIR 的 parseSourceFile 在解析完成后会自动 verify 一遍，
    // 所以 bias 形状非法的图在这里就被拦下，报错来自我们的 Verifier。
    llvm::errs() << "解析/验证失败: " << inputPath << "\n";
    return 1;
  }

  // 融合前再显式过一遍 Verifier（第二道闸门，口径与 MiniRules.h 共享）
  if (failed(verify(module.get()))) {
    llvm::errs() << "输入 IR 未通过 verify —— 融合 Pattern 不接管非法图\n";
    return 1;
  }

  llvm::outs() << "===== 融合前 =====\n";
  module->print(llvm::outs());
  llvm::outs() << "\n";
  llvm::outs().flush(); // 立即落盘，即使后面出错也能看到出错前的 IR

  llvm::errs() << "决策日志（策略 = " << strategy << "）：\n";
  RewritePatternSet patterns(&context);
  patterns.add<FuseMatmulBiasPattern>(&context, strat);

  FrozenRewritePatternSet frozen(std::move(patterns));
  module->walk([&](func::FuncOp fn) {
    (void)applyPatternsAndFoldGreedily(fn, frozen, GreedyRewriteConfig());
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
