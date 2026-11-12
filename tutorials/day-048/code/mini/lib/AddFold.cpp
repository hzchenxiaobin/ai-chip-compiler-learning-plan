//===- AddFold.cpp - mini.add / mini.constant 常量折叠 ---------*- C++ -*-===//
//
// 第 47 天的主角：常量折叠（Constant Folding）。对"常量碰常量"的
// mini.add 直接在编译期把和算出来：
//
//   %a = mini.constant dense<1.0> : tensor<f32>
//   %b = mini.constant dense<2.0> : tensor<f32>
//   %s = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
//
//   ==fold + materializeConstant==>
//
//   %s = mini.constant dense<3.0> : tensor<f32>   ; 新常量由驱动物化，
//                                                  ; 旧 add 出局
//
// 与 Day 45/46 的 RewritePattern 相比，今天是另一条生产线：
//   Pattern：拿 PatternRewriter，亲手改图（replaceUses + eraseOp）；
//   fold：   只做纯计算——读进属性，算出属性，原路返回。不许碰 IR
//            （连 PatternRewriter 的影子都见不到）。把属性变回 IR 上
//            一个真实节点（"常量物化"）是驱动的活，它调用方言的
//            materializeConstant 钩子（MiniDialect.cpp，今天同步新增）。
//
// 为什么要这么分？因为 fold 的输出是"值"而不是"指令"，驱动拿到值
// 之后可以做 Pattern 做不到的事：把两个地方算出的相同常量合并成
// 一个节点（OperationFolder 的 uniquing），不重复往图里塞。
//
// 两道护栏（对应计划里"限制过大 Tensor 的编译期展开"）：
//   类型护栏：结果类型 == 两个操作数类型，才保证物化出的常量能
//             无缝顶替 add 的结果（Day 46 的教训原样搬来）；
//   尺寸护栏：元素个数 > kMaxFoldElements 就拒绝——每折叠一次是
//             O(N) 次 APFloat 加法，还要物化一个 N 元素的新属性；
//             大常量在编译期展开的开销可能超过它省下的运行期开销。
//
//===----------------------------------------------------------------------===//

#include "mini/Ops.h"

#include "llvm/ADT/APFloat.h"
#include "llvm/ADT/STLExtras.h" // llvm::zip：两个常量的元素逐对配对
#include "mlir/IR/BuiltinAttributes.h"
#include "mlir/IR/BuiltinTypes.h"

using namespace mlir;

namespace {

// 尺寸护栏的阈值：单次折叠最多愿意算多少个元素。
// 1024 是教学取值：足够覆盖 bias、标量、小张量等真实折叠场景，
// 又能把 64x64（4096）这类"一折叠就是几千次浮点加法 + 几千个
// 元素的新属性"的大常量挡在编译期展开之外。真实编译器会按
// 编译时间预算调这个数（教程 5.6 节实测不同尺寸的真实代价）。
constexpr int64_t kMaxFoldElements = 1024;

} // namespace

//===----------------------------------------------------------------------===//
// mini.constant 的 fold：把 value 属性原样奉还
//===----------------------------------------------------------------------===//

// 这不是化简，是"递纸条"：驱动折叠某个 op 时，需要知道它的操作数
// 装着什么常量值。对操作数的定义者（ConstantLike 的 op）调用 fold，
// 得到的属性就是操作数的值。mini.constant 的值就存在 value 属性里，
// 所以原样返回；上游 arith.constant 的 fold 是同一句话。
OpFoldResult mini::ConstantOp::fold(mini::ConstantOp::FoldAdaptor adaptor) {
  return getValue();
}

//===----------------------------------------------------------------------===//
// mini.add 的 fold：常量碰常量，编译期把和算出来
//===----------------------------------------------------------------------===//

OpFoldResult mini::AddOp::fold(mini::AddOp::FoldAdaptor adaptor) {
  // 匹配第一步：两个操作数都得带着常量属性进门。
  // FoldAdaptor 里的属性是驱动收集的：操作数由 ConstantLike 的 op
  // 定义才有，否则是空 Attribute（函数参数、别的算子的结果都算
  // "非常量"）。dyn_cast_or_null 顺带确认属性确实是 dense<f32>。
  DenseElementsAttr lhs =
      dyn_cast_or_null<DenseElementsAttr>(adaptor.getLhs());
  DenseElementsAttr rhs =
      dyn_cast_or_null<DenseElementsAttr>(adaptor.getRhs());
  if (!lhs || !rhs)
    return {}; // 有一个不是常量：无活可干，交回驱动

  // 类型护栏：add 的结果类型必须和两个操作数类型完全一致。
  // Verifier 对动态维保守放行（?x3 与 2x3 记 Same），但物化出的常量
  // 类型跟着属性走（静态 2x3），顶替一个 ?x3 的结果会让使用者类型
  // 对不上——canonicalize 之后 IR 过不了验证（第 6 节错误 1）。
  // 顺带排除了 rank 或维数不一致的非法输入在 fold 里被误算。
  if (getRes().getType() != getLhs().getType() ||
      getRes().getType() != getRhs().getType())
    return {};

  // 尺寸护栏：元素太多就不在编译期展开。dense 属性的元素个数由
  // 类型决定（dense 要求全静态维，这里 cast 是安全的）。
  ShapedType resType = cast<ShapedType>(getRes().getType());
  if (resType.getNumElements() > kMaxFoldElements)
    return {};

  // 纯计算：逐元素 APFloat 加法，舍入模式与运行期默认一致
  // （round to nearest, ties to even）。IEEE 的边角值——inf + (-inf)
  // 得 NaN、(-0.0) + (+0.0) 得 +0.0——APFloat 按标准处理，fold
  // 出来的就是运行期会算出的同一个位模式（教程 5.5 节有实测见证）。
  // 注：MLIR 18 的 DenseElementsAttr 没有 begin<T>()/end<T>()，
  // 标准入口是 getValues<T>()——返回一个可迭代的值区间。
  SmallVector<llvm::APFloat, 16> sum;
  sum.reserve(lhs.getNumElements());
  for (auto [l, r] : llvm::zip(lhs.getValues<llvm::APFloat>(),
                               rhs.getValues<llvm::APFloat>())) {
    llvm::APFloat v = l;
    v.add(r, llvm::APFloat::rmNearestTiesToEven);
    sum.push_back(v);
  }

  // 把值交出去，节点交给驱动处理：它拿着这个属性调用
  // MiniDialect::materializeConstant 物化出 mini.constant，
  // 再把 add 的使用者全部改指新常量、擦除 add。
  return DenseElementsAttr::get(resType, sum);
}
