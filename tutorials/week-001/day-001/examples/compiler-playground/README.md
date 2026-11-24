# compiler-playground

AI 芯片编译器学习计划的宿主工程：从第 1 天的空骨架开始，后续 167 天的
IR、Pass、Lowering 和测试都长在这个目录里。

## 环境

| 工具 | 本机验证版本 |
|---|---|
| CMake | 3.20.5 |
| Ninja | 1.10.0 |
| g++ | 9.4.0 (Ubuntu 20.04, aarch64) |

安装依赖（Ubuntu/Debian）：

```bash
sudo apt-get install -y cmake ninja-build g++
```

## 构建、运行与测试

```bash
cmake -S . -B build -G Ninja
cmake --build build
./build/src/compiler-playground
ctest --test-dir build --output-on-failure
```

## 目录约定

```text
CMakeLists.txt   顶层配置：C++17、警告选项、测试开关
src/             库与可执行程序
tests/           单元测试，由 ctest 统一调度
build/           构建产物，不入库（可随时删除重建）
```
