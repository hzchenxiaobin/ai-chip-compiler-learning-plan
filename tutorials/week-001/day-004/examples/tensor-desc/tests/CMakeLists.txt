add_executable(test_tensor_desc test_tensor_desc.cpp)
target_link_libraries(test_tensor_desc PRIVATE tensor_desc)

add_test(NAME tensor_desc COMMAND test_tensor_desc)
