add_executable(test_buffer test_buffer.cpp)
target_link_libraries(test_buffer PRIVATE buffer)

add_test(NAME buffer_lifetime COMMAND test_buffer)
