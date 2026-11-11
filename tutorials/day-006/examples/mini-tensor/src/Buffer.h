#pragma once
#include <cstddef>
#include <memory>

// 第 6 天的 Buffer：只负责「这块堆内存归谁管」，按字节持有，不解释内容。
// 血统：第 2 天的 Buffer 用裸 new[]/delete[] 手写 RAII（还带日志）；
//       第 5 天把所有权纪律装进 unique_ptr；今天把它变成字节仓库，
//       配合 TensorDesc 解释成任意 Dtype。
// 由此自动获得（都是 unique_ptr 成员带来的，第 5 天 3.2 节的账）：
//   1) 拷贝构造 / 拷贝赋值被删除——两个仓库不能共用同一块堆内存；
//   2) 移动构造 / 移动赋值自动生成且正确——源仓库变空；
//   3) 析构自动 delete[]——不泄漏。
class Buffer {
public:
    Buffer() = default;

    // 分配 nbytes 字节并清零（make_unique<std::byte[]> 数值初始化）。
    // nbytes 允许为 0：拿到一个合法但空的仓库，empty() 仍为 false，
    // 这样「零元素张量」和「moved-from 空壳」就能区分开。
    explicit Buffer(std::size_t nbytes);

    std::byte* data() { return bytes_.get(); }
    const std::byte* data() const { return bytes_.get(); }

    std::size_t size() const { return size_; }  // 单位：字节
    bool empty() const { return bytes_ == nullptr; }

private:
    std::unique_ptr<std::byte[]> bytes_;  // 独占所有权
    std::size_t size_ = 0;
};
