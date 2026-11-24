#include "Tensor.h"

#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <utility>

int main() {
    int checks = 0;

    // --- ① 构造与数值 ---
    Tensor z = Tensor::zeros(2, 3);
    assert(z.numel() == 6);                       ++checks;
    assert(z.at(1, 2) == 0.0f);                  ++checks;

    Tensor t = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    assert(t.rows() == 2 && t.cols() == 3);      ++checks;
    assert(t.at(0, 0) == 1.0f);                 ++checks;
    assert(t.at(1, 2) == 6.0f);                  ++checks;  // 连续公式 1*3+2

    // --- ② 读写 ---
    t.at(1, 1) = 50.0f;
    assert(t.at(1, 1) == 50.0f);                 ++checks;
    t.at(1, 1) = 5.0f;                           // 恢复

    // --- ③ 边界检查：四个方向全部抛 out_of_range ---
    bool threw = false;
    try { t.at(2, 0); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                               ++checks;
    threw = false;
    try { t.at(1, 3); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                               ++checks;
    threw = false;
    try { t.at(-1, 0); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                               ++checks;

    // --- ④ from_data 参数检查 ---
    threw = false;
    try { Tensor::from_data(2, 3, {1, 2, 3}); }
    catch (const std::invalid_argument&) { threw = true; }
    assert(threw);                               ++checks;

    // --- ⑤ 移动：源置空、目标完好、指针不换 ---
    Tensor a = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    const float* old_ptr = a.raw();
    Tensor b = std::move(a);
    assert(a.empty());                           ++checks;
    assert(b.raw() == old_ptr);                  ++checks;  // 数据没搬，主人换了
    assert(b.at(1, 2) == 6.0f);                  ++checks;
    assert(b.rows() == 2 && b.cols() == 3);      ++checks;

    // --- ⑥ 移动后源可复用 ---
    a = Tensor::zeros(1, 2);
    assert(!a.empty() && a.numel() == 2);        ++checks;

    // --- ⑦ 默认构造为空 ---
    Tensor e;
    assert(e.empty() && e.numel() == 0);         ++checks;

    std::printf("all %d assertions passed\n", checks);
    return 0;
}
