#include "Buffer.h"
#include <cassert>
#include <cstdio>
#include <stdexcept>

int main() {
    // 1) 基本读写与析构：作用域结束后必然已销毁
    {
        Buffer b(8, "t0");
        assert(b.size() == 8);
        assert(b.data() != nullptr);
        b.at(0) = 0x11;
        b.at(7) = 0x22;
        assert(b.at(0) == 0x11);
        assert(b.at(7) == 0x22);
    }
    assert(Buffer::alive() == 0);

    // 2) 嵌套作用域：alive 计数随进入 / 离开作用域增减（LIFO）
    {
        Buffer x(4, "x");
        assert(Buffer::alive() == 1);
        {
            Buffer y(4, "y");
            assert(Buffer::alive() == 2);
        }
        assert(Buffer::alive() == 1);
    }
    assert(Buffer::alive() == 0);

    // 3) 越界访问必须被拦下
    bool threw = false;
    {
        Buffer b(4, "t1");
        try {
            b.at(4);
        } catch (const std::out_of_range&) {
            threw = true;
        }
    }
    assert(threw);

    // 4) 0 字节的 Buffer 也应能正常出生和销毁
    {
        Buffer z(0, "z");
        assert(z.size() == 0);
    }
    assert(Buffer::alive() == 0);

    std::printf("all 12 assertions passed\n");
    return 0;
}
