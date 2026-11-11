add_executable(test_greet test_greet.cpp)
target_link_libraries(test_greet PRIVATE greet)

add_test(NAME greet_returns_greeting COMMAND test_greet)
