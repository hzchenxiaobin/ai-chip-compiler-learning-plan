//===- AlgebraicSimplification.cpp - mini.add / mini.mul 代数化简 --*- C++ -*-===//
//
// 第 46 天的主角：代数化简 Pattern。把"加零""乘一"这类恒等运算
// 从图里拆掉：
//
//   %z = mini.constant dense<-0.0> : tensor<2x2xf32>   ; 全体元素 = -0.0
//   %s = mini.add %x, %z : ...                          ; 被匹配的根节点
//   ... 使用 %s ...
//
//   ==SimplifyAddNegZero==>
//
//   ... 使用 %x ...            ; 所有使用者的边从 %s 改指 %x；
//                              ; %s 出局，%z 若再无使用者也一并出局
//
// 为什么是 -0.0，不是计划原文里那个 0.0？IEEE 754 的加法规定：
//
//   (-0.0) + (+0.0) = +0.0    ≠ -0.0     —— x 恰好是 -0.0 时，
//                                          Add(x, +0.0) → x 改变了结果；
//   x + (-0.0) = x             对一切 x 成立（含 ±0.0、±Inf）。
//
// 所以"Add(x, 0) → x"这道小学数学题，在 f32 上只有 -0.0 写法是严格
// 安全的。mini.mul 的对应安全恒等式是 Mul(x, 1.0) → x：1.0 乘任何值
// （含 NaN、±Inf、-0.0）数值都不变。反过来 Mul(x, 0.0) → 0 不安全：
// NaN、±Inf 乘 0 得 NaN，-0.0 乘 +0.0 得 -0.0；它还违反收益前提——
// 得凭空造一个新常量（x 是动态 shape 时根本造不出来），见教程 3.3 节。
//
// 与 Day 45 的 SimplifyDoubleRelu 相比，骨架一字不差（Pattern 本体 +
// getCanonicalizationPatterns 挂钩），升级的只有"匹配"这一步：
//   Day 45  看输入的 def-use 边是不是另一个 mini.relu（结构匹配）；
//   Day 46  看某个操作数是不是 mini.constant 定义的、dense 属性里
//           装的是不是全体 -0.0 / 1.0（常量匹配 + 属性读取）。
//
// 假设声明：mini 不跟踪 NaN 的 payload（负载位）。IEEE 754 只要求
// "NaN 参与的运算返回某个 NaN"，不保证结果 NaN 与输入 NaN 逐位相等；
// 本 Pattern 与通用编译器通行做法一致，按"数值相等"判定恒等。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"

#include "llvm/ADT/APFloat.h"
#include "mlir/IR/BuiltinAttributes.h"
#include "mlir/IR/PatternMatch.h"

using namespace mlir;

namespace {

//===----------------------------------------------------------------------===//
// 常量匹配 + 属性读取：对操作数 v 的三连问
//===----------------------------------------------------------------------===//

// 三连问全部通过，v 才算"装着 pred 所指值的常量"：
//   1) v 由 mini.constant 定义吗？——def-use 边向定义方向走一步；
//      函数入口参数、别的算子的结果都回答"不是"（getDefiningOp 返回空）；
//   2) 它的 dense 属性是 splat 吗？——全体元素同一个值才有单一恒等值，
//      dense<[[0.0, 1.0]]> 这种"一半是零"的常量没有可交换的整体；
//   3) splat 元素满足 pred 吗？——把属性里的数读出来判定（-0.0 / 1.0）。
//
// getValue() 的返回类型是 DenseElementsAttr：MiniOps.td 里
// Mini_F32ElementsAttr（FloatElementsAttr<32>）的 C++ 存储类型由 tblgen
// 翻译成 DenseElementsAttr，不用再 cast。
static bool isSplatConstant(Value v, bool (*pred)(const llvm::APFloat &)) {
  mini::ConstantOp cst = v.getDefiningOp<mini::ConstantOp>();
  if (!cst)
    return false;
  DenseElementsAttr attr = cst.getValue();
  if (!attr.isSplat())
    return false;
  return pred(attr.getSplatValue<llvm::APFloat>());
}

// 判定 1：是不是 -0.0。APFloat 自带 isNegZero()（"是零且符号位为负"）。
// 千万别写 splat == APFloat(-0.0)：APFloat 的 operator== 走 IEEE 比较
// 语义，-0.0 == +0.0 成立，+0.0 会被误放行（第 6 节错误 2 有真实复现；
// 判逐位相等要用 isExactlyValue / bitwiseIsEqual）。
static bool isNegZero(const llvm::APFloat &f) { return f.isNegZero(); }

// 判定 2：是不是 1.0。1.0 没有正负零的歧义，isExactlyValue 的逐位
// 比较足够；-1.0 不会误命中（逐位比较，不是 IEEE 语义）。
static bool isOne(const llvm::APFloat &f) { return f.isExactlyValue(1.0); }

// 共享的重写动作：把 op 的唯一结果整体替换成 x（改所有使用者的边），
// 再擦除 op 本身。与 Day 45 的 SimplifyDoubleRelu 后半段逐字同款。
static void replaceWithOperand(PatternRewriter &rewriter, Operation *op,
                               Value result, Value x) {
  rewriter.replaceAllUsesWith(result, x);
  rewriter.eraseOp(op);
}

//===----------------------------------------------------------------------===//
// Pattern 1：Add(x, -0.0) → x
//===----------------------------------------------------------------------===//

struct SimplifyAddNegZero : OpRewritePattern<mini::AddOp> {
  // 继承构造：告诉基类"我匹配 mini.add"（getOperationName() 即
  // "mini.add"）和收益分数（默认 1，多个 Pattern 竞争同一根节点时
  // 分高者先被尝试——今天的两条规则互不竞争，都用默认值）。
  using OpRewritePattern<mini::AddOp>::OpRewritePattern;

  LogicalResult matchAndRewrite(mini::AddOp add,
                                PatternRewriter &rewriter) const override {
    // 匹配：加法满足交换律，-0.0 常量在右边或在左边是同一个恒等式，
    // 两个方向都收。两边都是 -0.0 常量时取 lhs（结果同为 -0.0，等价）。
    Value x;
    if (isSplatConstant(add.getRhs(), isNegZero))
      x = add.getLhs();
    else if (isSplatConstant(add.getLhs(), isNegZero))
      x = add.getRhs();
    else
      return failure(); // 没有任何一侧是全 -0.0 常量：不适用，交回驱动

    // 类型护栏：x 的类型必须与 add 的结果类型完全一致才动手。
    // Verifier 对动态维保守放行（?x3 与 2x3 记 Same），但把结果
    // （如 2x3）替换成 x（如 ?x3）会让使用者拿到类型对不上的值，
    // canonicalize 之后 IR 过不了验证（第 6 节错误 3 有真实复现）。
    if (x.getType() != add.getRes().getType())
      return failure();

    // 重写：改边（所有使用者改指 x），擦除（add 出局）。
    replaceWithOperand(rewriter, add, add.getRes(), x);
    return success();
  }
};

//===----------------------------------------------------------------------===//
// Pattern 2：Mul(x, 1.0) → x
//===----------------------------------------------------------------------===//

struct SimplifyMulOne : OpRewritePattern<mini::MulOp> {
  using OpRewritePattern<mini::MulOp>::OpRewritePattern;

  LogicalResult matchAndRewrite(mini::MulOp mul,
                                PatternRewriter &rewriter) const override {
    // 乘法同样满足交换律，两个方向都收。
    Value x;
    if (isSplatConstant(mul.getRhs(), isOne))
      x = mul.getLhs();
    else if (isSplatConstant(mul.getLhs(), isOne))
      x = mul.getRhs();
    else
      return failure();

    // 类型护栏：与 SimplifyAddNegZero 同款、同样不能省。
    if (x.getType() != mul.getRes().getType())
      return failure();

    replaceWithOperand(rewriter, mul, mul.getRes(), x);
    return success();
  }
};

} // namespace

//===----------------------------------------------------------------------===//
// 挂钩：把 Pattern 交给 -canonicalize 的驱动
//===----------------------------------------------------------------------===//

// MiniOps.td 里 let hasCanonicalizer = 1 让 tblgen 在 Mini_AddOp /
// Mini_MulOp 的生成类里声明这两个静态函数；-canonicalize 收集 Pattern
// 时对上下文里每个已注册算子逐个调用。Day 45 的 ReluOp 走的也是这个
// 入口——第 45 天埋在 ReluCanonicalization.cpp 尾注里的"Day 46 的
// Add(x, 0) 将来也走同一入口"今天兑现。
//
// 第 49 天（第 7 周复盘）改动：add 升级为 addWithLabel，给两条 Pattern
// 分别贴上 mini-add-neg-zero / mini-mul-one 标签（动机见
// ReluCanonicalization.cpp 尾注）。标签让 --enable-patterns /
// --disable-patterns 可以单独开关每条 Pattern——第 49 天正是用它证明
// "组合用例必须连续执行两种 Pattern 才能完全优化"。
void mini::AddOp::getCanonicalizationPatterns(RewritePatternSet &results,
                                              MLIRContext *context) {
  results.addWithLabel<SimplifyAddNegZero>({"mini-add-neg-zero"}, context);
}

void mini::MulOp::getCanonicalizationPatterns(RewritePatternSet &results,
                                              MLIRContext *context) {
  results.addWithLabel<SimplifyMulOne>({"mini-mul-one"}, context);
}
