add_mlir_dialect_library(MLIRMini
  AddFold.cpp
  AddVerifier.cpp
  AlgebraicSimplification.cpp
  CountOpsPass.cpp
  FusedAddReluVerifier.cpp
  FusedMatmulBiasReluVerifier.cpp
  MatmulVerifier.cpp
  MiniDialect.cpp
  MulVerifier.cpp
  ReluCanonicalization.cpp
  ReluVerifier.cpp
  ShapeInferencePass.cpp

  ADDITIONAL_HEADER_DIRS
  ${PROJECT_SOURCE_DIR}/include/mini

  DEPENDS
  MLIRMiniOpsIncGen

  LINK_LIBS PUBLIC
  MLIRFuncDialect
  MLIRIR
  MLIRPass
  )
