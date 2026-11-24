// mini-journey.cpp —— 第 56 天核心示例：一条 IR 的四站旅程（第 8 周复盘）
//
// 用法: ./mini-journey <input.mlir> [--skip-infer]
//                      [--expect=fused|identity|verifier_reject]
//
// 把第 8 周攒下的全部能力接进同一条管道，复盘计划里的实践题：
//   「用 15 分钟讲解一个输入 IR 如何经过验证、Shape 推导、折叠和融合」
//
//   站 1  验证      parse + verify（第 39/40/55 天的 Verifier 规则）
//   站 2  Shape 推导 matmul 结果 ? 维细化 + 类型跟随传播 + 签名细化
//                    （第 43/44 天规则的最小复刻）
//   站 3  折叠      fold 钩子（第 47 天）+ 死常量收尾（第 25 天 DCE）
//   站 4  融合      P1/P2/P51g/P3 让位版 + 类型闸门 + ? 护栏
//                    （第 51~55 天收敛的最终形态 Pattern 集）
//
// 每站出口都复查 verify；末尾打印各站 mini.* 计数表与 15 分钟讲解
// 时间轴（数字来自本次真实运行）。--skip-infer 是对照实验：跳过站 2，
// 观察「信息不齐，融合站卡住」——第 49 天信息关卡在融合场景的再现。
//
// 判决与退出码（与第 55 天 mini-accept 同口径）：
//   verdict = fused | identity | verifier_reject
//   accept=PASS 且 rc=0：期望判决吻合、各站 verify 复查通过

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
#include "llvm/ADT/SmallVector.h"
#include "llvm/Support/raw_ostream.h"

#include <map>
#include <string>
#include <vector>

using namespace mlir;

namespace {

// ============ 计数：mini.* 算子按种类统计（程序序） ============

struct OpCounts {
  int total = 0;
  std::map<std::string, int> byKind;
};

static OpCounts countMiniOps(ModuleOp mod) {
  OpCounts c;
  mod->walk<WalkOrder::PreOrder>([&](Operation *op) {
    llvm::StringRef name = op->getName().getStringRef();
    if (name.starts_with("mini.")) {
      ++c.total;
      ++c.byKind[name.str()];
    }
  });
  return c;
}

static std::string countsLine(const OpCounts &c) {
  std::string s;
  llvm::raw_string_ostream os(s);
  for (auto &[k, v] : c.byKind)
    os << k << "x" << v << " ";
  return s;
}

static std::string dumpIR(ModuleOp mod) {
  std::string s;
  llvm::raw_string_ostream os(s);
  mod->print(os);
  return s;
}

// ============ 站 2：Shape 推导（第 43/44 天规则的最小复刻） ============

// refine(old, new)：old 的维是数字就保留（写 IR 的人对 Verifier 的
// 承诺，Pass 无权改写），是 ? 才采纳 new 的对应维（Day 44 口径）。
// new 也是 ? 就保持 ?（两侧都未知，不许编数字）。
static Type refineType(Type oldT, Type newT) {
  auto o = oldT.dyn_cast<RankedTensorType>();
  auto n = newT.dyn_cast<RankedTensorType>();
  if (!o || !n)
    return oldT;
  SmallVector<int64_t, 4> shape;
  for (unsigned i = 0; i < o.getRank(); ++i) {
    int64_t od = o.getDimSize(i), nd = n.getDimSize(i);
    if (!ShapedType::isDynamic(od))
      shape.push_back(od);          // 静态：保留
    else if (!ShapedType::isDynamic(nd))
      shape.push_back(nd);          // ? + 数字：采纳
    else
      shape.push_back(od);          // ? + ?：保持 ?
  }
  return RankedTensorType::get(shape, o.getElementType());
}

// 推导站本体，迭代到不动点（最多 10 轮）：
//   (a) matmul：lhs/rhs 静态 -> 期望 [M,N]，结果维 ? 细化
//   (b) add / fused_add_relu：结果类型跟 lhs 走（Day 40 的 Verifier 规则）
//   (c) relu：结果类型跟输入走（SameOperandsAndResultType）
//   (d) 函数签名：return 操作数类型细化后，签名跟着细化——
//       签名也是类型信息的一部分，不细化的话 verify 复查会挂
static void inferShapes(ModuleOp mod, int &nRefined, int &nPropagated) {
  for (int round = 0; round < 10; ++round) {
    bool changed = false;
    // (a) matmul：唯一能「无中生有」产出数字的规则（Day 43 的 R1～R4）
    mod->walk([&](mini::MatmulOp mm) {
      auto lhs = mm.getLhs().getType().dyn_cast<RankedTensorType>();
      auto rhs = mm.getRhs().getType().dyn_cast<RankedTensorType>();
      if (!lhs || !rhs || !lhs.hasStaticShape() || !rhs.hasStaticShape())
        return;
      auto expected = RankedTensorType::get(
          {lhs.getShape()[0], rhs.getShape()[1]}, lhs.getElementType());
      Type t = refineType(mm.getRes().getType(), expected);
      if (t != mm.getRes().getType()) {
        mm.getRes().setType(t);
        llvm::errs() << "  [J2] matmul 结果 " << mm.getRes() << ": ? 维细化为 "
                    << t << "\n";
        ++nRefined;
        changed = true;
      }
    });
    // (b)(c) 类型跟随传播：结果里的 ? 采纳操作数里已有的数字
    mod->walk([&](Operation *op) {
      Value res, operand;
      if (auto ad = dyn_cast<mini::AddOp>(op)) {
        res = ad.getRes();
        operand = ad.getLhs();
      } else if (auto fa = dyn_cast<mini::FusedAddReluOp>(op)) {
        res = fa.getRes();
        operand = fa.getLhs();
      } else if (auto re = dyn_cast<mini::ReluOp>(op)) {
        res = re.getResult();
        operand = re.getX();
      } else {
        return;
      }
      Type t = refineType(res.getType(), operand.getType());
      if (t != res.getType()) {
        llvm::errs() << "  [J2] " << op->getName().getStringRef()
                    << " 结果类型跟随操作数: -> " << t << "\n";
        res.setType(t);
        ++nPropagated;
        changed = true;
      }
    });
    // (d) 函数签名：返回类型里的 ? 跟着 return 操作数细化
    mod->walk([&](func::FuncOp fn) {
      func::ReturnOp retOp;
      fn.walk([&](func::ReturnOp r) { retOp = r; });
      if (!retOp)
        return;
      auto oldTy = fn.getFunctionType();
      SmallVector<Type, 4> results(retOp.getOperandTypes().begin(),
                                   retOp.getOperandTypes().end());
      bool sig = false;
      for (size_t i = 0; i < results.size() &&
                         i < oldTy.getResults().size(); ++i) {
        Type t = refineType(oldTy.getResults()[i], results[i]);
        if (t != oldTy.getResults()[i]) {
          results[i] = t;
          sig = true;
        }
      }
      if (sig) {
        llvm::errs() << "  [J2] 函数签名返回类型细化: " << oldTy << " -> "
                    << FunctionType::get(fn.getContext(), oldTy.getInputs(),
                                         results)
                    << "\n";
        fn.setType(FunctionType::get(fn.getContext(), oldTy.getInputs(),
                                     results));
        changed = true;
      }
    });
    if (!changed)
      break;
  }
}

// ============ 站 3：折叠（fold 钩子 + 死常量收尾） ============

// fold 住在算子钩子里（MiniDialect.cpp 的 AddOp::fold / ConstantOp::fold，
// 第 47 天口径）；Pattern 集只挂「擦除无使用者的 mini.constant」——
// fold 造出新常量后，失去使用者的旧常量由它收走（第 25 天 DCE 的
// 常量特例）。分工：fold 只算值，DCE 收尸，驱动排班。
struct EraseDeadConstantPattern : OpRewritePattern<mini::ConstantOp> {
  using OpRewritePattern<mini::ConstantOp>::OpRewritePattern;
  LogicalResult matchAndRewrite(mini::ConstantOp c,
                                PatternRewriter &rewriter) const override {
    if (!c.getRes().use_empty())
      return failure();
    rewriter.eraseOp(c);
    return success();
  }
};

// ============ 站 4：融合 Pattern 集（第 51～55 天最终形态 + ? 护栏） ============

// 类型闸门（第 55 天）：fused* 的语义只对 f32 验证过
static bool allF32(ArrayRef<Value> vals) {
  for (Value v : vals) {
    auto t = v.getType().dyn_cast<RankedTensorType>();
    if (!t || !t.getElementType().isF32())
      return false;
  }
  return true;
}

// ? 护栏（第 56 天，第 46/49 天类型护栏口径在融合场景的延续）：
// 乘积/加法结果类型含 ? 时拒绝融合——把 ?x2 的结果顶替进融合产物，
// 使用者类型对不上；重写被护栏拦下时，缺的不是遍数，是类型信息。
static bool hasStaticTensorShape(Value v) {
  auto t = v.getType().dyn_cast<RankedTensorType>();
  return t && t.hasStaticShape();
}

// 共用：在 add 两侧找「乘积 / bias」＝第 53 天的判定
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

// P1 两阶段·第一步：MatMul + Add -> fused_matmul_bias
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
    if (!hasStaticTensorShape(m)) {
      llvm::errs() << "  [P1] 乘积类型含动态维（?）-> 拒绝"
                      "（信息不齐的重写不做，等 Shape 推导细化）\n";
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

// P2 两阶段·第二步：Relu(fused_matmul_bias) -> fused_mm_bias_relu
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

// P51g：让位版 Add + Relu -> fused_add_relu
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
    if (!hasStaticTensorShape(x)) {
      llvm::errs() << "  [P51g] add 结果类型含动态维（?）-> 拒绝"
                      "（融合产物必须类型明确，等 Shape 推导细化）\n";
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

// P3 直接三算子：MatMul + Add (+Relu) -> fused_mm_bias(_relu)
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
    if (!hasStaticTensorShape(m)) {
      llvm::errs() << "  [P3] 乘积类型含动态维（?）-> 拒绝"
                      "（信息不齐的重写不做，等 Shape 推导细化）\n";
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

// ============ 各站驱动 ============

static bool runFoldStation(func::FuncOp fn, MLIRContext &context) {
  RewritePatternSet patterns(&context);
  patterns.add<EraseDeadConstantPattern>(&context);
  GreedyRewriteConfig config;
  return succeeded(applyPatternsAndFoldGreedily(
      fn, FrozenRewritePatternSet(std::move(patterns)), config));
}

static bool runFuseStation(func::FuncOp fn, MLIRContext &context) {
  RewritePatternSet patterns(&context);
  patterns.add<FuseMatmulBiasTwoStagePattern>(&context, 1);    // P1
  patterns.add<AbsorbReluEpiloguePattern>(&context, 1);        // P2
  patterns.add<FuseAddReluGuardedPattern>(&context, 1);        // P51g
  patterns.add<FuseMatmulBiasReluDirectPattern>(&context, 2);  // P3
  GreedyRewriteConfig config;
  return succeeded(applyPatternsAndFoldGreedily(
      fn, FrozenRewritePatternSet(std::move(patterns)), config));
}

// ============ main：四站顺序执行，逐站 dump 与复查 ============

int main(int argc, char **argv) {
  if (argc < 2) {
    llvm::errs() << "用法: " << argv[0] << " <input.mlir> [--skip-infer] "
                 << "[--expect=fused|identity|verifier_reject]\n";
    return 1;
  }
  std::string inputPath = argv[1];
  bool skipInfer = false;
  std::string expect;                    // 空 = 只报告，不比对
  for (int i = 2; i < argc; ++i) {
    llvm::StringRef arg = argv[i];
    if (arg == "--skip-infer")
      skipInfer = true;
    if (arg.starts_with("--expect="))
      expect = arg.substr(strlen("--expect=")).str();
  }

  DialectRegistry registry;
  registry.insert<mini::MiniDialect, func::FuncDialect>();
  MLIRContext context;
  context.appendDialectRegistry(registry);
  context.loadAllAvailableDialects();

  // ---------- 站 1：parse + verify ----------
  OwningOpRef<ModuleOp> mod = parseSourceFile<ModuleOp>(inputPath, &context);
  if (!mod || failed(verify(mod.get()))) {
    llvm::outs() << "[J1] parse + verify: 拒绝（verifier_reject，"
                    "报错见 stderr；后续三站短路）\n";
    llvm::outs() << "verdict=verifier_reject\n";
    bool ok = (expect == "verifier_reject");
    llvm::outs() << (ok ? "accept=PASS" : "accept=FAIL") << "\n";
    return ok ? 0 : 1;
  }
  llvm::outs() << "[J1] parse + verify: 通过\n";

  OpCounts c0 = countMiniOps(mod.get());
  llvm::outs() << "===== 阶段 0: 输入 IR（" << c0.total << " 个 mini.*）=====\n"
               << dumpIR(mod.get()) << "\n";
  llvm::outs() << "===== 阶段 1: 验证后 IR（"
               << c0.total << " 个 mini.*——验证只裁决，不改图）=====\n"
               << dumpIR(mod.get()) << "\n";

  // ---------- 站 2：Shape 推导 ----------
  int nRefined = 0, nPropagated = 0;
  if (!skipInfer) {
    llvm::errs() << "站 2 Shape 推导（细化 + 传播 + 签名，迭代到不动点）：\n";
    inferShapes(mod.get(), nRefined, nPropagated);
    llvm::outs() << "[J2] Shape 推导: 细化 " << nRefined << " 处、传播 "
                 << nPropagated << " 处\n";
  } else {
    llvm::outs() << "[J2] Shape 推导: 跳过（--skip-infer 对照实验）\n";
  }
  OpCounts c2 = countMiniOps(mod.get());
  llvm::outs() << "===== 阶段 2: Shape 推导后 IR（" << c2.total
               << " 个 mini.*——推导只细化类型，不删算子）=====\n"
               << dumpIR(mod.get()) << "\n";
  bool v2 = succeeded(verify(mod.get()));
  llvm::outs() << "[J2] verify 复查: " << (v2 ? "通过" : "失败") << "\n";

  // ---------- 站 3：折叠 ----------
  llvm::errs() << "站 3 折叠（fold 钩子 + 死常量收尾，迭代到不动点）：\n";
  int addBefore = c2.byKind.count("mini.add") ? c2.byKind["mini.add"] : 0;
  bool ok3 = true;
  mod->walk([&](func::FuncOp fn) {
    if (!runFoldStation(fn, context))
      ok3 = false;
  });
  if (!ok3) {
    llvm::errs() << "!! 折叠站驱动未收敛\n";
    return 2;
  }
  OpCounts c3 = countMiniOps(mod.get());
  int addAfter = c3.byKind.count("mini.add") ? c3.byKind["mini.add"] : 0;
  llvm::outs() << "[J3] 折叠: " << (addBefore - addAfter)
               << " 个 add 折成常量\n";
  llvm::outs() << "===== 阶段 3: 折叠后 IR（" << c3.total
               << " 个 mini.*）=====\n"
               << dumpIR(mod.get()) << "\n";
  bool v3 = succeeded(verify(mod.get()));
  llvm::outs() << "[J3] verify 复查: " << (v3 ? "通过" : "失败") << "\n";

  // ---------- 站 4：融合 ----------
  llvm::errs() << "站 4 融合（P1/P2/P51g/P3 让位版 + 类型闸门 + ? 护栏）：\n";
  bool ok4 = true;
  mod->walk([&](func::FuncOp fn) {
    if (!runFuseStation(fn, context))
      ok4 = false;
  });
  if (!ok4) {
    llvm::errs() << "!! 融合站驱动未收敛\n";
    return 2;
  }
  OpCounts c4 = countMiniOps(mod.get());
  llvm::outs() << "===== 阶段 4: 融合后 IR（" << c4.total
               << " 个 mini.*）=====\n"
               << dumpIR(mod.get()) << "\n";
  bool v4 = succeeded(verify(mod.get()));
  llvm::outs() << "[J4] verify 复查: " << (v4 ? "通过" : "失败") << "\n";

  // ---------- 判决 ----------
  bool hasFused = false;
  for (auto &[k, v] : c4.byKind)
    if (k.substr(0, 11) == "mini.fused_")
      hasFused = true;
  std::string verdict = hasFused ? "fused" : "identity";
  llvm::outs() << "verdict=" << verdict << "\n";

  // ---------- 汇总：各站计数表 + 15 分钟讲解时间轴 ----------
  llvm::outs() << "===== 汇总：一条 IR 的四站旅程 =====\n";
  llvm::outs() << "站点            mini.* 计数   变化\n";
  llvm::outs() << "输入            " << c0.total << "\n";
  llvm::outs() << "站 1 验证        " << c0.total
               << "        （只裁决，结构不变）\n";
  llvm::outs() << "站 2 Shape 推导   " << c2.total << "        （"
               << (skipInfer ? "--skip-infer：类型保持 ?x2，站 4 会付代价"
                             : "类型 ?x2 -> 2x2，结构不变")
               << "）\n";
  llvm::outs() << "站 3 折叠        " << c3.total
               << "        （add(0.5,0.5) -> 1.0，死常量被收走）\n";
  llvm::outs() << "站 4 融合        " << c4.total
               << "        （" << countsLine(c4) << "）\n";
  llvm::outs() << "\n===== 15 分钟讲解时间轴（数字来自本次真实运行）=====\n";
  llvm::outs() << " 0:00- 2:00  开场：输入图 " << c0.total
               << " 个 mini.*（两条链），讲解目标：走完四站剩 " << c4.total
               << " 个\n";
  llvm::outs() << " 2:00- 5:00  站 1 验证：合法性裁决（结构不变 "
               << c0.total << "->" << c0.total
               << "；f64/错形状负例在此短路）\n";
  if (skipInfer)
    llvm::outs() << " 5:00- 8:00  站 2 推导：本次被 --skip-infer 跳过——"
                    "记住这个缺口，站 4 会付代价\n";
  else
    llvm::outs() << " 5:00- 8:00  站 2 推导：? 维细化 " << nRefined
                 << " 处、类型跟随 " << nPropagated
                 << " 处（只补信息，不动图）\n";
  llvm::outs() << " 8:00-11:00  站 3 折叠：" << (addBefore - addAfter)
               << " 个 add 折成常量（fold 只算值不碰图，DCE 收尸）\n";
  llvm::outs() << "11:00-14:00  站 4 融合：先查后改（use 表、类型闸门、? "
                  "护栏），多使用者铁律看 shared 用例\n";
  llvm::outs() << "14:00-15:00  收尾：" << c0.total << " -> " << c4.total
               << " 计数表 + 「融合为什么不仅是图模式替换」一句话\n";

  bool ok = v2 && v3 && v4 && (expect.empty() || verdict == expect);
  llvm::outs() << (ok ? "accept=PASS" : "accept=FAIL") << "\n";
  return ok ? 0 : 1;
}
