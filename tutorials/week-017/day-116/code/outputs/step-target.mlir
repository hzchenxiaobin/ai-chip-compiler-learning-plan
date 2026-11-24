llvm.func @step(%i: i64, %k: i64) -> i64 {
  %c2 = llvm.mlir.constant(2 : i64) : i64
  %s = llvm.add %i, %k : i64
  %p = llvm.mul %s, %c2 : i64
  llvm.return %p : i64
}

// 运行库符号：真实 MLIR 由 MemRefToLLVM 自动声明 malloc
llvm.func @malloc(i64) -> !llvm.ptr
