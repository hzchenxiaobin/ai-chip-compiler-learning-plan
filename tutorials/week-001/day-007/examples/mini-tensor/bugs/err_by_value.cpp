// 第 7 天·错误三的复现：add 的参数按值传 Tensor——"随意拷贝"在真 Tensor 上过不了编译。
//
// 编译（预期失败，错误发生在编译期）：
//   g++ -std=c++17 -g -I ../src ../src/Buffer.cpp ../src/TensorDesc.cpp \
//       ../src/Tensor.cpp ../src/ops.cpp err_by_value.cpp -o err_by_value
//
// 修复：把签名改成 const Tensor&（借用），见 ../src/ops.h。

#include "ops.h"

// 故意按值传参：正确版本是 const Tensor&（见 ../src/ops.h）。
// 编译器在这一行直接拒绝——Tensor 的拷贝构造是 deleted 的。
Tensor by_value_add(Tensor a, Tensor b) {
    return add(a, b);
}

int main() {
    Tensor a = Tensor::from_data({2, 3}, {1, 2, 3, 4, 5, 6});
    Tensor b = Tensor::from_data({2, 3}, {10, 20, 30, 40, 50, 60});
    Tensor c = by_value_add(a, b);
    (void)c;
    return 0;
}
