# 第 3 天示例：拷贝、移动与所有权

在 Day 002 的 `Buffer` 基础上做三件事：

1. 用 `= delete` 禁止拷贝构造和拷贝赋值（隐式浅拷贝会导致 double free，见 Day 002 错误二）；
2. 实现移动构造和移动赋值，交接资源后把原对象清空；
3. 对比移动前后资源的堆地址，确认"同一段内存换了主人"。

## 构建与运行

```bash
cmake -S . -B build -G Ninja
cmake --build build
./build/src/move-semantics
ctest --test-dir build --output-on-failure
```

环境：Linux aarch64（Ubuntu 20.04）· g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0。
