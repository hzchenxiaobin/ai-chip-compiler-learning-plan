//===- MiniOpt.cpp - mini-opt 入口 ---------------------------------*- C++ -*-===//
//
// mini-opt：一个只认识 mini 和 func 两家方言的"迷你 mlir-opt"。
// MlirOptMain 提供解析、验证、打印和命令行框架——我们只负责往注册表里
// 放住户：mini（今天新建的空户口本）和 func（函数容器，测试要用）。
//
//===----------------------------------------------------------------------===//

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/Dialect.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/Tools/mlir-opt/MlirOptMain.h"

#include "mini/Dialect.h"

int main(int argc, char **argv) {
  mlir::DialectRegistry registry;
  // 注意命名空间：MiniDialect.td 里 cppNamespace = "::mini"，
  // 所以类名是 mini::MiniDialect，而不是 mlir::mini::MiniDialect。
  registry.insert<mini::MiniDialect,
                  mlir::func::FuncDialect>();

  return mlir::asMainReturnCode(
      mlir::MlirOptMain(argc, argv, "mini dialect optimizer driver\n", registry));
}
