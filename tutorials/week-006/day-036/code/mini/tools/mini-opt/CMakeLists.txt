get_property(dialect_libs GLOBAL PROPERTY MLIR_DIALECT_LIBS)
set(LIBS
  ${dialect_libs}
  MLIRFuncDialect
  MLIROptLib
  MLIRMini
  )
add_llvm_executable(mini-opt MiniOpt.cpp)

llvm_update_compile_flags(mini-opt)
target_link_libraries(mini-opt PRIVATE ${LIBS})
