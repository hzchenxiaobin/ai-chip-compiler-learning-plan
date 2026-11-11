add_executable(test_tensor test_tensor.cpp)
target_link_libraries(test_tensor PRIVATE mini_tensor)
add_test(NAME tensor COMMAND test_tensor)

add_executable(test_ops test_ops.cpp)
target_link_libraries(test_ops PRIVATE mini_tensor)
add_test(NAME ops COMMAND test_ops)
