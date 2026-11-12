//===- Ops.h - mini dialect ops ----------------------------------*- C++ -*-===//
//
// 第 37 天新增：算子类的声明头。
// MiniOps.h.inc 由 mlir-tblgen 根据 MiniOps.td（今天的核心文件）生成，
// 里面就是 C++ 类 mini::MatmulOp 的完整声明。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_OPS_H
#define MINI_OPS_H

#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Dialect.h"
#include "mlir/IR/OpDefinition.h"
#include "mlir/Interfaces/SideEffectInterfaces.h"

#define GET_OP_CLASSES
#include "mini/MiniOps.h.inc"

#endif // MINI_OPS_H
