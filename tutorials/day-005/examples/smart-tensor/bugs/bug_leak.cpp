// 泄漏现场：绕过 Tensor 的封装直接裸 new，然后忘了 delete。
// 普通 builds 一声不吭；ASan 构建里 LeakSanitizer 在进程退出时点名。
// 编译（ASan）：g++ -std=c++17 -g -I ../src ../src/Tensor.cpp bug_leak.cpp -o bug_leak_asan -fsanitize=address -static-libasan
#include "Tensor.h"
#include <cstdio>

int main() {
    Tensor t = Tensor::zeros(2, 3);       // 这块由 unique_ptr 管，没问题
    float* scratch = new float[1024];     // 这块裸 new，没人负责释放
    scratch[0] = t.at(0, 0);
    std::printf("scratch[0] = %g，正常返回 main\n", scratch[0]);
    return 0;                              // ← 4 KB（1024 x 4）泄漏
}
