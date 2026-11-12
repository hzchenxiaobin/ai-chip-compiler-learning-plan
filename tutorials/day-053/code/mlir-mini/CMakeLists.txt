cmake_minimum_required(VERSION 3.20)
project(mini-fuse-bias CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(MLIR REQUIRED CONFIG)

# 定位 mlir-tblgen：优先 PATH，其次常见安装前缀
find_program(MLIR_TBLGEN_DOC mlir-tblgen HINTS ${LLVM_TOOLS_BINARY_DIR})
if(NOT MLIR_TBLGEN_DOC)
  find_program(MLIR_TBLGEN_DOC mlir-tblgen HINTS /usr/lib/llvm-18/bin)
endif()
set(MLIR_TBLGEN ${MLIR_TBLGEN_DOC} CACHE FILEPATH "mlir-tblgen 路径")

set(GEN_DIR ${CMAKE_BINARY_DIR}/gen)
file(MAKE_DIRECTORY ${GEN_DIR})

set(TD_FILE ${CMAKE_CURRENT_SOURCE_DIR}/MiniOps.td)

add_custom_command(
  OUTPUT ${GEN_DIR}/MiniDialect.h.inc
  COMMAND ${MLIR_TBLGEN} -gen-dialect-decls ${TD_FILE} -I ${MLIR_INCLUDE_DIRS} -o ${GEN_DIR}/MiniDialect.h.inc
  DEPENDS ${TD_FILE}
  COMMENT "mlir-tblgen: MiniDialect.h.inc")
add_custom_command(
  OUTPUT ${GEN_DIR}/MiniDialect.cpp.inc
  COMMAND ${MLIR_TBLGEN} -gen-dialect-defs ${TD_FILE} -I ${MLIR_INCLUDE_DIRS} -o ${GEN_DIR}/MiniDialect.cpp.inc
  DEPENDS ${TD_FILE}
  COMMENT "mlir-tblgen: MiniDialect.cpp.inc")
add_custom_command(
  OUTPUT ${GEN_DIR}/MiniOps.h.inc
  COMMAND ${MLIR_TBLGEN} -gen-op-decls ${TD_FILE} -I ${MLIR_INCLUDE_DIRS} -o ${GEN_DIR}/MiniOps.h.inc
  DEPENDS ${TD_FILE}
  COMMENT "mlir-tblgen: MiniOps.h.inc")
add_custom_command(
  OUTPUT ${GEN_DIR}/MiniOps.cpp.inc
  COMMAND ${MLIR_TBLGEN} -gen-op-defs ${TD_FILE} -I ${MLIR_INCLUDE_DIRS} -o ${GEN_DIR}/MiniOps.cpp.inc
  DEPENDS ${TD_FILE}
  COMMENT "mlir-tblgen: MiniOps.cpp.inc")

add_custom_target(MiniGen DEPENDS
  ${GEN_DIR}/MiniDialect.h.inc ${GEN_DIR}/MiniDialect.cpp.inc
  ${GEN_DIR}/MiniOps.h.inc ${GEN_DIR}/MiniOps.cpp.inc)

add_library(MiniDialectLib STATIC ${CMAKE_CURRENT_SOURCE_DIR}/MiniDialect.cpp)
add_dependencies(MiniDialectLib MiniGen)
target_include_directories(MiniDialectLib SYSTEM PUBLIC
  ${LLVM_INCLUDE_DIRS} ${MLIR_INCLUDE_DIRS} ${GEN_DIR})
target_link_libraries(MiniDialectLib PUBLIC MLIRIR MLIRSupport)

add_executable(mini-fuse-bias mini-fuse-bias.cpp)
add_dependencies(mini-fuse-bias MiniGen)
target_link_libraries(mini-fuse-bias PRIVATE
  MiniDialectLib
  MLIRIR
  MLIRParser
  MLIRFuncDialect
  MLIRFunctionInterfaces
  MLIRRewrite
  MLIRTransforms
  MLIRAnalysis
  MLIRSupport
  LLVMSupport)
