add_mlir_dialect_library(MLIRMini
  AddVerifier.cpp
  CountOpsPass.cpp
  MatmulVerifier.cpp
  MiniDialect.cpp
  ReluVerifier.cpp

  ADDITIONAL_HEADER_DIRS
  ${PROJECT_SOURCE_DIR}/include/mini

  DEPENDS
  MLIRMiniOpsIncGen

  LINK_LIBS PUBLIC
  MLIRFuncDialect
  MLIRIR
  MLIRPass
  )
