// mini-fuse3.cpp —— 第 54 天核心示例：三算子融合与 Pattern 优先级
//
// 用法: ./mini-fuse3 <input.mlir> [--set=NAME] [--top-down] [--max-rewrites=N]
//
//   --set=two-stage  P1(MatMul+Add, benefit 1) + P2(吸收 Relu, benefit 1)
//                    两阶段路线：先两算子、再吸收，靠「重复匹配」衔接
//   --set=direct     P3(直接三算子, benefit 2)：第 53 天的形态，一步到位
//   --set=all        P1 + P2 + P3：同 root(mini.add) 上 benefit 高的先出手
//   --set=steal      P51(Add+Relu, 第 51 天) + P3：抢跑事故——不同 root，
//                    benefit 管不到先后，访问顺序决定最终形态
//   --set=guarded    P51g(让位版) + P3：add 的操作数是乘积就收手
//   --set=pipeline   先 {P3} 一个贪心轮，再 {P51} 一个贪心轮（管道顺序修法）
//   --set=oscillate  P1 + P2 + Unfuse(benefit 3)：P2 与 Unfuse 互为逆变换，
//                    先融起来再拉锯，永不收敛（配 --max-rewrites=N 护栏
//                    演示止损）
//   --top-down       GreedyRewriteConfig::useTopDownTraversal = true
//                    （默认 false = 自底向上遍历；只改变访问顺序）
//   --max-rewrites=N GreedyRewriteConfig::maxNumRewrites = N（本轮改写上限）
//
// 每次匹配向 stderr 打一行决策日志：谁出手、为什么不出手，看得见。

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

// ============ 共用：在 add 两侧找「乘积 / bias」＝第 53 天的判定 ============

static bool findMatmulPair(mini::AddOp add, mini::MatmulOp &mmOut,
                           Value &biasOut) {
  Value lhs = add.getLhs(), rhs = add.getRhs();
  auto lmm = lhs.getDefiningOp<mini::MatmulOp>();
  auto rmm = rhs.getDefiningOp<mini::MatmulOp>();
  if (lmm && rmm) {
    llvm::errs() << "  [拒绝] 匹配 Add：两侧都是 mini.matmul —— "
                    "分不清谁是 bias，拒绝融合\n";
    return false;
  }
  mini::MatmulOp mm = lmm ? lmm : rmm;
  if (!mm)
    return false;                        // 没有链，安静返回（不是错误）
  mmOut = mm;
  biasOut = lmm ? rhs : lhs;             // 另一侧就是 bias，左右都认
  return true;
}

// ============ P1 两阶段·第一步：MatMul + Add -> fused_matmul_bias ============

struct FuseMatmulBiasTwoStagePattern : OpRewritePattern<mini::AddOp> {
  // benefit 默认 1：吃掉 2 个算子的融合。
  FuseMatmulBiasTwoStagePattern(MLIRContext *ctx, PatternBenefit benefit = 1)
      : OpRewritePattern<mini::AddOp>(ctx, benefit) {}

  LogicalResult matchAndRewrite(mini::AddOp add,
                                PatternRewriter &rewriter) const override {
    mini::MatmulOp mm;
    Value bias;
    if (!findMatmulPair(add, mm, bias))
      return failure();
    Value m = mm.getRes();
    if (mini::classifyBias(bias.getType(), m.getType()) != mini::BiasKind::Same)
      return failure();                  // Verifier 已拦过，第二道防线
    unsigned numUses = std::distance(m.use_begin(), m.use_end());
    if (numUses != 1) {
      llvm::errs() << "  [P1] 匹配 Add：乘积使用者 " << numUses
                   << " -> 拒绝（Day 52 规则），保留整条链\n";
      return failure();
    }
    // 改写：结果类型跟 matmul 走（m.getType() = [M,N]，Day 53 的结论）
    rewriter.setInsertionPoint(add);
    auto fused = rewriter.create<mini::FusedMatmulBiasOp>(
        add.getLoc(), m.getType(), mm.getLhs(), mm.getRhs(), bias);
    rewriter.replaceAllUsesWith(add.getResult(), fused.getResult());
    rewriter.eraseOp(add);
    rewriter.eraseOp(mm);                // 乘积独占 -> 生产者一并删除
    llvm::errs() << "  [P1] 匹配 MatMul + Add -> fused_matmul_bias"
                    "（两阶段·第一步，Relu 原地不动）\n";
    return success();
  }
};

// ============ P2 两阶段·第二步：Relu(fused_matmul_bias) -> fused_mm_bias_relu ============

struct AbsorbReluEpiloguePattern : OpRewritePattern<mini::ReluOp> {
  // benefit 默认 1。锚在 mini.relu（消费者）上。
  AbsorbReluEpiloguePattern(MLIRContext *ctx, PatternBenefit benefit = 1)
      : OpRewritePattern<mini::ReluOp>(ctx, benefit) {}

  LogicalResult matchAndRewrite(mini::ReluOp relu,
                                PatternRewriter &rewriter) const override {
    Value x = relu.getX();
    auto fm = x.getDefiningOp<mini::FusedMatmulBiasOp>();
    if (!fm) {
      // 不匹配也打一行：同一个 relu 被访问两次（先不匹配、后吸收）
      // 就写在日志里——重复匹配看得见。
      Operation *def = x.getDefiningOp();
      llvm::errs() << "  [P2] 访问 Relu：操作数由 "
                   << (def ? def->getName().getStringRef() : "图输入")
                   << " 定义 -> 不匹配\n";
      return failure();
    }
    unsigned numUses = std::distance(x.use_begin(), x.use_end());
    if (numUses != 1) {
      llvm::errs() << "  [P2] 融合结果有 " << numUses
                   << " 个使用者 -> 不能吸收 Relu（Day 53 场景 E 的规则）\n";
      return failure();
    }
    rewriter.setInsertionPoint(fm);
    auto fused = rewriter.create<mini::FusedMatmulBiasReluOp>(
        relu.getLoc(), x.getType(), fm.getLhs(), fm.getRhs(), fm.getBias());
    rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
    rewriter.eraseOp(relu);              // 先擦消费者
    rewriter.eraseOp(fm);                // 再擦生产者（结果已无人用）
    llvm::errs() << "  [P2] fused_matmul_bias + relu -> fused_matmul_bias_relu"
                    "（两阶段·第二步，epilogue 吸收）\n";
    return success();
  }
};

// ============ P3 直接三算子：MatMul + Add (+Relu) -> fused_mm_bias(_relu) ============

struct FuseMatmulBiasReluDirectPattern : OpRewritePattern<mini::AddOp> {
  // benefit = 2：一次匹配吃掉 3 个算子（0~65535 的无量纲值，官方建议的
  // 量纲是「匹配的算子数」）。同一 root(mini.add) 上压过 P1。
  FuseMatmulBiasReluDirectPattern(MLIRContext *ctx, PatternBenefit benefit = 2)
      : OpRewritePattern<mini::AddOp>(ctx, benefit) {}

  LogicalResult matchAndRewrite(mini::AddOp add,
                                PatternRewriter &rewriter) const override {
    mini::MatmulOp mm;
    Value bias;
    if (!findMatmulPair(add, mm, bias))
      return failure();
    Value m = mm.getRes();
    if (mini::classifyBias(bias.getType(), m.getType()) != mini::BiasKind::Same)
      return failure();
    unsigned numUses = std::distance(m.use_begin(), m.use_end());
    if (numUses != 1) {
      llvm::errs() << "  [P3] 匹配 Add：乘积使用者 " << numUses
                   << " -> 拒绝（Day 52 规则），保留整条链\n";
      return failure();
    }
    // 可选 Relu：加法结果 %s 的唯一使用者是 mini.relu 时才吸收
    mini::ReluOp relu;
    if (add.getRes().hasOneUse())
      if (auto r = dyn_cast<mini::ReluOp>(*add.getRes().user_begin()))
        relu = r;

    rewriter.setInsertionPoint(add);
    if (relu) {
      auto fused = rewriter.create<mini::FusedMatmulBiasReluOp>(
          add.getLoc(), m.getType(), mm.getLhs(), mm.getRhs(), bias);
      rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
      rewriter.eraseOp(relu);
      rewriter.eraseOp(add);
      rewriter.eraseOp(mm);
      llvm::errs() << "  [P3] 匹配 MatMul + Add + Relu -> "
                      "fused_matmul_bias_relu（直接三算子，一步到位）\n";
      return success();
    }
    auto fused = rewriter.create<mini::FusedMatmulBiasOp>(
        add.getLoc(), m.getType(), mm.getLhs(), mm.getRhs(), bias);
    rewriter.replaceAllUsesWith(add.getResult(), fused.getResult());
    rewriter.eraseOp(add);
    rewriter.eraseOp(mm);
    llvm::errs() << "  [P3] 匹配 MatMul + Add -> fused_matmul_bias"
                    "（直接两算子，%s 还有别的使用者时不吸收 Relu）\n";
    return success();
  }
};

// ============ P51 / P51g：第 51 天的 Add + Relu -> fused_add_relu ============

struct FuseAddReluPattern : OpRewritePattern<mini::ReluOp> {
  bool guardMatmul;                      // true = 让位版 P51g

  FuseAddReluPattern(MLIRContext *ctx, bool guardMatmul,
                     PatternBenefit benefit = 1)
      : OpRewritePattern<mini::ReluOp>(ctx, benefit),
        guardMatmul(guardMatmul) {}

  LogicalResult matchAndRewrite(mini::ReluOp relu,
                                PatternRewriter &rewriter) const override {
    Value x = relu.getX();
    auto ad = x.getDefiningOp<mini::AddOp>();
    if (!ad || !x.hasOneUse())
      return failure();                  // 没有链 / 加法结果多使用者
    if (guardMatmul) {
      // 让位规则：add 的操作数里有 matmul 乘积 -> 大融合的原料，不抢
      bool hasMatmulOperand =
          ad->getOperand(0).getDefiningOp<mini::MatmulOp>() ||
          ad->getOperand(1).getDefiningOp<mini::MatmulOp>();
      if (hasMatmulOperand) {
        llvm::errs() << "  [P51g] add 的操作数之一是 matmul 乘积 -> "
                        "让位给更大的融合（MatMul+Bias 系），本次不抢\n";
        return failure();
      }
    }
    rewriter.setInsertionPoint(ad);
    auto fused = rewriter.create<mini::FusedAddReluOp>(
        relu.getLoc(), x.getType(), ad.getLhs(), ad.getRhs());
    rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
    rewriter.eraseOp(relu);
    rewriter.eraseOp(ad);
    llvm::errs() << "  [" << (guardMatmul ? "P51g" : "P51")
                 << "] 匹配 Add + Relu -> fused_add_relu（Add+Relu 小融合）\n";
    return success();
  }
};

// ============ 反面教材：fused_matmul_bias_relu -> fused_mm_bias + relu ============

struct UnfuseMatmulBiasReluPattern
    : OpRewritePattern<mini::FusedMatmulBiasReluOp> {
  // benefit = 3：压过 P2 —— 只为演示「谁都能抢到」改变不了不收敛的结局
  UnfuseMatmulBiasReluPattern(MLIRContext *ctx, PatternBenefit benefit = 3)
      : OpRewritePattern<mini::FusedMatmulBiasReluOp>(ctx, benefit) {}

  LogicalResult matchAndRewrite(mini::FusedMatmulBiasReluOp f,
                                PatternRewriter &rewriter) const override {
    rewriter.setInsertionPoint(f);
    auto m = rewriter.create<mini::FusedMatmulBiasOp>(
        f.getLoc(), f.getRes().getType(), f.getLhs(), f.getRhs(), f.getBias());
    auto r = rewriter.create<mini::ReluOp>(f.getLoc(), m.getRes().getType(),
                                           m.getRes());
    rewriter.replaceAllUsesWith(f.getRes(), r.getResult());
    rewriter.eraseOp(f);
    llvm::errs() << "  [Unfuse] fused_matmul_bias_relu 拆回 "
                    "fused_matmul_bias + relu（语义不变，P2 会再融回去……）\n";
    return success();
  }
};

} // namespace

// ============================ main：装配 Pattern 集 ============================

int main(int argc, char **argv) {
  if (argc < 2) {
    llvm::errs() << "用法: " << argv[0] << " <input.mlir> "
                 << "[--set=two-stage|direct|all|steal|guarded|pipeline|"
                    "oscillate] [--top-down] [--max-rewrites=N]\n";
    return 1;
  }
  std::string inputPath = argv[1];
  std::string set = "two-stage";
  bool topDown = false;
  std::optional<int64_t> maxRewrites;
  for (int i = 2; i < argc; ++i) {
    llvm::StringRef arg = argv[i];
    if (arg.starts_with("--set="))
      set = arg.substr(strlen("--set=")).str();
    else if (arg == "--top-down")
      topDown = true;
    else if (arg.starts_with("--max-rewrites="))
      maxRewrites = std::stoll(arg.substr(strlen("--max-rewrites=")).str());
  }

  DialectRegistry registry;
  registry.insert<mini::MiniDialect, func::FuncDialect>();
  MLIRContext context;
  context.appendDialectRegistry(registry);
  context.loadAllAvailableDialects();

  OwningOpRef<ModuleOp> module = parseSourceFile<ModuleOp>(inputPath, &context);
  if (!module) {
    llvm::errs() << "解析/验证失败: " << inputPath << "\n";
    return 1;
  }
  if (failed(verify(module.get()))) {
    llvm::errs() << "输入 IR 未通过 verify —— 融合 Pattern 不接管非法图\n";
    return 1;
  }

  llvm::outs() << "===== 融合前 =====\n";
  module->print(llvm::outs());
  llvm::outs() << "\n";
  llvm::outs().flush();

  // 装配 Pattern 集（每个集都打印 benefit，方便对照日志）
  auto makeSet = [&](const std::string &name, RewritePatternSet &patterns) {
    if (name == "two-stage") {
      patterns.add<FuseMatmulBiasTwoStagePattern>(&context, 1);
      patterns.add<AbsorbReluEpiloguePattern>(&context, 1);
      llvm::errs() << "Pattern 集: P1 FuseMatmulBias(benefit 1, root add) + "
                      "P2 AbsorbRelu(benefit 1, root relu)\n";
    } else if (name == "direct") {
      patterns.add<FuseMatmulBiasReluDirectPattern>(&context, 2);
      llvm::errs() << "Pattern 集: P3 FuseMatmulBiasRelu(benefit 2, root add)\n";
    } else if (name == "all") {
      patterns.add<FuseMatmulBiasTwoStagePattern>(&context, 1);
      patterns.add<AbsorbReluEpiloguePattern>(&context, 1);
      patterns.add<FuseMatmulBiasReluDirectPattern>(&context, 2);
      llvm::errs() << "Pattern 集: P1(benefit 1) + P2(benefit 1) + "
                      "P3(benefit 2)——同 root(add) 上 P3 领先\n";
    } else if (name == "steal") {
      patterns.add<FuseAddReluPattern>(&context, /*guardMatmul=*/false, 1);
      patterns.add<FuseMatmulBiasReluDirectPattern>(&context, 2);
      llvm::errs() << "Pattern 集: P51 FuseAddRelu(benefit 1, root relu) + "
                      "P3(benefit 2, root add)——root 不同，benefit 管不到先后\n";
    } else if (name == "guarded") {
      patterns.add<FuseAddReluPattern>(&context, /*guardMatmul=*/true, 1);
      patterns.add<FuseMatmulBiasReluDirectPattern>(&context, 2);
      llvm::errs() << "Pattern 集: P51g FuseAddRelu(让位版, benefit 1, root "
                      "relu) + P3(benefit 2, root add)\n";
    } else if (name == "oscillate") {
      // 注意必须有 P1 把图先融起来，Unfuse/P2 的拉锯才会开始；
      // benefit 3 的 Unfuse 在同 root 上没有对手——它赢的是「别的 root
      // 造出来的东西被它拆掉」，benefit 根本管不到这种跨 root 打架。
      patterns.add<FuseMatmulBiasTwoStagePattern>(&context, 1);
      patterns.add<AbsorbReluEpiloguePattern>(&context, 1);
      patterns.add<UnfuseMatmulBiasReluPattern>(&context, 3);
      llvm::errs() << "Pattern 集: P1(benefit 1) + P2(benefit 1) + "
                      "Unfuse(benefit 3)——P2 与 Unfuse 互为逆变换，"
                      "先融起来再拉锯，不会收敛\n";
    } else {
      llvm::errs() << "未知 Pattern 集: " << name << "\n";
      return false;
    }
    return true;
  };

  auto configOf = [&]() {
    GreedyRewriteConfig config;
    config.useTopDownTraversal = topDown;
    if (maxRewrites)
      config.maxNumRewrites = *maxRewrites;
    return config;
  };

  auto runGreedy = [&](RewritePatternSet &&patterns, const char *phase) {
    FrozenRewritePatternSet frozen(std::move(patterns));
    llvm::errs() << "决策日志（" << phase
                 << "，遍历 = " << (topDown ? "top-down" : "bottom-up")
                 << (maxRewrites
                         ? "，本轮改写上限 = " + std::to_string(*maxRewrites)
                         : "")
                 << "）：\n";
    bool converged = true;
    module->walk([&](func::FuncOp fn) {
      LogicalResult r = applyPatternsAndFoldGreedily(fn, frozen, configOf());
      if (failed(r))
        converged = false;
    });
    if (!converged) {
      llvm::errs() << "!! 驱动未收敛：Pattern 互相打架，超过迭代/改写上限"
                      "（护栏止损，见教程错误 4）\n";
      return false;
    }
    return true;
  };

  bool ok;
  if (set == "pipeline") {
    // 修法二：Pass 管道顺序——大融合的 Pass 先跑，小融合的 Pass 收尾。
    // 两个独立的贪心轮次，先后是显式契约，不依赖驱动内部顺序。
    llvm::errs() << "Pattern 管道: 第 1 轮 {P3}，第 2 轮 {P51}\n";
    RewritePatternSet phase1(&context);
    phase1.add<FuseMatmulBiasReluDirectPattern>(&context, 2);
    RewritePatternSet phase2(&context);
    phase2.add<FuseAddReluPattern>(&context, /*guardMatmul=*/false, 1);
    bool c1 = runGreedy(std::move(phase1), "第 1 轮 {P3}");
    bool c2 = runGreedy(std::move(phase2), "第 2 轮 {P51}");
    ok = c1 && c2;
  } else {
    RewritePatternSet patterns(&context);
    if (!makeSet(set, patterns)) {
      return 1;
    }
    ok = runGreedy(std::move(patterns), "贪心驱动");
  }

  if (failed(verify(module.get()))) {
    llvm::errs() << "融合后 IR 校验失败\n";
    return 1;
  }
  llvm::errs() << "verify: 通过（注意：这只代表结构合法，不代表语义没变）\n";

  llvm::outs() << "===== 融合后 =====\n";
  module->print(llvm::outs());
  llvm::outs() << "\n";
  return ok ? 0 : 2;
}
