add_executable(test_use_def test_use_def.cpp)
target_link_libraries(test_use_def PRIVATE mini_graph_v4)
add_test(NAME use_def COMMAND test_use_def)

add_executable(test_visitor test_visitor.cpp)
target_link_libraries(test_visitor PRIVATE mini_graph_v4)
add_test(NAME visitor COMMAND test_visitor)
