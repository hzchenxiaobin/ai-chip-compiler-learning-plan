add_library(mini_cfg_v1 STATIC
    Cfg.cpp
    Interpreter.cpp
)
target_include_directories(mini_cfg_v1 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(mini-cfg-v1 main.cpp)
target_link_libraries(mini-cfg-v1 PRIVATE mini_cfg_v1)
