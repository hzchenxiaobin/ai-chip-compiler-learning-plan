//===- ReluCanonicalization.cpp - mini.relu 的规范化 Pattern ----*- C++ -*-===//
//
// 第 45 天的主角：第一个 RewritePattern —— SimplifyDoubleRelu。
//
//   %r1 = mini.relu %x        : T -> T
//   %r2 = mini.relu %r1       : T -> T      ; 外层，被匹配的根节点
//   ... 使用 %r2 ...
//
//   ==SimplifyDoubleRelu==>
//
//   %r1 = mini.relu %x        ; 内层原样保留（它定义了替换值）
//   ... 使用 %r1 ...           ; 所有使用者的边从 %r2 改指 %r1
//
// 合法性一句话：relu 的输出已经 >= 0，再套一层 max(0, .) 不可能改变
// 任何元素——max(0, max(0, x)) == max(0, x) 对所有实数成立，所以删掉
// 外层不改变任何使用者读到的值（语义不变，且必然少一次计算）。
//
// 结构分两层，和 Day 44 的 ShapeInferencePass 同一个套路：
//
//   1. SimplifyDoubleRelu —— Pattern 本体：只管“看到什么形状的 IR、
//      换成什么形状的 IR”。什么时候被调用、被谁调用，一概不知道。
//   2. ReluOp::getCanonicalizationPatterns —— 挂钩：把 Pattern 塞进
//      驱动发来的 results 集合。MiniOps.td 里 hasCanonicalizer = 1
//      让 tblgen 生成这个静态函数的声明，本体在这里。
//
// 为什么不自己写个 Pass？因为 Canonicalizer（-canonicalize）就是现成
// 的驱动：它对上下文里每个已注册算子调用 getCanonicalizationPatterns
// 收集 Pattern，再用贪婪工作表驱动迭代到不动点。Pattern 与驱动分离，
// mini-opt 和 Pass 注册代码（Day 41 写好的 registerTransformsPasses）
// 一行都不用动。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"

#include "mlir/IR/PatternMatch.h"

using namespace mlir;

namespace {

//===----------------------------------------------------------------------===//
// Pattern 本体
//===----------------------------------------------------------------------===//

struct SimplifyDoubleRelu : OpRewritePattern<mini::ReluOp> {
  // 继承构造函数：Pattern 需要告诉基类“我匹配哪种算子”
  // （mini::ReluOp::getOperationName()，即 "mini.relu"）和收益权重
  // （默认 1，多个 Pattern 竞争时高者先试）。
  using OpRewritePattern<mini::ReluOp>::OpRewritePattern;

  // matchAndRewrite 是 Pattern 的全部：参数是被驱动选中的“根算子”
  // （这里是一个 mini.relu），返回 failure 表示“这个 Pattern 对当前
  // 节点不适用，请驱动去试别的”；返回 success 表示“已重写完成”。
  LogicalResult matchAndRewrite(mini::ReluOp outer,
                                PatternRewriter &rewriter) const override {
    // ---- 匹配：外层 relu 的输入，是否恰好由另一个 mini.relu 定义？
    // getDefiningOp<T>()：顺着操作数的 def-use 边往上看一步；
    // 类型不匹配（定义者不是 mini.relu，或是函数入口参数）返回空。
    // 这就是“Pattern 匹配”——只看局部形状，不做全局分析。
    mini::ReluOp inner = outer.getInput().getDefiningOp<mini::ReluOp>();
    if (!inner)
      return failure();

    // ---- 重写：把外层的结果“整批”换成内层的结果。
    // 必须通过 rewriter 改 IR：驱动在工作表里排着别的节点，直接改
    // 会让它的计划失效（第 6 节错误 1 有真实复现）。
    //
    // replaceAllUsesWith：替换——遍历 %outer 结果的所有使用者，把
    // 它们的操作数边逐条改指 %inner 的结果。SSA 值本身不可改写，
    // “替换”永远是“改边的指向”。
    rewriter.replaceAllUsesWith(outer.getRes(), inner.getRes());

    // eraseOp：擦除——外层 op 从父 Block 中摘除并销毁。此时它已经
    // 没有任何使用者（上一步全改走了），擦除是安全的；内层 op
    // 原样保留，因为替换值正是它的结果。
    //
    // 等价的一行合体写法（效果完全相同，见教程 5.4 节对照实验）：
    //   rewriter.replaceOp(outer, inner.getRes());
    rewriter.eraseOp(outer);

    return success();
  }
};

} // namespace

//===----------------------------------------------------------------------===//
// 挂钩：把 Pattern 交给 -canonicalize 的驱动
//===----------------------------------------------------------------------===//

// MiniOps.td 的 let hasCanonicalizer = 1 让 tblgen 在生成的类里声明
// 这个静态函数；-canonicalize 收集 Pattern 时，对每个已注册算子调用
// 它。今天只塞一条规则；Day 46 的 Add(x, 0) -> x、Day 47 的常量折叠
// 将来也走同一个入口，按算子各自挂在 mini.add / mini.constant 上。
void mini::ReluOp::getCanonicalizationPatterns(RewritePatternSet &results,
                                               MLIRContext *context) {
  results.add<SimplifyDoubleRelu>(context);
}
