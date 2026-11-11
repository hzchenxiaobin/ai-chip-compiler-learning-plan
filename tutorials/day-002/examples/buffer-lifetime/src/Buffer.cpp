#include "Buffer.h"

#include <cstdio>
#include <stdexcept>
#include <utility>

int Buffer::alive_ = 0;

Buffer::Buffer(std::size_t bytes, std::string name)
    : data_(new unsigned char[bytes]), size_(bytes), name_(std::move(name)) {
    ++alive_;
    std::printf("[ctor] Buffer \"%s\" 出生：在堆上拿到 %zu 字节 @ %p\n",
                name_.c_str(), size_, static_cast<void*>(data_));
}

Buffer::~Buffer() {
    --alive_;
    std::printf("[dtor] Buffer \"%s\" 销毁：归还堆上 %zu 字节\n",
                name_.c_str(), size_);
    delete[] data_;
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
