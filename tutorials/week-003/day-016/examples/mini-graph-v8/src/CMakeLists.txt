add_library(mini_graph_v8 STATIC
    Graph.cpp
    Interpreter.cpp
    Verifier.cpp
    Frontend.cpp
    TopoSort.cpp
)
target_include_directories(mini_graph_v8 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(mini-graph-v8 main.cpp)
target_link_libraries(mini-graph-v8 PRIVATE mini_graph_v8)
