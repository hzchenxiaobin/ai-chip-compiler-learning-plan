add_library(greet STATIC greet.cpp)
target_include_directories(greet PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(compiler-playground main.cpp)
target_link_libraries(compiler-playground PRIVATE greet)
