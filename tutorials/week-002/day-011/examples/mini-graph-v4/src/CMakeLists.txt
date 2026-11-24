add_library(mini_graph_v4 STATIC
    Graph.cpp
    Interpreter.cpp
    bench.cpp
)
target_include_directories(mini_graph_v4 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(mini-graph-v4 main.cpp)
target_link_libraries(mini-graph-v4 PRIVATE mini_graph_v4)
