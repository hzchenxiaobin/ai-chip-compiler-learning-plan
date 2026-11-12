//===- Ops.h - mini dialect ops ----------------------------------*- C++ -*-===//
//
// 算子类的声明头。MiniOps.h.inc 由 mlir-tblgen 根据 MiniOps.td 生成，
// 里面是 C++ 类 mini::MatmulOp / AddOp / ReluOp / ConstantOp 的完整声明。
//
// 第 38 天踩过的坑：MiniOps.td 里新用到 SameOperandsAndResultType 后，
// 生成的 .inc 引用了 mlir::InferTypeOpInterface，Ops.h 若不 include
// InferTypeOpInterface.h，编译会报
// "'InferTypeOpInterface' is not a member of 'mlir'"。
// 第 40 天摘掉该 trait 后试着直接删掉这个 include，编译却在
// MiniOps.cpp.inc 报 'mlir::Builder' incomplete type——原来它还顺手
// （传递地）提供了 Builders.h，mini.constant 的属性代码需要 Builder。
// 正确做法不是恢复旧 include，而是把真正需要的头摆到明面上：
//   #include "mlir/IR/Builders.h"
// 摘 trait 是三处联动：.td 的 trait 列表、.td 的 include、这里的 include
// （外加一次"传递依赖现形"的编译错误）。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_OPS_H
#define MINI_OPS_H

#include "mlir/Bytecode/BytecodeOpInterface.h"
#include "mlir/IR/Builders.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Dialect.h"
#include "mlir/IR/OpDefinition.h"
#include "mlir/Interfaces/SideEffectInterfaces.h"

#define GET_OP_CLASSES
#include "mini/MiniOps.h.inc"

#endif // MINI_OPS_H
