# 声明要求的最低 CMake 版本：低于 3.16 的 cmake 会直接报错拒绝配置（本机 3.20.5 满足）
cmake_minimum_required(VERSION 3.16)
# 定义工程名、声明只用 C++ 一种语言；CMake 在这一步探测并固定 C++ 编译器——
# 5.3 节第一行输出 “The CXX compiler identification is GNU 9.4.0” 就是它触发的
project(compiler-playground LANGUAGES CXX)

# 本目录及以下所有目标按 C++17 编译，效果等同 3.1 节手敲的 -std=c++17
set(CMAKE_CXX_STANDARD 17)
# 编译器不支持 C++17 时直接报错，而不是悄悄降级到旧标准“侥幸”通过
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# 关掉编译器私有扩展：g++ 会改用 -std=c++17 而不是 -std=gnu++17，代码不沾 GNU 方言
set(CMAKE_CXX_EXTENSIONS OFF)

# 统一警告档位：MSVC 用 /W4，其余编译器用 -Wall -Wextra -Wpedantic；
# 前两个与 3.1 节相同，-Wpedantic 额外对非标准扩展的写法发警告，只提醒、不阻断编译
if(MSVC)
  add_compile_options(/W4)
else()
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 把 src/ 纳入构建：CMake 接着读取 src/CMakeLists.txt，其中定义的目标成为工程的一部分
add_subdirectory(src)

# 打开 ctest 支持，只对当前目录及以下生效；必须放在顶层且在 add_subdirectory(tests)
# 之前，构建根目录才会生成 CTestTestfile.cmake，ctest 才收集得到测试（第 6 节错误三）
enable_testing()
add_subdirectory(tests)
