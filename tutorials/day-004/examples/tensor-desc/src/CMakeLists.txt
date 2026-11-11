add_library(tensor_desc STATIC TensorDesc.cpp)
target_include_directories(tensor_desc PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(tensor-desc main.cpp)
target_link_libraries(tensor-desc PRIVATE tensor_desc)
