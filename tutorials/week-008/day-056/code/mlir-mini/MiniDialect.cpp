#include "MiniDialect.h"

#include "MiniRules.h"

#include "mlir/IR/DialectImplementation.h"
#include "mlir/IR/OpImplementation.h"
#include "llvm/ADT/SmallVector.h"

using namespace mlir;

// TableGen 生成：MiniDialect 构造函数、类型注册
#include "MiniDialect.cpp.inc"

// TableGen 生成：七个算子的 parse/print/verify/build/fold 声明实现
#define GET_OP_CLASSES
#include "MiniOps.cpp.inc"

// 注册本 Dialect 的全部算子：解析器和 Pattern 驱动靠这里认识 mini.* 操作
// 第 56 天：第 47 天的 mini.constant 回归（折叠站的主角）
void mini::MiniDialect::initialize() {
  addOperations<mini::ConstantOp, mini::MatmulOp, mini::AddOp, mini::ReluOp,
                mini::FusedAddReluOp, mini::FusedMatmulBiasOp,
                mini::FusedMatmulBiasReluOp>();
}

// ===================== 常量物化（第 47/49 天口径） =====================
// fold 只返回「值」（Attribute）；把值变回 IR 上一个真实 mini.constant
// 节点是这个钩子的活。折叠驱动（OperationFolder）折出属性结果后回头调
// 它；不实现这个钩子，fold 返回的属性没有落脚点，折叠等于白算。
// 声明由 MiniOps.td 的 hasConstantMaterializer = 1 生成（第 49 天结论：
// 手抄类外定义编译不过，唯一正确入口是 TableGen 开关）。
Operation *mini::MiniDialect::materializeConstant(OpBuilder &builder,
                                                  Attribute value, Type type,
                                                  Location loc) {
  auto dense = dyn_cast<DenseElementsAttr>(value);
  auto tensorType = dyn_cast<ShapedType>(type);
  if (!dense || !tensorType || dense.getType() != tensorType)
    return nullptr;
  return builder.create<mini::ConstantOp>(loc, tensorType, dense);
}

// ===================== 手写 Verifier：规则来自 MiniRules.h =====================

LogicalResult mini::ConstantOp::verify() {
  auto dense = getValue().dyn_cast<DenseElementsAttr>();
  if (!dense)
    return emitOpError("value 必须是 dense elements 属性");
  if (dense.getType() != getRes().getType())
    return emitOpError("value 属性类型必须与结果类型一致");
  if (!dense.getElementType().isF32())
    return emitOpError("本教程壳的常量只支持 f32");
  return success();
}

LogicalResult mini::MatmulOp::verify() {
  return verifyMatmul2D(getOperation(), getLhs().getType(),
                        getRhs().getType(), getRes().getType());
}

LogicalResult mini::AddOp::verify() {
  // rhs 相对 lhs 三分类（add 对称，bias 在哪侧都行——先按 rhs 报，
  // 报错文案只说形状不说左右，两侧交换后读者自己能对上）
  mlir::Type lhsT = getLhs().getType(), rhsT = getRhs().getType();
  auto lhs = lhsT.dyn_cast<mlir::RankedTensorType>();
  auto rhs = rhsT.dyn_cast<mlir::RankedTensorType>();
  if (!lhs || !rhs)
    return emitOpError("操作数必须是 ranked tensor");
  switch (classifyBias(rhsT, lhsT)) {
  case mini::BiasKind::Same:
    break;
  case mini::BiasKind::BroadcastOnly:
    return emitOpError("rhs shape 对 lhs 需要广播——第 40 天起故意不支持"
                       "（第 60 天放行）");
  case mini::BiasKind::Mismatch:
    return emitOpError("两个操作数 shape 不匹配");
  }
  if (getRes().getType() != lhsT)
    return emitOpError("结果类型必须等于 lhs 类型");
  return success();
}

// 第 51 天的 fused_add_relu：规则与 mini.add 完全一致
LogicalResult mini::FusedAddReluOp::verify() {
  mlir::Type lhsT = getLhs().getType(), rhsT = getRhs().getType();
  auto lhs = lhsT.dyn_cast<mlir::RankedTensorType>();
  auto rhs = rhsT.dyn_cast<mlir::RankedTensorType>();
  if (!lhs || !rhs)
    return emitOpError("操作数必须是 ranked tensor");
  switch (classifyBias(rhsT, lhsT)) {
  case mini::BiasKind::Same:
    break;
  case mini::BiasKind::BroadcastOnly:
    return emitOpError("rhs shape 对 lhs 需要广播——第 40 天起故意不支持"
                       "（第 60 天放行）");
  case mini::BiasKind::Mismatch:
    return emitOpError("两个操作数 shape 不匹配");
  }
  if (getRes().getType() != lhsT)
    return emitOpError("结果类型必须等于 lhs 类型");
  return success();
}

LogicalResult mini::FusedMatmulBiasOp::verify() {
  if (failed(verifyMatmul2D(getOperation(), getLhs().getType(),
                            getRhs().getType(), getRes().getType())))
    return failure();
  return verifyBias(getOperation(), getBias().getType(), getRes().getType());
}

LogicalResult mini::FusedMatmulBiasReluOp::verify() {
  if (failed(verifyMatmul2D(getOperation(), getLhs().getType(),
                            getRhs().getType(), getRes().getType())))
    return failure();
  return verifyBias(getOperation(), getBias().getType(), getRes().getType());
}

// ===================== Fold：第 47 天口径，今天回归 =====================

// mini.constant 的 fold：递纸条。驱动向操作数定义者「要常量值」时，
// 把 value 属性原样奉还。这不是化简——上游 arith.constant 同款。
OpFoldResult mini::ConstantOp::fold(mini::ConstantOp::FoldAdaptor adaptor) {
  return getValue();
}

// mini.add 的 fold：常量碰常量，编译期把和算出来（第 47 天）。
// 尺寸护栏：元素个数超过 kMaxFoldElements 就拒绝——每折叠一次是
// O(N) 的编译期计算加一份属性拷贝，大张量不该在编译期展开。
static constexpr int64_t kMaxFoldElements = 1024;

OpFoldResult mini::AddOp::fold(mini::AddOp::FoldAdaptor adaptor) {
  // 匹配第一步：两个操作数都得带着常量属性进门。FoldAdaptor 里的属性
  // 是驱动收集的：操作数由 ConstantLike 的 op 定义才有，否则是空
  // Attribute（函数参数、别的算子的结果都算「非常量」）。
  DenseElementsAttr lhsAttr =
      dyn_cast_or_null<DenseElementsAttr>(adaptor.getLhs());
  DenseElementsAttr rhsAttr =
      dyn_cast_or_null<DenseElementsAttr>(adaptor.getRhs());
  if (!lhsAttr || !rhsAttr)
    return {}; // 有一个不是常量：无活可干，交回驱动

  // 类型护栏：结果类型与两个操作数完全一致才动手。Verifier 对动态维
  // 保守放行（?x2 与 2x2 记 Same），但物化出的常量类型跟着属性走
  // （静态），顶替一个 ?x2 的结果会让使用者类型对不上——折叠之后
  // IR 过不了验证（第 49 天第 6 节错误 1 的教训）。
  if (getRes().getType() != getLhs().getType() ||
      getRes().getType() != getRhs().getType())
    return {};

  // 尺寸护栏
  ShapedType resType = cast<ShapedType>(getRes().getType());
  if (resType.getNumElements() > kMaxFoldElements)
    return {};

  // 纯计算：逐元素 APFloat 加法，舍入模式 round to nearest, ties to
  // even——fold 出来的就是运行期会算出的同一个位模式。
  SmallVector<llvm::APFloat, 16> sum;
  sum.reserve(lhsAttr.getNumElements());
  for (auto [l, r] : llvm::zip_equal(lhsAttr.getValues<llvm::APFloat>(),
                                     rhsAttr.getValues<llvm::APFloat>())) {
    llvm::APFloat v = l;
    v.add(r, llvm::APFloat::rmNearestTiesToEven);
    sum.push_back(v);
  }

  // 把值交出去，节点交给驱动处理：它拿着这个属性调用
  // materializeConstant 物化出 mini.constant，再把 add 的使用者
  // 全部改指新常量、擦除 add。
  return DenseElementsAttr::get(resType, sum);
}
