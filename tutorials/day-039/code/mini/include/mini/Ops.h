//===- Ops.h - mini dialect ops ----------------------------------*- C++ -*-===//
//
// 算子类的声明头。MiniOps.h.inc 由 mlir-tblgen 根据 MiniOps.td 生成，
// 里面是 C++ 类 mini::MatmulOp / AddOp / ReluOp / ConstantOp 的完整声明。
//
// 第 38 天踩过的坑：MiniOps.td 里新用到 SameOperandsAndResultType 后，
// 生成的 .inc 引用了 mlir::InferTypeOpInterface，Ops.h 若不 include
// InferTypeOpInterface.h，编译会报
// "'InferTypeOpInterface' is not a member of 'mlir'"。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_OPS_H
#define MINI_OPS_H

#include "mlir/Bytecode/BytecodeOpInterface.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Dialect.h"
#include "mlir/IR/OpDefinition.h"
#include "mlir/Interfaces/InferTypeOpInterface.h"
#include "mlir/Interfaces/SideEffectInterfaces.h"

#define GET_OP_CLASSES
#include "mini/MiniOps.h.inc"

#endif // MINI_OPS_H
