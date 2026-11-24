add_executable(test_graph test_graph.cpp)
target_link_libraries(test_graph PRIVATE mini_graph)
add_test(NAME graph COMMAND test_graph)
