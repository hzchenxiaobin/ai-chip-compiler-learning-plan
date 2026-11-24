add_mlir_dialect_library(MLIRMini
  MatmulVerifier.cpp
  MiniDialect.cpp

  ADDITIONAL_HEADER_DIRS
  ${PROJECT_SOURCE_DIR}/include/mini

  DEPENDS
  MLIRMiniOpsIncGen

  LINK_LIBS PUBLIC
  MLIRIR
  )
