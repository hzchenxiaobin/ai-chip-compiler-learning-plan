#pragma once
#include <cstddef>
#include <string>

class Buffer {
public:
    explicit Buffer(std::size_t bytes, std::string name);
    ~Buffer();

    // 拷贝构造 / 拷贝赋值：禁止。
    // 隐式生成的版本只复制指针（浅拷贝），两个对象析构时会对同一块
    // 堆内存各 delete 一次（double free）。深拷贝虽然正确，但语义上
    // Buffer 是"独占资源"的类，我们不想让它悄悄复制一大段内存。
    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;

    // 移动构造 / 移动赋值：资源的所有权从 other 交接给 this。
    // noexcept 是移动操作的"标准姿势"，标准容器只对 noexcept 的移动
    // 放心（否则扩容时会退回拷贝以保证安全）。
    Buffer(Buffer&& other) noexcept;
    Buffer& operator=(Buffer&& other) noexcept;

    std::size_t size() const { return size_; }
    const std::string& name() const { return name_; }
    unsigned char* data() { return data_; }
    const unsigned char* data() const { return data_; }

    unsigned char& at(std::size_t i);  // 带边界检查的访问

    static int alive();  // 当前还活着的 Buffer 数量

private:
    unsigned char* data_;  // 指向堆上内存；nullptr 表示"手里没有资源"
    std::size_t size_;
    std::string name_;
    static int alive_;
};
