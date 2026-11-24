#include "Tensor.h"

#include <cstdio>
#include <stdexcept>
#include <utility>

// 借用演示：函数只是「看一眼」——既不拷贝（拷贝已被 unique_ptr 删除），
// 也不抢所有权（参数是 const 引用，离开函数什么都带不走）。
static float sum(const Tensor& t) {
    float s = 0.0f;
    for (std::int64_t i = 0; i < t.rows(); ++i)
        for (std::int64_t j = 0; j < t.cols(); ++j)
            s += t.at(i, j);
    return s;
}

// 转移演示：按值接收 + 调用方 std::move = 把所有权整个交进函数；
// 函数返回时 t 在栈上析构，堆内存自动释放。
static float consume(Tensor t) {
    return sum(t);
}

int main() {
    std::printf("== 0. 构造：2x3 float，数据就是第 4 天那块 [1..6] ==\n");
    Tensor t = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    std::printf("%s\n", t.to_string().c_str());
    std::printf("numel = %lld，empty? %s\n",
                static_cast<long long>(t.numel()), t.empty() ? "yes" : "no");

    std::printf("== 1. 正常读写：at(1,2) 乘 10 ==\n");
    t.at(1, 2) = t.at(1, 2) * 10.0f;
    std::printf("  at(1,2) = %g\n", t.at(1, 2));

    std::printf("== 2. 边界检查：at(1,3) 越界 → 抛 std::out_of_range ==\n");
    try {
        t.at(1, 3) = 99.0f;
    } catch (const std::out_of_range& e) {
        std::printf("  caught: %s\n", e.what());
    }

    std::printf("== 3. 借用：sum(const Tensor&) 不拷贝、不抢所有权 ==\n");
    std::printf("  sum(t) = %g\n", sum(t));

    std::printf("== 4. 移动：Tensor b = std::move(t) ==\n");
    const float* before = t.raw();
    Tensor b = std::move(t);
    std::printf("  移动后 t.empty()? %s；b.raw() 和移动前相同? %s\n",
                t.empty() ? "yes" : "no", b.raw() == before ? "yes" : "no");
    std::printf("%s\n", b.to_string().c_str());
    std::printf("  t 复用为 1x1：%s\n",
                (t = Tensor::zeros(1, 1), t.to_string().c_str()));

    std::printf("== 5. 所有权交进函数：consume(std::move(b)) ==\n");
    float s = consume(std::move(b));
    std::printf("  consume 拿走 b，sum = %g\n", s);
    std::printf("  b.empty()? %s\n", b.empty() ? "yes" : "no");
    std::printf("  程序结束：所有堆内存均已自动释放（ASan 构建下由 LeakSanitizer 作证）\n");
    return 0;
}
