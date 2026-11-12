add_library(mini_graph_v5 STATIC
    Graph.cpp
    Interpreter.cpp
    Verifier.cpp
)
target_include_directories(mini_graph_v5 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(mini-graph-v5 main.cpp)
target_link_libraries(mini-graph-v5 PRIVATE mini_graph_v5)
