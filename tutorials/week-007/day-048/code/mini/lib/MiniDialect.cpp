//===- MiniDialect.cpp - mini dialect ----------------------------*- C++ -*-===//
//
// 方言注册：把生成的算子类挂进 mini 的"户口本"，
// mini.matmul 从此能被解析和打印。
//
// 第 47 天新增：materializeConstant——常量物化钩子。fold 只返回
// "值"（Attribute），把值变回 IR 上一个真实 mini.constant 节点是
// 这个钩子的活。-canonicalize 的驱动（OperationFolder）折叠出属性
// 结果后，回头调用它；不实现这个钩子，fold 返回的属性没有落脚点，
// 折叠等于白算。
//
//===----------------------------------------------------------------------===//

#include "mlir/IR/OpImplementation.h" // OpAsmParser/OpAsmPrinter：assemblyFormat 生成代码的依赖

#include "mini/Dialect.h"
#include "mini/Ops.h"

using namespace mlir;
using namespace mini;

// MiniOpsDialect.cpp.inc：MiniDialect 构造函数／析构函数／TypeID 的定义。
// 漏掉它会在链接期报 undefined reference to `mini::MiniDialect::MiniDialect(...)`。
#include "mini/MiniOpsDialect.cpp.inc"

// MiniOps.cpp.inc：MatmulOp 的成员函数定义（parse/print/verify 等）。
// 必须先 #define GET_OP_CLASSES，否则 .inc 里的大块内容被预处理直接跳过，
// 链接期会报 undefined reference to `...TypeIDResolver<mini::MatmulOp...>::id`。
#define GET_OP_CLASSES
#include "mini/MiniOps.cpp.inc"

//===----------------------------------------------------------------------===//
// mini dialect 初始化。
//===----------------------------------------------------------------------===//

void MiniDialect::initialize() {
  addOperations<
#define GET_OP_LIST
#include "mini/MiniOps.cpp.inc"
      >();
}

//===----------------------------------------------------------------------===//
// 第 47 天：常量物化——把 fold 算出的属性变成图上的 mini.constant
//===----------------------------------------------------------------------===//

// 驱动（OperationFolder）在 mini.add 的 fold 返回 dense 属性后调用这里：
// 用给定的类型和属性造一个 mini.constant，返回它的 Operation*。
// 约定（见 Dialect.h 基类注释）：生成的 op 必须是"常量样"的——
// 单结果、零操作数、无副作用；mini.constant 天生满足（Pure +
// ConstantLike + AllTypesMatch 保证属性类型与结果类型一致）。
// 类型对不上时返回 nullptr 交还驱动（fold 的类型护栏已把这种情形
// 挡在前面，这里是双保险）。
Operation *MiniDialect::materializeConstant(OpBuilder &builder,
                                            Attribute value, Type type,
                                            Location loc) {
  auto dense = dyn_cast<DenseElementsAttr>(value);
  auto tensorType = dyn_cast<ShapedType>(type);
  if (!dense || !tensorType || dense.getType() != tensorType)
    return nullptr;
  return builder.create<mini::ConstantOp>(loc, tensorType, dense);
}
