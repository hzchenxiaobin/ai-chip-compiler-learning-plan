// 5.4 节对照实验：越界距离可调（元素下标来自 argv）。
// 观察同一程序在「无检查」和「ASan」两种构建下的行为差异。
// 编译（无检查）：  g++ -std=c++17 -g -I ../src ../src/Tensor.cpp exp_oob_far.cpp -o exp_plain
// 编译（ASan）：    g++ -std=c++17 -g -I ../src ../src/Tensor.cpp exp_oob_far.cpp -o exp_asan -fsanitize=address -static-libasan
// 运行示例：        ./exp_plain 6 | ./exp_asan 6 | ./exp_plain 100000
#include "Tensor.h"
#include <cstdio>
#include <cstdlib>

int main(int argc, char** argv) {
    const long k = (argc > 1) ? std::atol(argv[1]) : 6;
    Tensor t = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    std::printf("2x3 存储（24 字节），访问元素下标 %ld ...\n", k);

    t.at_unchecked(0, k) = 99.0f;           // 元素位置 = 0*3 + k = k
    std::printf("访问完成，exit 0\n");
    return 0;
}
