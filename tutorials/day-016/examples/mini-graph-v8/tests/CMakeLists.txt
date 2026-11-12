add_executable(test_use_def test_use_def.cpp)
target_link_libraries(test_use_def PRIVATE mini_graph_v8)
add_test(NAME use_def COMMAND test_use_def)

add_executable(test_visitor test_visitor.cpp)
target_link_libraries(test_visitor PRIVATE mini_graph_v8)
add_test(NAME visitor COMMAND test_visitor)

add_executable(test_verifier test_verifier.cpp)
target_link_libraries(test_verifier PRIVATE mini_graph_v8)
add_test(NAME verifier COMMAND test_verifier)

add_executable(test_frontend test_frontend.cpp)
target_link_libraries(test_frontend PRIVATE mini_graph_v8)
add_test(NAME frontend COMMAND test_frontend)

add_executable(test_mul test_mul.cpp)
target_link_libraries(test_mul PRIVATE mini_graph_v8)
add_test(NAME mul COMMAND test_mul)

add_executable(test_toposort test_toposort.cpp)
target_link_libraries(test_toposort PRIVATE mini_graph_v8)
add_test(NAME toposort COMMAND test_toposort)
