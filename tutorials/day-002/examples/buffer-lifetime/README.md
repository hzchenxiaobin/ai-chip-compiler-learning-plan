# buffer-lifetime（第 2 天示例工程）

记录构造 / 析构日志的 `Buffer` 类，用于观察对象生命周期与 RAII。

环境：Linux aarch64（Ubuntu 20.04）· g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0

构建与运行：

```bash
cmake -S . -B build -G Ninja
cmake --build build
./build/src/buffer-lifetime   # 观察三段作用域的构造/析构日志
ctest --test-dir build        # 12 条断言
```

教程第 6 节的三个错误复现（泄漏 / double free / 悬垂指针）使用独立单文件程序，
不包含在本工程里，命令见教程正文。
