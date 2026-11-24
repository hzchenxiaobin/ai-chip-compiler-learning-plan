#include "Buffer.h"
#include <cstdio>

int main() {
    std::printf("== 1. 栈对象：作用域结束自动销毁 ==\n");
    {
        Buffer a(16, "a");
        Buffer b(32, "b");
        a.at(0) = 1;
        b.at(0) = 2;
        std::printf("-- a、b 都活着，alive = %d --\n", Buffer::alive());
    }
    std::printf("-- 离开作用域，alive = %d --\n\n", Buffer::alive());

    std::printf("== 2. 嵌套作用域：内层先结束 ==\n");
    {
        Buffer outer(8, "outer");
        {
            Buffer inner(8, "inner");
            std::printf("-- 最内层，alive = %d --\n", Buffer::alive());
        }
        std::printf("-- inner 已销毁、outer 还在，alive = %d --\n", Buffer::alive());
    }
    std::printf("-- 外层也结束，alive = %d --\n\n", Buffer::alive());

    std::printf("== 3. 堆对象：new 出来的必须手动 delete ==\n");
    {
        Buffer* p = new Buffer(64, "heap");
        std::printf("-- 刚 new 完，alive = %d --\n", Buffer::alive());
        delete p;  // 试着注释掉这一行再运行（见第 6 节错误一）
        std::printf("-- delete 之后，alive = %d --\n", Buffer::alive());
    }

    std::printf("\nmain 结束，还活着的 Buffer 数量 = %d\n", Buffer::alive());
    return 0;
}
