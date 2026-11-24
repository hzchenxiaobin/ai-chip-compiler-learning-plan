add_executable(test_ops test_ops.cpp)
target_link_libraries(test_ops PRIVATE mini_graph_v2)
add_test(NAME ops COMMAND test_ops)
