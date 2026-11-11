add_executable(test_move test_move.cpp)
target_link_libraries(test_move PRIVATE buffer)

add_test(NAME move_semantics COMMAND test_move)
