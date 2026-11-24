#include "Tensor.h"

#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

int main() {
    int checks = 0;

    // --- ① zeros：元信息与全零值（float32） ---
    Tensor z = Tensor::zeros({2, 3}, Dtype::Float32);
    assert(z.rank() == 2);                                  ++checks;
    assert(z.numel() == 6);                                 ++checks;
    assert(z.nbytes() == 24);                               ++checks;
    assert(z.is_contiguous());                              ++checks;
    assert(!z.empty());                                     ++checks;
    assert(z.desc().shape() == (std::vector<std::int64_t>{2, 3}));    ++checks;
    assert(z.desc().strides() == (std::vector<std::int64_t>{3, 1}));  ++checks;
    assert(z.at({1, 2}) == 0.0f);                           ++checks;

    // --- ② zeros：其他 Dtype 只改元信息，不涉编解码（nbytes = numel × itemsize） ---
    assert(Tensor::zeros({2, 3}, Dtype::Float16).nbytes() == 12);  ++checks;
    assert(Tensor::zeros({2, 3}, Dtype::Int8).nbytes() == 6);      ++checks;
    assert(Tensor::zeros({4, 7}, Dtype::Int32).nbytes() == 112);   ++checks;
    assert(Tensor::zeros({2, 3}, Dtype::Int8).desc().dtype() == Dtype::Int8);  ++checks;

    // --- ③ from_data：按 desc 的解释逐位核对 ---
    Tensor t = Tensor::from_data({2, 3}, {1, 2, 3, 4, 5, 6});
    assert(t.at({0, 0}) == 1.0f && t.at({0, 1}) == 2.0f);
    assert(t.at({0, 2}) == 3.0f && t.at({1, 0}) == 4.0f);
    assert(t.at({1, 1}) == 5.0f && t.at({1, 2}) == 6.0f);  ++checks;

    // --- ④ 写入：at 返回引用 ---
    t.at({1, 2}) = 60.0f;
    assert(t.at({1, 2}) == 60.0f);                          ++checks;
    t.at({1, 2}) = 6.0f;                                    // 恢复，后面的段落接着用

    // --- ⑤ 边界检查：四个方向 + 负下标全部 out_of_range ---
    bool threw = false;
    try { t.at({2, 0}); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                                          ++checks;
    threw = false;
    try { t.at({0, 3}); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                                          ++checks;
    threw = false;
    try { t.at({-1, 0}); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                                          ++checks;
    threw = false;
    try { t.at({1, -1}); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                                          ++checks;

    // --- ⑥ 秩不匹配：invalid_argument ---
    threw = false;
    try { t.at({0}); } catch (const std::invalid_argument&) { threw = true; }
    assert(threw);                                          ++checks;
    threw = false;
    try { t.at({0, 0, 0}); } catch (const std::invalid_argument&) { threw = true; }
    assert(threw);                                          ++checks;

    // --- ⑦ 一维：shape 写作 (6,)，strides (1,) ---
    Tensor v = Tensor::from_data({6}, {1, 2, 3, 4, 5, 6});
    assert(v.desc().strides() == (std::vector<std::int64_t>{1}));  ++checks;
    assert(v.at({5}) == 6.0f);                              ++checks;
    threw = false;
    try { v.at({6}); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                                          ++checks;

    // --- ⑧ 三维：strides = (6,3,1) ---
    Tensor t3 = Tensor::from_data({1, 2, 3}, {1, 2, 3, 4, 5, 6});
    assert(t3.desc().strides() == (std::vector<std::int64_t>{6, 3, 1}));  ++checks;
    assert(t3.at({0, 0, 0}) == 1.0f);                       ++checks;
    assert(t3.at({0, 1, 2}) == 6.0f);                       ++checks;

    // --- ⑨ 同一组数字、不同 shape：值 6 的坐标各不相同 ---
    Tensor m32 = Tensor::from_data({3, 2}, {1, 2, 3, 4, 5, 6});
    assert(m32.at({2, 1}) == 6.0f);                         ++checks;
    threw = false;
    try { m32.at({1, 2}); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);  // (3,2) 里 (1,2) 越界：换说明书后同一坐标可能失效
    ++checks;

    // --- ⑩ 移动：源变空壳、目标完好、仓库字节不搬家 ---
    Tensor a = Tensor::from_data({2, 3}, {1, 2, 3, 4, 5, 6});
    const std::byte* old_ptr = a.storage().data();
    const std::size_t old_size = a.storage().size();
    Tensor b = std::move(a);
    assert(a.empty());                                      ++checks;
    assert(b.storage().data() == old_ptr);                  ++checks;
    assert(b.storage().size() == old_size && old_size == 24);  ++checks;
    assert(b.at({1, 2}) == 6.0f);                           ++checks;

    // --- ⑪ moved-from 再误用：第 5 天是 SEGV，今天被两道防线拦下 ---
    threw = false;
    try { a.at({1, 2}); } catch (const std::invalid_argument&) { threw = true; }
    assert(threw);  // 说明书（vector）也被搬空 → 秩检查第一道拦截
    ++checks;
    threw = false;
    try { a.at({}); } catch (const std::logic_error&) { threw = true; }
    assert(threw);  // 秩恰好对上（都是 0）→ 空壳检查兜底
    ++checks;

    // --- ⑫ 空壳可复用：赋新值 ---
    a = Tensor::zeros({1, 2}, Dtype::Float32);
    assert(!a.empty() && a.numel() == 2);                   ++checks;

    // --- ⑬ 默认构造：空壳，at 先撞秩检查，at({}) 撞空壳检查 ---
    Tensor e;
    assert(e.empty());                                      ++checks;
    threw = false;
    try { e.at({0}); } catch (const std::invalid_argument&) { threw = true; }
    assert(threw);                                          ++checks;
    threw = false;
    try { e.at({}); } catch (const std::logic_error&) { threw = true; }
    assert(threw);                                          ++checks;

    // --- ⑭ 配套检查：说明书装不进仓库，构造期就拒绝 ---
    threw = false;
    try {
        // shape (2,3)、strides (5,1)：最远元素 = 1×5 + 2×1 = 7 → 需要 8 格 > 仓库 6 格
        Tensor bad(TensorDesc({2, 3}, Dtype::Float32, {5, 1}), Buffer(24));
    } catch (const std::invalid_argument&) { threw = true; }
    assert(threw);                                          ++checks;

    threw = false;
    try {
        // 有元素的说明书 + 空仓库
        Tensor bad(TensorDesc({2, 3}, Dtype::Float32, {3, 1}), Buffer());
    } catch (const std::invalid_argument&) { threw = true; }
    assert(threw);                                          ++checks;

    // --- ⑮ 配套检查的合法侧：offset 4 起、(2,2)/(2,1) 恰好用到第 7 格 ---
    Tensor view(TensorDesc({2, 2}, Dtype::Float32, {2, 1}, 4), Buffer(32));
    assert(view.storage().size() == 32);                    ++checks;
    assert(view.at({1, 1}) == 0.0f);  // 位置 4 + 1×2 + 1×1 = 7，仍在仓库里  ++checks;

    // --- ⑯ 异常安全：个数不匹配 → 抛异常 → 程序照常继续 ---
    threw = false;
    try { Tensor::from_data({2, 3}, {1, 2, 3}); }
    catch (const std::invalid_argument&) { threw = true; }
    assert(threw);                                          ++checks;
    threw = false;
    try { Tensor::from_data({2, 3}, {1, 2, 3, 4, 5, 6, 7}); }
    catch (const std::invalid_argument&) { threw = true; }
    assert(threw);                                          ++checks;
    Tensor after = Tensor::from_data({2, 2}, {1, 2, 3, 4});
    assert(after.at({1, 1}) == 4.0f);                       ++checks;

    // --- ⑰ 非 float32 的读写：明确拒绝，而不是读出垃圾 ---
    Tensor i8 = Tensor::zeros({2, 3}, Dtype::Int8);
    threw = false;
    try { i8.at({0, 0}); } catch (const std::logic_error&) { threw = true; }
    assert(threw);                                          ++checks;

    // --- ⑱ 零元素张量：numel = 0 装得进任何仓库，at 必然越界 ---
    Tensor z03 = Tensor::zeros({0, 3}, Dtype::Float32);
    assert(z03.numel() == 0 && z03.nbytes() == 0);          ++checks;
    threw = false;
    try { z03.at({0, 0}); } catch (const std::out_of_range&) { threw = true; }
    assert(threw);                                          ++checks;

    // --- ⑲ info / to_string：关键元信息要出现在打印里 ---
    const std::string info = t.info();
    assert(info.find("shape=(2,3)") != std::string::npos);          ++checks;
    assert(info.find("strides=(3,1)") != std::string::npos);        ++checks;
    assert(info.find("nbytes=24") != std::string::npos);            ++checks;
    const std::string shown = t.to_string();
    assert(shown.find("[1 2 3]") != std::string::npos);             ++checks;
    assert(shown.find("[4 5 6]") != std::string::npos);             ++checks;
    const std::string shown3 = t3.to_string();
    assert(shown3.find("[[1 2 3] [4 5 6]]") != std::string::npos);  ++checks;

    std::printf("all %d assertions passed\n", checks);
    return 0;
}
