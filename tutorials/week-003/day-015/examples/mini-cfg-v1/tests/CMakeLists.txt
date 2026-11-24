add_executable(test_cfg test_cfg.cpp)
target_link_libraries(test_cfg PRIVATE mini_cfg_v1)
add_test(NAME cfg COMMAND test_cfg)
