# smart-tensor：第 5 天示例工程

`unique_ptr` 版 `Tensor` 初版 + 一组故意翻车的 bug 程序。构建环境：g++ 9.4.0（aarch64, Ubuntu 20.04）、CMake ≥ 3.16、Ninja。

## 目录

```text
smart-tensor/
├── CMakeLists.txt            # 含 ENABLE_ASAN / ENABLE_UBSAN 两个开关
├── src/                      # Tensor 初版（unique_ptr<float[]>）+ 观察程序
├── tests/                    # test_tensor：16 条断言
└── bugs/                     # 单文件演示：故意越界、泄漏、溢出、UAF 与修复版
```

## 三种构建

```bash
cmake -S . -B build      -G Ninja && cmake --build build       # 普通 Debug
cmake -S . -B build-asan -G Ninja -DENABLE_ASAN=ON && cmake --build build-asan   # ASan（含 LSan）
cmake -S . -B build-ubsan -G Ninja -DENABLE_UBSAN=ON && cmake --build build-ubsan # UBSan
```

> 本机动态链接 libasan 会报 `ASan runtime does not come first in initial library list`，
> 因此 ASan 统一加 `-static-libasan`（见根 CMakeLists.txt）。

运行观察程序与测试：

```bash
./build/src/smart-tensor
ctest --test-dir build --output-on-failure
```

## bug 程序（在 `bugs/` 下单独用 g++ 编译）

```bash
cd bugs
# 越界：先无检查（静默通过），再上 ASan（被抓），最后看修复版
g++ -std=c++17 -g -I ../src ../src/Tensor.cpp bug_oob.cpp        -o oob_plain
g++ -std=c++17 -g -I ../src ../src/Tensor.cpp bug_oob.cpp        -o oob_asan -fsanitize=address -static-libasan
g++ -std=c++17 -g -I ../src ../src/Tensor.cpp bug_oob_fixed.cpp -o oob_fixed_asan -fsanitize=address -static-libasan
./oob_plain; ./oob_asan; ./oob_fixed_asan

# 泄漏（LeakSanitizer）、use-after-free、移动后误用源：同样加 ASan
# 有符号溢出：UBSan
g++ -std=c++17 -g -fsanitize=undefined -fno-sanitize-recover=all bug_overflow.cpp -o overflow && ./overflow

# 5.4 节对照实验：越界距离可调（k = 6 / 1000 / 100000）
g++ -std=c++17 -g -I ../src ../src/Tensor.cpp exp_oob_far.cpp -o exp_plain
g++ -std=c++17 -g -I ../src ../src/Tensor.cpp exp_oob_far.cpp -o exp_asan -fsanitize=address -static-libasan
./exp_plain 6; ./exp_asan 6; ./exp_plain 100000

# 3.3 节 shared_ptr 引用计数演示
g++ -std=c++17 -g -I ../src ../src/Tensor.cpp exp_shared.cpp -o exp_shared && ./exp_shared
```

错误一（拷贝 Tensor）是编译期错误，不需要运行：

```bash
g++ -std=c++17 -I ../src -c err_copy.cpp -o /dev/null    # 编译即失败
```
