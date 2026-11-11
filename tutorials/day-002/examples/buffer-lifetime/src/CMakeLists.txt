add_library(buffer STATIC Buffer.cpp)
target_include_directories(buffer PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(buffer-lifetime main.cpp)
target_link_libraries(buffer-lifetime PRIVATE buffer)
