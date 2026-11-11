#include "Buffer.h"

#include <cstdio>
#include <stdexcept>
#include <utility>

int Buffer::alive_ = 0;

Buffer::Buffer(std::size_t bytes, std::string name)
    : data_(new unsigned char[bytes]), size_(bytes), name_(std::move(name)) {
    ++alive_;
    std::printf("[ctor]       Buffer \"%s\" 出生：在堆上拿到 %zu 字节 @ %p\n",
                name_.c_str(), size_, static_cast<void*>(data_));
}

Buffer::~Buffer() {
    --alive_;
    std::printf("[dtor]       Buffer \"%s\" 销毁：归还堆上 %zu 字节%s\n",
                name_.c_str(), size_, data_ ? "" : "（本来就是空的，没事）");
    delete[] data_;
}

// 移动构造：新对象直接接管 other 的指针，然后把 other 清空。
// 全程没有 new、没有 memcpy——移动的"便宜"就便宜在这里。
Buffer::Buffer(Buffer&& other) noexcept
    : data_(other.data_), size_(other.size_), name_(std::move(other.name_)) {
    other.data_ = nullptr;  // 关键一步：不置空，两个析构函数会 delete 同一块内存
    other.size_ = 0;
    ++alive_;
    std::printf("[move-ctor]  Buffer \"%s\" 接管 %zu 字节 @ %p，原主人已清空\n",
                name_.c_str(), size_, static_cast<void*>(data_));
}

// 移动赋值：目标是"已存在"的对象，先归还自己手里的资源，再接管 other 的。
Buffer& Buffer::operator=(Buffer&& other) noexcept {
    if (this != &other) {  // 防 c = std::move(c)：自己交接给自己等于原地自毁
        std::printf("[move-assign] Buffer \"%s\" 先归还旧资源 %zu 字节，",
                    name_.c_str(), size_);
        delete[] data_;  // 不做这一步，自己原来的内存就泄漏了
        data_ = other.data_;
        size_ = other.size_;
        name_ = std::move(other.name_);
        other.data_ = nullptr;
        other.size_ = 0;
        std::printf("再接管 Buffer 的新资源 %zu 字节 @ %p\n",
                    size_, static_cast<void*>(data_));
    }
    return *this;
}

unsigned char& Buffer::at(std::size_t i) {
    if (i >= size_) {
        throw std::out_of_range("Buffer \"" + name_ + "\": index " +
                                std::to_string(i) + " out of range for size " +
                                std::to_string(size_));
    }
    return data_[i];
}

int Buffer::alive() { return alive_; }
