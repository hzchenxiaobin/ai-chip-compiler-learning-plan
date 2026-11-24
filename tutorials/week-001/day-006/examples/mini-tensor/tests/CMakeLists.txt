add_executable(test_tensor test_tensor.cpp)
target_link_libraries(test_tensor PRIVATE mini_tensor)
add_test(NAME tensor COMMAND test_tensor)
