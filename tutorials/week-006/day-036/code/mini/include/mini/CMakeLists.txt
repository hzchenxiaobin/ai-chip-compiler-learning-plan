# Day 36：方言还没有算子，暂时没有 MiniOps.td，
# 所以不走 add_mlir_dialect(MiniOps mini)（它以 MiniOps.td 为 TableGen 入口），
# 而是对 MiniDialect.td 直接生成方言本体的声明和定义。
# 生成的文件名沿用 MiniOps 前缀，与 add_mlir_dialect 的命名惯例一致——
# 明天（Day 37）MiniOps.td 出现后，这四行可以原样换成一行
#   add_mlir_dialect(MiniOps mini)
# 生成的文件名不变，Dialect.h / MiniDialect.cpp 一行都不用改。

set(LLVM_TARGET_DEFINITIONS MiniDialect.td)
mlir_tablegen(MiniOpsDialect.h.inc -gen-dialect-decls -dialect=mini)
mlir_tablegen(MiniOpsDialect.cpp.inc -gen-dialect-defs -dialect=mini)
add_public_tablegen_target(MLIRMiniDialectIncGen)
