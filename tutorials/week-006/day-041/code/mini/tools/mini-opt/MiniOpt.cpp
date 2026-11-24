//===- MiniOpt.cpp - mini-opt 入口 ---------------------------------*- C++ -*-===//
//
// mini-opt：能认识 mini 方言的 mlir-opt 复刻。
// 注册表里只放 mini 和 func 两家——第 35 天的结论在这里生效：
// 注册表决定谁能被解析。
//
// 第 41 天：注册"通用变换 Pass"。没有这一行，-cse / -canonicalize 这些
// 命令行选项根本不存在（Pass 和 Dialect 一样，谁注册谁可用）；
// 有了它，mini-opt 就从"只能 round-trip 打印"升级成
// "能跑 Pass 流水线的完整工具"。自定义 Pass 的注册见 lib/CountOpsPass.cpp
// （第 42 天复盘新增 mini.mul 时也不会再碰这个文件）。
//
//===----------------------------------------------------------------------===//

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/Dialect.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/Tools/mlir-opt/MlirOptMain.h"
#include "mlir/Transforms/Passes.h"

#include "mini/Dialect.h"
#include "mini/Ops.h"
#include "mini/Passes.h"

int main(int argc, char **argv) {
  mlir::DialectRegistry registry;
  // 注意命名空间：MiniDialect.td 里 cppNamespace = "::mini"，
  // 所以类名是 mini::MiniDialect，而不是 mlir::mini::MiniDialect。
  registry.insert<mini::MiniDialect,
                  mlir::func::FuncDialect>();

  // 第 41 天：把 CSE / Canonicalize 等通用变换 Pass 注册进全局 PassRegistry。
  // 注册的是"名字到 Pass 构造函数"的映射，命令行 -cse、-canonicalize
  // 由 MlirOptMain 的 PassPipelineCLParser 查这张表。
  mlir::registerTransformsPasses();

  // 第 41 天：注册第一个自定义 Pass —— mini-count-ops。
  // 自己写的 Pass 和上游 Pass 走同一张表、同一条命令行通道。
  mlir::mini::registerCountOpsPass();

  return mlir::asMainReturnCode(
      mlir::MlirOptMain(argc, argv, "mini dialect optimizer driver\n", registry));
}
