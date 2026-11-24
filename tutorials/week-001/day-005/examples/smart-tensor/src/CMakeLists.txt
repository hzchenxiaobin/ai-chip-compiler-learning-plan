add_library(smart_tensor STATIC Tensor.cpp)
target_include_directories(smart_tensor PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(smart-tensor main.cpp)
target_link_libraries(smart-tensor PRIVATE smart_tensor)
