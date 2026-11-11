// 错误三：移动之后继续用源对象（第 5 天错误二的复演）。
// 第 5 天：rows/cols（整型）还在、data_ 是 nullptr → at() 通过边界检查后解引用空指针 → SEGV。
// 第 6 天：默认移动连说明书（vector）一起搬空，误用会被两道防线拦下，都不再是 SEGV：
//   at({1,2}) → 秩检查（invalid_argument）；at({}) → 空壳检查（logic_error）。
#include "Tensor.h"
#include <cstdio>
#include <stdexcept>
#include <utility>

int main() {
    Tensor a = Tensor::from_data({2, 3}, {1, 2, 3, 4, 5, 6});
    Tensor b = std::move(a);
    std::printf("b.at({1,2}) = %g，一切正常\n", b.at({1, 2}));
    std::printf("a.empty()? %s；a.rank() = %d（说明书也被搬空了）\n",
                a.empty() ? "yes" : "no", a.rank());
    std::printf("现在错误地继续用 a ...\n");
    try {
        std::printf("a.at({1,2}) = %g\n", a.at({1, 2}));
    } catch (const std::invalid_argument& e) {
        std::printf("caught: %s\n", e.what());
    }
    try {
        std::printf("a.at({}) = %g\n", a.at({}));
    } catch (const std::logic_error& e) {
        std::printf("caught: %s\n", e.what());
    }
    std::printf("程序正常退出，exit 0\n");
    return 0;
}
