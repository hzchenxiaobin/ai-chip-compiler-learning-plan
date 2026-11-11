add_library(mini_graph STATIC
    Graph.cpp
)
target_include_directories(mini_graph PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(mini-graph main.cpp)
target_link_libraries(mini-graph PRIVATE mini_graph)
