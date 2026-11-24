# 第 4 天示例：TensorDesc（Shape / Stride / Dtype）

设计 Tensor 的"取数说明书"：只记录元信息（shape、strides、storage_offset、dtype），不拥有任何数据。实现：

1. `numel()` 元素数、`nbytes()` 字节数（numel × itemsize）；
2. `element_offset()` / `byte_offset()`：多维下标 → 底层存储位置的换算；
3. `is_contiguous()`：行主序连续判断（从最后一维倒序累乘期望步长，尺寸为 1 的维度跳过）；
4. `make_contiguous()` 工厂：按行主序推导 strides。

stride 以**元素**为单位（同 PyTorch、MLIR MemRef；NumPy 的 `strides` 属性是字节）。

## 构建与运行

```bash
cmake -S . -B build -G Ninja
cmake --build build
./build/src/tensor-desc
ctest --test-dir build --output-on-failure
```

环境：Linux aarch64（Ubuntu 20.04）· g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0。
