add_executable(test_use_def test_use_def.cpp)
target_link_libraries(test_use_def PRIVATE mini_graph_v3)
add_test(NAME use_def COMMAND test_use_def)
