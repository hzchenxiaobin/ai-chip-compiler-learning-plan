cmake_minimum_required(VERSION 3.16)
project(mini-graph-v6 CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif()

add_compile_options(-Wall -Wextra -Wpedantic)

# 两个 Sanitizer 开关：普通 Debug、ASan、UBSan 三种构建用同一份源码（同第 8～12 天）。
option(ENABLE_ASAN "用 AddressSanitizer（含 LeakSanitizer）构建" OFF)
option(ENABLE_UBSAN "用 UndefinedBehaviorSanitizer 构建" OFF)

if(ENABLE_ASAN)
    # 本机（Ubuntu 20.04, g++ 9.4, aarch64）动态链接 libasan 时会报
    # "ASan runtime does not come first in initial library list"，
    # 因此用 -static-libasan 把运行时静态链接进可执行文件。
    add_compile_options(-fsanitize=address -static-libasan -fno-omit-frame-pointer -g)
    add_link_options(-fsanitize=address -static-libasan)
endif()
if(ENABLE_UBSAN)
    add_compile_options(-fsanitize=undefined -fno-sanitize-recover=all -g)
    add_link_options(-fsanitize=undefined)
endif()

enable_testing()
add_subdirectory(src)
add_subdirectory(tests)
