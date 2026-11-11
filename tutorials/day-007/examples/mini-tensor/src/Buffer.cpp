#include "Buffer.h"

Buffer::Buffer(std::size_t nbytes)
    : bytes_(std::make_unique<std::byte[]>(nbytes)),  // 全部清零
      size_(nbytes) {}
