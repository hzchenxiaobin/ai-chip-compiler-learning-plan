// 错误一：from_data 元素个数与 numel 不匹配。
// 构造期（还没分配任何东西）就被拒绝——异常安全的顺序在起作用。
#include "Tensor.h"
#include <cstdio>
#include <stdexcept>

int main() {
    std::printf("想造 shape=(2,3) 的 Tensor，却只给了 3 个数 ...\n");
    try {
        Tensor t = Tensor::from_data({2, 3}, {1, 2, 3});
        (void)t;
        std::printf("不应该走到这里\n");
    } catch (const std::invalid_argument& e) {
        std::printf("caught: %s\n", e.what());
    }
    Tensor ok = Tensor::from_data({2, 3}, {1, 2, 3, 4, 5, 6});
    std::printf("异常之后照常创建：ok.at({1,2}) = %g\n", ok.at({1, 2}));
    return 0;
}
