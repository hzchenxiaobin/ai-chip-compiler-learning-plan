add_mlir_dialect_library(MLIRMini
  MiniDialect.cpp

  ADDITIONAL_HEADER_DIRS
  ${PROJECT_SOURCE_DIR}/include/mini

  DEPENDS
  MLIRMiniDialectIncGen

  LINK_LIBS PUBLIC
  MLIRIR
  )
