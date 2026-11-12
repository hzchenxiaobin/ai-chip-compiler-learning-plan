add_library(mini_graph_v3 STATIC
    Graph.cpp
    Interpreter.cpp
)
target_include_directories(mini_graph_v3 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(mini-graph-v3 main.cpp)
target_link_libraries(mini-graph-v3 PRIVATE mini_graph_v3)
