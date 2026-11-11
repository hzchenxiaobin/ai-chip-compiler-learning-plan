# mini-tensor：第 6 天示例工程

最小 `Tensor` 类：`TensorDesc`（说明书）＋ `Buffer`（仓库）＋ 构造期配套检查，支持创建、读取、写入、移动和基本信息打印。构建环境：g++ 9.4.0（aarch64, Ubuntu 20.04）、CMake ≥ 3.16、Ninja。

## 目录

```text
mini-tensor/
├── CMakeLists.txt            # 默认 Debug 构建（-Wall -Wextra -Wpedantic）＋ ASan/UBSan 开关
├── src/
│   ├── Buffer.h/.cpp         # 字节仓库：unique_ptr<byte[]>，独占所有权
│   ├── TensorDesc.h/.cpp     # 第 4 天的说明书（补了默认构造和指针区间版 element_offset）
│   ├── Tensor.h/.cpp         # 今天的主体：desc + storage + check_fit + at
│   └── main.cpp              # 观察程序：创建/读写/边界/移动/换说明书/dtype/异常安全
├── tests/                    # test_tensor：53 条断言
└── bugs/                     # 单文件演示：个数不匹配、说明书装不进仓库、误用 moved-from
```

## 三种构建（同一份源码）

```bash
cmake -S . -B build      -G Ninja -DCMAKE_BUILD_TYPE=Debug && cmake --build build        # Debug
cmake -S . -B build-asan -G Ninja -DENABLE_ASAN=ON  && cmake --build build-asan          # ASan（含 LSan）
cmake -S . -B build-ubsan -G Ninja -DENABLE_UBSAN=ON && cmake --build build-ubsan        # UBSan
```

> 本机动态链接 libasan 会报 `ASan runtime does not come first in initial library list`，
> 因此 ASan 统一加 `-static-libasan`（见根 CMakeLists.txt）。

运行观察程序与测试：

```bash
./build/src/mini-tensor
ctest --test-dir build --output-on-failure
```

## bug 程序（在 `bugs/` 下单独用 g++ 编译）

```bash
cd bugs
SRC="../src/Buffer.cpp ../src/TensorDesc.cpp ../src/Tensor.cpp"

# 错误一：from_data 元素个数不匹配（构造期拒绝）
g++ -std=c++17 -g -I ../src $SRC err_count.cpp -o err_count && ./err_count

# 错误二：说明书装不进仓库（check_fit 拦截）
g++ -std=c++17 -g -I ../src $SRC err_bad_desc.cpp -o err_bad_desc && ./err_bad_desc

# 错误三：移动之后继续用源对象（两道防线，不再是 SEGV）
g++ -std=c++17 -g -I ../src $SRC err_moved_from.cpp -o err_moved_from && ./err_moved_from

# 三个程序都可以再跑一遍 ASan 版，确认零泄漏：
g++ -std=c++17 -g -I ../src $SRC err_moved_from.cpp -o err_asan -fsanitize=address -static-libasan && ./err_asan
```
