add_library(mini_graph_v7 STATIC
    Graph.cpp
    Interpreter.cpp
    Verifier.cpp
    Frontend.cpp
)
target_include_directories(mini_graph_v7 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(mini-graph-v7 main.cpp)
target_link_libraries(mini-graph-v7 PRIVATE mini_graph_v7)
