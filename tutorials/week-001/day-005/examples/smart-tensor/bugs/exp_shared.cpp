// 3.3 节 shared_ptr 演示：两台「观察者」共享同一块 Tensor 数据，看引用计数变化。
// 编译：g++ -std=c++17 -g -I ../src ../src/Tensor.cpp exp_shared.cpp -o exp_shared
#include "Tensor.h"
#include <cstdio>
#include <memory>
#include <utility>

int main() {
    std::printf("== 1. unique_ptr：Tensor 数据只有一个主人 ==\n");
    Tensor a = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    const float* pa = a.raw();

    // == 2. shared_ptr：两台「观察者」共享同一块 Tensor 数据 ==
    // 这里演示的是「共享同一份 Tensor」；Tensor 自身仍是 move-only 的。
    auto s1 = std::make_shared<Tensor>(std::move(a));
    std::printf("move 进 shared_ptr：a.empty()? %s，data 指针不变? %s\n",
                a.empty() ? "yes" : "no", s1->raw() == pa ? "yes" : "no");
    std::printf("s1.use_count() = %ld\n", static_cast<long>(s1.use_count()));

    auto s2 = s1;                       // 拷贝 shared_ptr：引用计数 +1
    std::printf("拷贝出 s2 后 use_count() = %ld\n", static_cast<long>(s1.use_count()));

    std::printf("s1->at(1,2) = %g，s2->at(1,2) = %g（同一块数据）\n",
                s1->at(1, 2), s2->at(1, 2));

    s1.reset();                         // 放掉一台观察者
    std::printf("s1.reset() 后 s2.use_count() = %ld\n", static_cast<long>(s2.use_count()));
    std::printf("s2 还能用：s2->at(0,0) = %g\n", s2->at(0, 0));
    std::printf("（s2 也 reset() 后，最后离开的那位负责释放——这正是 shared_ptr 的语义）\n");
    return 0;
}
