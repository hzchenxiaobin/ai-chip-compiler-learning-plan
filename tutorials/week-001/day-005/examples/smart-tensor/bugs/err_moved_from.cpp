// 错误二现场：移动之后继续用源对象。
// 移动把 data_ 搬走了，源的 rows_/cols_ 还是旧值（int 移动=拷贝），
// 于是 at(0,0) 通过了边界检查，然后解引用空指针。
// 编译（ASan）：g++ -std=c++17 -g -I ../src ../src/Tensor.cpp err_moved_from.cpp -o err_moved_from_asan -fsanitize=address -static-libasan
#include "Tensor.h"
#include <cstdio>
#include <utility>

int main() {
    Tensor a = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    Tensor b = std::move(a);               // a.data_ 已是 nullptr
    std::printf("b(1,2) = %g，一切正常\n", b.at(1, 2));

    std::printf("现在错误地继续用 a ...\n");
    std::printf("a(0,0) = %g\n", a.at(0, 0));   // ← 边界检查通过，空指针解引用
    return 0;
}
