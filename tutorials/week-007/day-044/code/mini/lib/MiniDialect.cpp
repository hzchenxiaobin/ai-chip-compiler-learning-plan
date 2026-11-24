//===- MiniDialect.cpp - mini dialect ----------------------------*- C++ -*-===//
//
// 方言注册：把生成的算子类挂进 mini 的"户口本"，
// mini.matmul 从此能被解析和打印。
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
