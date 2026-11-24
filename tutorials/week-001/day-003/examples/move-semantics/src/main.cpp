#include "Buffer.h"
#include <cstdio>

int main() {
    std::printf("== 1. 移动构造：Buffer b = std::move(a) ==\n");
    unsigned char* addr_before = nullptr;
    {
        Buffer a(64, "a");
        a.at(0) = 0xAB;  // 在 a 的内存里写一个标记字节
        addr_before = a.data();
        std::printf("-- 移动前：a.data() = %p --\n", static_cast<void*>(addr_before));

        Buffer b = std::move(a);  // 移动构造：b 接管 a 的堆内存

        std::printf("-- 移动后：b.data() = %p --\n", static_cast<void*>(b.data()));
        std::printf("-- 移动后：a.data() = %p, a.size() = %zu --\n",
                    static_cast<void*>(a.data()), a.size());
        std::printf("-- b.at(0) = 0x%02X（数据跟着内存一起过来了）--\n", b.at(0));
        std::printf("-- 此时 alive = %d（a、b 两个对象都活着）--\n", Buffer::alive());

        std::printf("\n== 2. 移动赋值：c = std::move(b)，c 先退掉旧房子 ==\n");
        Buffer c(32, "c");
        unsigned char* c_old = c.data();
        c = std::move(b);  // 移动赋值：c 归还自己的 32 字节，再接管 b 的 64 字节
        std::printf("-- c 旧地址 %p 已归还，c 新地址 = %p（= b 原来的地址）--\n",
                    static_cast<void*>(c_old), static_cast<void*>(c.data()));
        std::printf("-- 移动后：b.data() = %p, b.size() = %zu --\n",
                    static_cast<void*>(b.data()), b.size());

        std::printf("\n== 3. 作用域结束：倒序析构，看谁归还多少字节 ==\n");
    }
    std::printf("-- 全部析构完，alive = %d --\n", Buffer::alive());
    (void)addr_before;
    return 0;
}
