#include "Tensor.h"

#include <cstdio>
#include <stdexcept>
#include <utility>

int main() {
    std::printf("== 0. 创建：from_data({2,3}, [1..6])——还是那块老存储 ==\n");
    Tensor t = Tensor::from_data({2, 3}, {1, 2, 3, 4, 5, 6});
    std::printf("%s\n", t.to_string().c_str());

    std::printf("== 1. 读取：at({0,0})、at({1,2}) ==\n");
    std::printf("  at({0,0}) = %g\n", t.at({0, 0}));
    std::printf("  at({1,2}) = %g\n", t.at({1, 2}));

    std::printf("== 2. 写入：at({1,2}) *= 10 ==\n");
    t.at({1, 2}) *= 10.0f;
    std::printf("  at({1,2}) = %g\n", t.at({1, 2}));

    std::printf("== 3. 边界检查：秩、逐维、负下标 ==\n");
    try {
        t.at({2, 0});
    } catch (const std::out_of_range& e) {
        std::printf("  at({2,0})  caught: %s\n", e.what());
    }
    try {
        t.at({0, 3});
    } catch (const std::out_of_range& e) {
        std::printf("  at({0,3})  caught: %s\n", e.what());
    }
    try {
        t.at({-1, 0});
    } catch (const std::out_of_range& e) {
        std::printf("  at({-1,0}) caught: %s\n", e.what());
    }
    try {
        t.at({1});
    } catch (const std::invalid_argument& e) {
        std::printf("  at({1})    caught: %s\n", e.what());
    }

    std::printf("== 4. 移动：Tensor b = std::move(t) ==\n");
    const std::byte* before = t.storage().data();
    Tensor b = std::move(t);
    std::printf("  移动后 t.empty()? %s；b.storage().data() 与移动前相同? %s\n",
                t.empty() ? "yes" : "no", b.storage().data() == before ? "yes" : "no");
    std::printf("  b 还能读：b.at({1,2}) = %g\n", b.at({1, 2}));
    std::printf("  t 的说明书也被搬空（vector 移动 = 源变空）：t.rank() = %d\n", t.rank());
    try {
        t.at({1, 2});  // 第 5 天错误二在这里翻车成 SEGV；今天第一道防线（秩）就拦下
    } catch (const std::invalid_argument& e) {
        std::printf("  误用空壳 t.at({1,2}) caught: %s\n", e.what());
    }
    try {
        t.at({});  // 秩恰好都是 0、过了第一道防线 → 空壳检查兜底
    } catch (const std::logic_error& e) {
        std::printf("  误用空壳 t.at({})   caught: %s\n", e.what());
    }

    std::printf("== 5. 同一组数字，换一份说明书 ==\n");
    Tensor m32 = Tensor::from_data({3, 2}, {1, 2, 3, 4, 5, 6});
    Tensor t123 = Tensor::from_data({1, 2, 3}, {1, 2, 3, 4, 5, 6});
    std::printf("%s\n", m32.to_string().c_str());
    std::printf("  at({2,1}) = %g\n", m32.at({2, 1}));
    std::printf("%s\n", t123.to_string().c_str());
    std::printf("  at({0,1,2}) = %g\n", t123.at({0, 1, 2}));

    std::printf("== 6. dtype 换一换：同一 shape，nbytes 跟着 itemsize 走 ==\n");
    std::printf("  %s\n", Tensor::zeros({2, 3}, Dtype::Float32).info().c_str());
    std::printf("  %s\n", Tensor::zeros({2, 3}, Dtype::Float16).info().c_str());
    std::printf("  %s\n", Tensor::zeros({2, 3}, Dtype::Int8).info().c_str());

    std::printf("== 7. 异常安全：from_data 元素个数不匹配 ==\n");
    try {
        Tensor bad_t = Tensor::from_data({2, 3}, {1, 2, 3});
        (void)bad_t;
    } catch (const std::invalid_argument& e) {
        std::printf("  caught: %s\n", e.what());
    }
    Tensor after = Tensor::from_data({2, 2}, {1, 2, 3, 4});
    std::printf("  异常之后照常创建：after.at({1,1}) = %g\n", after.at({1, 1}));
    std::printf("  程序结束：所有堆内存自动释放（ASan 构建下由 LeakSanitizer 作证）\n");
    return 0;
}
