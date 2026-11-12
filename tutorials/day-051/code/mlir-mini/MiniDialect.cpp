#include "MiniDialect.h"

#include "mlir/IR/DialectImplementation.h"

// TableGen 生成：MiniDialect 构造函数、类型注册
#include "MiniDialect.cpp.inc"

// TableGen 生成：三个算子的 parse/print/verify/build 实现
#define GET_OP_CLASSES
#include "MiniOps.cpp.inc"

// 注册本 Dialect 的全部算子：解析器和 Pattern 驱动靠这里认识 mini.* 操作
void mini::MiniDialect::initialize() {
  addOperations<mini::AddOp, mini::ReluOp, mini::FusedAddReluOp>();
}
