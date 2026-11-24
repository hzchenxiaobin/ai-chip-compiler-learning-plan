// 修复版：同样的访问意图，但用带边界检查的 at()。
// 越界在第一次访问就被拒绝并给出可读的诊断，而不是写坏邻居的内存。
// 编译（ASan）：g++ -std=c++17 -g -I ../src ../src/Tensor.cpp bug_oob_fixed.cpp -o bug_oob_fixed_asan -fsanitize=address -static-libasan
#include "Tensor.h"
#include <cstdio>
#include <stdexcept>

int main() {
    Tensor t = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    std::printf("t = %s\n", t.to_string().c_str());
    std::printf("还是想写 (1,3)——但这次用 at()\n");

    try {
        t.at(1, 3) = 99.0f;
    } catch (const std::out_of_range& e) {
        std::printf("caught: %s\n", e.what());
    }
    std::printf("内存一个字节都没被写坏，正常退出，exit 0\n");
    return 0;
}
