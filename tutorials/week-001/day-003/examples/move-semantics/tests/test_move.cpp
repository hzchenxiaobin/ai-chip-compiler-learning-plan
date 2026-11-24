#include "Buffer.h"
#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <utility>

int main() {
    // --- 1. 移动构造：地址原封不动地换主人 ---
    {
        Buffer a(16, "a");
        unsigned char* addr = a.data();
        a.at(3) = 0x5A;  // 写一个标记字节，验证数据跟着内存走

        Buffer b = std::move(a);  // 移动构造
        assert(b.data() == addr);      // ① b 接管的正是 a 原来的堆地址
        assert(b.size() == 16);        // ② 大小一起交接
        assert(b.at(3) == 0x5A);       // ③ 内存没动过，内容原样
        assert(a.data() == nullptr);   // ④ 原主人被清空
        assert(a.size() == 0);         // ⑤ 尺寸归零

        // ⑥ 移动不减少对象总数：a（空壳）和 b 都还活着
        assert(Buffer::alive() == 2);
    }
    assert(Buffer::alive() == 0);      // ⑦ 离开作用域全部析构，账对得上

    // --- 2. 移动赋值：先归还旧资源，再接管新资源 ---
    {
        Buffer b(32, "b");
        unsigned char* b_addr = b.data();
        Buffer c(8, "c");
        unsigned char* c_old = c.data();

        c = std::move(b);  // 移动赋值
        assert(c.data() == b_addr);  // ⑧ c 的新地址 = b 原来的地址
        assert(c_old != c.data());   // ⑨ c 旧地址已不是它的
        assert(b.data() == nullptr); // ⑩ b 被清空
        assert(b.size() == 0);
    }
    assert(Buffer::alive() == 0);      // ⑪ 两段作用域都干净

    // --- 3. 使用被移空的对象：不会读到野数据，而是明确拦截 ---
    {
        Buffer a(4, "a");
        Buffer b = std::move(a);
        bool threw = false;
        try {
            a.at(0);  // a.size() == 0，任何下标都越界
        } catch (const std::out_of_range&) {
            threw = true;
        }
        assert(threw);                // ⑫ at() 用边界检查拦住了"用已移交的资源"
    }
    assert(Buffer::alive() == 0);      // ⑬

    // --- 4. 自我移动赋值：c = std::move(c) 不应自毁 ---
    {
        Buffer c(8, "c");
        unsigned char* addr = c.data();
        c.at(1) = 0x77;
        c = std::move(c);              // 借助 if (this != &other) 保护
        assert(c.data() == addr);       // ⑭ 资源还在自己手里
        assert(c.at(1) == 0x77);        // ⑮ 内容没丢
    }
    assert(Buffer::alive() == 0);      // ⑯

    // --- 5. 被移空的对象可以再接收新资源（可重新赋值状态） ---
    {
        Buffer a(4, "a");
        Buffer b = std::move(a);
        a = Buffer(12, "fresh");  // 移动赋值接收一个临时对象
        assert(a.size() == 12);         // ⑰ a 重新持有了新资源
        assert(a.data() != nullptr);
        assert(b.size() == 4);          // ⑱ b 的资源不受影响
    }
    assert(Buffer::alive() == 0);      // ⑲

    std::printf("all 19 assertions passed\n");
    return 0;
}
