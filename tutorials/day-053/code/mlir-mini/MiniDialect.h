#ifndef MINI_DIALECT_H
#define MINI_DIALECT_H

#include "mlir/IR/Builders.h"
#include "mlir/IR/Dialect.h"
#include "mlir/IR/OpDefinition.h"
#include "mlir/IR/OpImplementation.h"
// SameOperandsAndResultType trait 会为算子挂上 InferTypeOpInterface，
// 因此这里需要它的头文件
#include "mlir/Interfaces/InferTypeOpInterface.h"

// TableGen 生成：MiniDialect 类声明
#include "MiniDialect.h.inc"

// TableGen 生成：五个 Operation 的完整类声明（需要先打开 GET_OP_CLASSES 开关）
#define GET_OP_CLASSES
#include "MiniOps.h.inc"

#endif // MINI_DIALECT_H
