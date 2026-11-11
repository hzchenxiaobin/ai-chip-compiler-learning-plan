// use-after-free 现场：把对容器里 Tensor 元素的引用存下来，容器清空后继续用。
// 编译（ASan）：g++ -std=c++17 -g -I ../src ../src/Tensor.cpp bug_uaf.cpp -o bug_uaf_asan -fsanitize=address -static-libasan
#include "Tensor.h"
#include <cstdio>
#include <vector>

int main() {
    std::vector<Tensor> ts;
    ts.push_back(Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6}));

    float& r = ts[0].at(0, 0);             // 借用：引用指向堆上那 24 字节
    std::printf("r = %g\n", r);

    ts.clear();                            // 容器析构 Tensor → 堆内存被 delete[]
    std::printf("容器清空后再读 r ...\n");
    std::printf("r = %g\n", r);            // ← 读取已释放内存
    return 0;
}
