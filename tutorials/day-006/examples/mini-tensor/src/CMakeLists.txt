add_library(mini_tensor STATIC
    Buffer.cpp
    TensorDesc.cpp
    Tensor.cpp
)
target_include_directories(mini_tensor PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(mini-tensor main.cpp)
target_link_libraries(mini-tensor PRIVATE mini_tensor)
