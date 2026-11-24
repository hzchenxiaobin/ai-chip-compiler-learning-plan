// UBSan 现场：按 int 计算 numel，46341 x 46341 超出 int 最大值。
// 场景原型：给大 Tensor 算元素数/字节数时随手用了 int（第 4 天用 int64_t 才是对的）。
// 编译（UBSan）：g++ -std=c++17 -g -fsanitize=undefined -fno-sanitize-recover=all bug_overflow.cpp -o bug_overflow
#include <cstdio>

int main() {
    int rows = 46341, cols = 46341;
    int numel = rows * cols;               // ← 有符号整数溢出：UB
    std::printf("numel = %d\n", numel);
    return 0;
}
