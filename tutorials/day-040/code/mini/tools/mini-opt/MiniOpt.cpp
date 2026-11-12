//===- MiniOpt.cpp - mini-opt 入口 ---------------------------------*- C++ -*-===//
//
// mini-opt：能认识 mini 方言的 mlir-opt 复刻。
// 注册表里只放 mini 和 func 两家——第 35 天的结论在这里生效：
// 注册表决定谁能被解析。
//
//===----------------------------------------------------------------------===//

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/Dialect.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/Tools/mlir-opt/MlirOptMain.h"

#include "mini/Dialect.h"
#include "mini/Ops.h"

int main(int argc, char **argv) {
  mlir::DialectRegistry registry;
  // 注意命名空间：MiniDialect.td 里 cppNamespace = "::mini"，
  // 所以类名是 mini::MiniDialect，而不是 mlir::mini::MiniDialect。
  registry.insert<mini::MiniDialect,
                  mlir::func::FuncDialect>();

  return mlir::asMainReturnCode(
      mlir::MlirOptMain(argc, argv, "mini dialect optimizer driver\n", registry));
}
