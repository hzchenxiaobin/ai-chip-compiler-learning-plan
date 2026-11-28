# 把 greet.cpp 编成静态库，Linux 上产物名固定是 libgreet.a（5.3 节 [2/6] 生成的那件
# 东西）；STATIC 表示用 ar 把 .o 归档打包，对应图 2 的中间步骤
add_library(greet STATIC greet.cpp)
# 把本文件所在目录（即 src/）加入头文件搜索路径；PUBLIC 表示“自己和链接我的目标都能
# 用”，所以 main.cpp、test_greet.cpp 可以直接写 #include "greet.h"，不用带 src/ 前缀
target_include_directories(greet PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# 把 main.cpp 编译成可执行文件 compiler-playground
add_executable(compiler-playground main.cpp)
# 链接 libgreet.a——第 3.2 节的“符号接线”由这行触发，漏了它就是第 6 节错误一的
# undefined reference；PRIVATE 表示只供自己链接、不向下游传播，与上一行 PUBLIC 恰成对照
target_link_libraries(compiler-playground PRIVATE greet)
