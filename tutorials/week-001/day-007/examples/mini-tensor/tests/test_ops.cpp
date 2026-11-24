// 第 7 天：为修复遗留的 add 补的测试（第 6 天必做练习的验收清单）。
// 覆盖：正确性（1D/2D/不同 strides）、shape 不匹配、非 float32、秩超范围、
//       a/b 不被改动（借用）、结果独立于输入（新仓库）、异常后照常工作。

#include "ops.h"
#include "Tensor.h"

#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <utility>
#include <vector>

int main() {
    int checks = 0;

    // --- ① 2D 正确性：逐位核对 ---
    Tensor a = Tensor::from_data({2, 3}, {1, 2, 3, 4, 5, 6});
    Tensor b = Tensor::from_data({2, 3}, {10, 20, 30, 40, 50, 60});
    Tensor c = add(a, b);
    assert(c.at({0, 0}) == 11.0f && c.at({0, 1}) == 22.0f && c.at({0, 2}) == 33.0f);
    assert(c.at({1, 0}) == 44.0f && c.at({1, 1}) == 55.0f && c.at({1, 2}) == 66.0f);  ++checks;
    assert(c.desc().shape() == (std::vector<std::int64_t>{2, 3}));                    ++checks;

    // --- ② 1D 正确性 ---
    Tensor v1 = Tensor::from_data({4}, {1, 2, 3, 4});
    Tensor v2 = Tensor::from_data({4}, {100, 200, 300, 400});
    Tensor v3 = add(v1, v2);
    assert(v3.at({0}) == 101.0f && v3.at({3}) == 404.0f);                             ++checks;

    // --- ③ 借用：add 之后 a、b 一个字节都没动 ---
    assert(a.at({0, 0}) == 1.0f && a.at({1, 2}) == 6.0f);
    assert(b.at({0, 0}) == 10.0f && b.at({1, 2}) == 60.0f);                           ++checks;

    // --- ④ 结果是独立的新仓库：改 c 不影响 a、b ---
    c.at({0, 0}) = -1.0f;
    assert(a.at({0, 0}) == 1.0f && b.at({0, 0}) == 10.0f);                            ++checks;

    // --- ⑤ 同一组数字、不同的说明书（strides 不同）也能相加 ---
    // 两个仓库里都放 1..6：
    //   strides (3,1)（行主序）读作 [[1 2 3][4 5 6]]；
    //   strides (1,2) 读作 [[1 3 5][2 4 6]]（前者的转置读法）。
    // add 通过各自的 at() 翻译下标，与存储布局无关——
    // 这也是第 57 天"同一块存储配多份说明书"的最小预演。
    Buffer buf_row(24), buf_col(24);
    {
        float* r = reinterpret_cast<float*>(buf_row.data());
        float* c2 = reinterpret_cast<float*>(buf_col.data());
        for (int k = 0; k < 6; ++k) {
            r[static_cast<std::size_t>(k)] = static_cast<float>(k + 1);
            c2[static_cast<std::size_t>(k)] = static_cast<float>(k + 1);
        }
    }
    Tensor row_major(TensorDesc({2, 3}, Dtype::Float32, {3, 1}), std::move(buf_row));
    Tensor col_major(TensorDesc({2, 3}, Dtype::Float32, {1, 2}), std::move(buf_col));
    // 同一个坐标 (0,2)：行主序读到元素 2（值 3），strides (1,2) 读到元素 4（值 5）。
    assert(row_major.at({0, 2}) == 3.0f && col_major.at({0, 2}) == 5.0f);             ++checks;
    Tensor sum = add(row_major, col_major);
    assert(sum.at({0, 0}) == 2.0f && sum.at({0, 1}) == 5.0f && sum.at({0, 2}) == 8.0f);
    assert(sum.at({1, 0}) == 6.0f && sum.at({1, 1}) == 9.0f && sum.at({1, 2}) == 12.0f); ++checks;

    // --- ⑥ shape 不匹配：invalid_argument ---
    bool threw = false;
    try {
        Tensor bad = add(a, Tensor::from_data({3, 2}, {1, 2, 3, 4, 5, 6}));
        (void)bad;
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    assert(threw);                                                                     ++checks;

    // --- ⑦ 非 float32 输入：invalid_argument ---
    threw = false;
    try {
        Tensor bad = add(Tensor::zeros({2, 3}, Dtype::Int8), b);
        (void)bad;
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    assert(threw);                                                                     ++checks;

    // --- ⑧ 秩超范围（今天只做 1～2 维）：invalid_argument ---
    threw = false;
    try {
        Tensor bad = add(Tensor::zeros({2, 2, 2}, Dtype::Float32),
                         Tensor::zeros({2, 2, 2}, Dtype::Float32));
        (void)bad;
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    assert(threw);                                                                     ++checks;

    // --- ⑨ 异常之后一切照常（无状态残留） ---
    Tensor after = add(a, b);
    assert(after.at({1, 2}) == 66.0f);                                                 ++checks;

    // --- ⑩ add 的结果可以继续参与移动语义 ---
    Tensor moved = std::move(after);
    assert(moved.at({1, 2}) == 66.0f);
    assert(after.empty());                                                             ++checks;

    std::printf("all %d assertions passed\n", checks);
    return 0;
}
