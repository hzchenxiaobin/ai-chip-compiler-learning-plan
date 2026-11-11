// 故意的堆越界写：2x3 只有 6 个元素，at_unchecked(1,3) 落在第 7 个。
// 这就是学习计划第 5 天要求「故意构造一次越界并用 Sanitizer 定位」的现场。
// 编译（无检查）：  g++ -std=c++17 -g -I ../src ../src/Tensor.cpp bug_oob.cpp -o bug_oob
// 编译（ASan）：    g++ -std=c++17 -g -I ../src ../src/Tensor.cpp bug_oob.cpp -o bug_oob_asan -fsanitize=address -static-libasan
#include "Tensor.h"
#include <cstdio>

int main() {
    Tensor t = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    std::printf("t = %s\n", t.to_string().c_str());
    std::printf("现在故意写到 (1,3)——shape 只有 2x3，这一格不存在\n");

    t.at_unchecked(1, 3) = 99.0f;  // 元素位置 1*3+3 = 6：24 字节区域的第 25~28 字节

    std::printf("写完了，程序看起来还活着，exit 0\n");
    return 0;
}
