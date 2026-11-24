#pragma once
#include <cstddef>
#include <string>

// 第 2 天的最小 Buffer：记录构造 / 析构日志，观察对象生命周期。
// 注意：它持有裸指针，还没有处理拷贝和移动——那是第 3 天的主题。
class Buffer {
public:
    explicit Buffer(std::size_t bytes, std::string name);
    ~Buffer();

    std::size_t size() const { return size_; }
    const std::string& name() const { return name_; }
    unsigned char* data() { return data_; }
    const unsigned char* data() const { return data_; }

    unsigned char& at(std::size_t i);  // 带边界检查的访问

    static int alive();  // 当前还活着的 Buffer 数量

private:
    unsigned char* data_;  // 指向堆上内存
    std::size_t size_;
    std::string name_;
    static int alive_;
};
