llvm_canonicalize_cmake_booleans(
        MLIR_ENABLE_BINDINGS_PYTHON
)

configure_lit_site_cfg(
        ${CMAKE_CURRENT_SOURCE_DIR}/lit.site.cfg.py.in
        ${CMAKE_CURRENT_BINARY_DIR}/lit.site.cfg.py
        MAIN_CONFIG
        ${CMAKE_CURRENT_SOURCE_DIR}/lit.cfg.py
)

set(STANDALONE_TEST_DEPENDS
        FileCheck count not
        standalone-opt
        standalone-translate
        StandalonePlugin
        )
if(MLIR_ENABLE_BINDINGS_PYTHON)
  list(APPEND STANDALONE_TEST_DEPENDS StandalonePythonModules)
endif()

add_lit_testsuite(check-standalone "Running the standalone regression tests"
        ${CMAKE_CURRENT_BINARY_DIR}
        DEPENDS ${STANDALONE_TEST_DEPENDS}
        )
set_target_properties(check-standalone PROPERTIES FOLDER "Tests")

add_lit_testsuites(STANDALONE ${CMAKE_CURRENT_SOURCE_DIR} DEPENDS ${STANDALONE_TEST_DEPENDS})

# NOTE(ubuntu-distro): CAPI 测试需要 MLIR_INSTALL_AGGREGATE_OBJECTS 聚合目标，
# Ubuntu 官方包未安装这些聚合对象，本环境跳过该子目录。
# add_subdirectory(CAPI)
