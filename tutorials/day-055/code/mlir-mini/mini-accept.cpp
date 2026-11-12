// mini-accept.cpp —— 第 55 天核心示例：融合负例总验收（MLIR 层）
//
// 用法: ./mini-accept <input.mlir> --expect=fused|identity|verifier_reject
//
// 验收管道 = 第 54 天收敛出的「最终形态」Pattern 集（P1/P2/P51g/P3 让位版），
// 外加第 55 天补上的类型闸门（fused* 的语义只对 f32 验证过）：
//
//   P3  (benefit 2, root add)   直接三算子：MatMul + Add (+Relu)
//   P1  (benefit 1, root add)   两阶段第一步：MatMul + Add
//   P2  (benefit 1, root relu)  两阶段第二步：吸收 Relu（epilogue）
//   P51g (benefit 1, root relu) Add + Relu 小融合（让位版：add 的操作数
//                               是乘积就收手，不跟大融合抢）
//
// 三条验收规则（与 Python 层 mini_fuse_accept.py 逐条对齐）：
//   R1 正例：bottom-up / top-down 两种遍历必须收敛到同一最终形态
//          （Day 54 的教训：verify 通过 ≠ 融对了，遍历顺序不能决定结果）
//   R2 负例：拒绝必须是恒等变换——融合后 IR 与输入逐字一致、无副作用
//   （R3 数值对账在 Python 层做：MLIR 壳没有解释器，不伪造运行数据）
//   闸门一：parse + verify 失败即判决 verifier_reject（Shape / f64 负例）
//
// 判决与退出码：
//   verdict = fused | identity | verifier_reject（打印在 stdout 末行）
//   accept=PASS 且 rc=0：期望判决吻合、R1/R2 相应检查全部通过

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
#include <vector>

using namespace mlir;

namespace {

// ============ 类型闸门（第 55 天新增）：fused* 语义只对 f32 验证过 ============

static bool allF32(ArrayRef<Value> vals) {
  for (Value v : vals) {
    auto t = v.getType().dyn_cast<RankedTensorType>();
    if (!t || !t.getElementType().isF32())
      return false;
  }
  return true;
}

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
    if (!allF32({mm.getLhs(), mm.getRhs(), bias})) {
      llvm::errs() << "  [P1] 类型边界：元素类型非全 f32 -> 拒绝"
                     "（融合语义只对 f32 验证过）\n";
      return failure();
    }
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
  AbsorbReluEpiloguePattern(MLIRContext *ctx, PatternBenefit benefit = 1)
      : OpRewritePattern<mini::ReluOp>(ctx, benefit) {}

  LogicalResult matchAndRewrite(mini::ReluOp relu,
                                 PatternRewriter &rewriter) const override {
    Value x = relu.getX();
    auto fm = x.getDefiningOp<mini::FusedMatmulBiasOp>();
    if (!fm) {
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

// ============ P51g：让位版 Add + Relu -> fused_add_relu ============

struct FuseAddReluGuardedPattern : OpRewritePattern<mini::ReluOp> {
  FuseAddReluGuardedPattern(MLIRContext *ctx, PatternBenefit benefit = 1)
      : OpRewritePattern<mini::ReluOp>(ctx, benefit) {}

  LogicalResult matchAndRewrite(mini::ReluOp relu,
                                 PatternRewriter &rewriter) const override {
    Value x = relu.getX();
    auto ad = x.getDefiningOp<mini::AddOp>();
    if (!ad || !x.hasOneUse())
      return failure();                  // 没有链 / 加法结果多使用者
    // 让位规则：add 的操作数里有 matmul 乘积 -> 大融合的原料，不抢
    bool hasMatmulOperand =
        ad->getOperand(0).getDefiningOp<mini::MatmulOp>() ||
        ad->getOperand(1).getDefiningOp<mini::MatmulOp>();
    if (hasMatmulOperand) {
      llvm::errs() << "  [P51g] add 的操作数之一是 matmul 乘积 -> "
                      "让位给更大的融合（MatMul+Bias 系），本次不抢\n";
      return failure();
    }
    if (!allF32({ad.getLhs(), ad.getRhs()})) {
      llvm::errs() << "  [P51g] 类型边界：元素类型非 f32 -> 拒绝"
                     "（fused_add_relu 的语义只对 f32 验证过）\n";
      return failure();
    }
    rewriter.setInsertionPoint(ad);
    auto fused = rewriter.create<mini::FusedAddReluOp>(
        relu.getLoc(), x.getType(), ad.getLhs(), ad.getRhs());
    rewriter.replaceAllUsesWith(relu.getResult(), fused.getResult());
    rewriter.eraseOp(relu);
    rewriter.eraseOp(ad);
    llvm::errs() << "  [P51g] 匹配 Add + Relu -> fused_add_relu"
                    "（Add+Relu 小融合）\n";
    return success();
  }
};

// ============ P3 直接三算子：MatMul + Add (+Relu) -> fused_mm_bias(_relu) ============

struct FuseMatmulBiasReluDirectPattern : OpRewritePattern<mini::AddOp> {
  // benefit = 2：一次匹配吃掉 3 个算子，同一 root(mini.add) 上压过 P1
  FuseMatmulBiasReluDirectPattern(MLIRContext *ctx, PatternBenefit benefit = 2)
      : OpRewritePattern<mini::AddOp>(ctx, benefit) {}

  LogicalResult matchAndRewrite(mini::AddOp add,
                                 PatternRewriter &rewriter) const override {
    mini::MatmulOp mm;
    Value bias;
    if (!findMatmulPair(add, mm, bias))
      return failure();
    Value m = mm.getRes();
    if (mini::classifyBias(bias.getType(), m.getType()) != mini::BiasKind::Same) {
      llvm::errs() << "  [P3] bias 形状非 Same -> 拒绝"
                     "（第二道防线，Verifier 已拦过）\n";
      return failure();
    }
    if (!allF32({mm.getLhs(), mm.getRhs(), bias})) {
      llvm::errs() << "  [P3] 类型边界：元素类型非全 f32 -> 拒绝"
                     "（融合语义只对 f32 验证过）\n";
      return failure();
    }
    unsigned numUses = std::distance(m.use_begin(), m.use_end());
    if (numUses != 1) {
      llvm::errs() << "  [P3] 匹配 Add：乘积使用者 " << numUses
                   << " -> 拒绝（Day 52 规则），保留整条链\n";
      return failure();
    }
    // 可选 Relu：加法结果的唯一使用者是 mini.relu 时才吸收
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
                    "（%s 还有别的使用者时不吸收 Relu）\n";
    return success();
  }
};

} // namespace

// ============ 验收辅助：收集 mini.* 算子名单（程序序） ============

static std::vector<std::string> collectOpNames(ModuleOp module) {
  std::vector<std::string> names;
  module->walk<WalkOrder::PreOrder>([&](Operation *op) {
    llvm::StringRef name = op->getName().getStringRef();
    if (name.startswith("mini."))
      names.push_back(name.str());
  });
  return names;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    llvm::errs() << "用法: " << argv[0]
                << " <input.mlir> [--expect=fused|identity|verifier_reject]\n";
    return 1;
  }
  std::string inputPath = argv[1];
  std::string expect;                    // 空 = 只报告判决，不比对
  for (int i = 2; i < argc; ++i) {
    llvm::StringRef arg = argv[i];
    if (arg.starts_with("--expect="))
      expect = arg.substr(strlen("--expect=")).str();
  }

  DialectRegistry registry;
  registry.insert<mini::MiniDialect, func::FuncDialect>();
  MLIRContext context;
  context.appendDialectRegistry(registry);
  context.loadAllAvailableDialects();

  // ---------- 闸门一：parse + verify（Shape / f64 负例在这层拦下） ----------
  OwningOpRef<ModuleOp> modA = parseSourceFile<ModuleOp>(inputPath, &context);
  if (!modA || failed(verify(modA.get()))) {
    llvm::outs() << "[闸门一] parse + verify: 拒绝（verifier_reject，"
                    "报错见 stderr）\n";
    llvm::outs() << "verdict=verifier_reject\n";
    bool ok = (expect == "verifier_reject");
    llvm::outs() << (ok ? "accept=PASS" : "accept=FAIL") << "\n";
    return ok ? 0 : 1;
  }
  llvm::outs() << "[闸门一] parse + verify: 通过\n";

  // ---------- R2 的比对基准：融合前 IR（逐字） ----------
  std::string preIR;
  {
    llvm::raw_string_ostream os(preIR);
    modA->print(os);
  }
  llvm::outs() << "===== 输入 IR =====\n" << preIR << "\n";

  auto makePatterns = [&](MLIRContext *ctx) {
    RewritePatternSet patterns(ctx);
    patterns.add<FuseMatmulBiasTwoStagePattern>(ctx, 1);    // P1
    patterns.add<AbsorbReluEpiloguePattern>(ctx, 1);       // P2
    patterns.add<FuseAddReluGuardedPattern>(ctx, 1);       // P51g
    patterns.add<FuseMatmulBiasReluDirectPattern>(ctx, 2); // P3
    return patterns;
  };

  // ---------- A 路：bottom-up 遍历（默认） ----------
  llvm::errs() << "决策日志（A 路，bottom-up）：\n";
  bool convergedA = true;
  {
    GreedyRewriteConfig config;           // useTopDownTraversal 默认 false
    modA->walk([&](func::FuncOp fn) {
      if (failed(applyPatternsAndFoldGreedily(
              fn, FrozenRewritePatternSet(makePatterns(&context)), config)))
        convergedA = false;
    });
  }
  if (!convergedA) {
    llvm::errs() << "!! A 路驱动未收敛\n";
    return 2;
  }

  // ---------- B 路：同一输入重新解析，top-down 遍历 ----------
  OwningOpRef<ModuleOp> modB = parseSourceFile<ModuleOp>(inputPath, &context);
  if (!modB || failed(verify(modB.get()))) {
    llvm::errs() << "B 路重新解析失败（不该发生）\n";
    return 1;
  }
  llvm::errs() << "决策日志（B 路，top-down）：\n";
  bool convergedB = true;
  {
    GreedyRewriteConfig config;
    config.useTopDownTraversal = true;
    modB->walk([&](func::FuncOp fn) {
      if (failed(applyPatternsAndFoldGreedily(
              fn, FrozenRewritePatternSet(makePatterns(&context)), config)))
        convergedB = false;
    });
  }
  if (!convergedB) {
    llvm::errs() << "!! B 路驱动未收敛\n";
    return 2;
  }

  // ---------- R1：两种遍历必须殊途同归 ----------
  std::vector<std::string> namesA = collectOpNames(modA.get());
  std::vector<std::string> namesB = collectOpNames(modB.get());
  bool r1 = (namesA == namesB);
  llvm::outs() << "[R1] 双遍历同形态（bottom-up == top-down）: "
               << (r1 ? "PASS" : "FAIL") << "\n";

  std::string postA, postB;
  {
    llvm::raw_string_ostream os(postA);
    modA->print(os);
    llvm::raw_string_ostream os2(postB);
    modB->print(os2);
  }
  llvm::outs() << "===== 融合后（A 路 bottom-up）=====\n" << postA << "\n";
  llvm::outs() << "===== 融合后（B 路 top-down）=====\n" << postB << "\n";

  // ---------- R2：负例的拒绝必须是恒等变换（IR 逐字不变） ----------
  bool r2checked = (expect == "identity");
  bool r2 = (postA == preIR);
  if (r2checked)
    llvm::outs() << "[R2] 恒等拒绝（IR 逐字不变）: "
                 << (r2 ? "PASS" : "FAIL") << "\n";

  // ---------- 融合后复查 verify ----------
  bool verifyAfter = succeeded(verify(modA.get()));
  llvm::outs() << "[verify] 融合后复查: " << (verifyAfter ? "通过" : "失败")
               << "\n";

  // ---------- 判决 ----------
  bool hasFused = false;
  for (auto &n : namesA)
    if (n.substr(0, 11) == "mini.fused_")
      hasFused = true;
  std::string verdict = hasFused ? "fused" : "identity";
  llvm::outs() << "verdict=" << verdict << "\n";

  bool ok = r1 && verifyAfter && (expect.empty() || verdict == expect) &&
            (!r2checked || r2);
  llvm::outs() << (ok ? "accept=PASS" : "accept=FAIL") << "\n";
  return ok ? 0 : 1;
}
