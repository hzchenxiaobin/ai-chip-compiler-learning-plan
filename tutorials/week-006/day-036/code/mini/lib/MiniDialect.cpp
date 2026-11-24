//===- MiniDialect.cpp - mini dialect ----------------------------*- C++ -*-===//
//
// 方言注册的"承重墙"：整个 mini 方言手写的 C++ 只有这十来行。
//
//===----------------------------------------------------------------------===//

#include "mini/Dialect.h"

using namespace mlir;

// MiniOpsDialect.cpp.inc：MiniDialect 构造函数／析构函数／TypeID 的定义。
// 漏掉这一行，链接期会报 undefined reference to `mini::MiniDialect::MiniDialect(...)`。
#include "mini/MiniOpsDialect.cpp.inc"

//===----------------------------------------------------------------------===//
// mini dialect 初始化：现在还没有算子，所以函数体是空的。
// Day 37 起，这里会陆续变成 addOperations<#define GET_OP_LIST ...>()。
//===----------------------------------------------------------------------===//

void mini::MiniDialect::initialize() {}
