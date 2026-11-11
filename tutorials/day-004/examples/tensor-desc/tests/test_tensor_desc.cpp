#include "TensorDesc.h"

#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <string>

int main() {
    // --- 1. 一维：最朴素的连续布局 ---
    {
        TensorDesc v({6}, Dtype::Int32, {1}, 0);
        assert(v.rank() == 1);                              // ① 秩 = 维度数
        assert(v.numel() == 6);                             // ② 元素数 = 6（不是字节）
        assert(v.nbytes() == 24);                           // ③ 字节 = 6 × itemsize(int32)=4
        assert(v.is_contiguous());                          // ④ (6,)/(1,) 连续
        assert(v.element_offset({0}) == 0);                 // ⑤ 首元素
        assert(v.element_offset({4}) == 4);                 // ⑥ stride=1：下标即位置
        assert(v.byte_offset({4}) == 16);                   // ⑦ 字节位置 = 4 × 4
    }

    // --- 2. 二维行主序：make_contiguous 推导 strides ---
    {
        TensorDesc a = TensorDesc::make_contiguous({2, 3}, Dtype::Int32);
        assert(a.strides()[0] == 3 && a.strides()[1] == 1); // ⑧ (2,3) → strides (3,1)
        assert(a.numel() == 6 && a.nbytes() == 24);         // ⑨
        assert(a.is_contiguous());                          // ⑩ 行主序连续
        assert(a.element_offset({0, 0}) == 0);              // ⑪ 左上角
        assert(a.element_offset({0, 2}) == 2);              // ⑫ 第一行末尾
        assert(a.element_offset({1, 0}) == 3);              // ⑬ 换行跳 3 个元素
        assert(a.element_offset({1, 2}) == 5);              // ⑭ 右下角
        assert(a.byte_offset({1, 1}) == 16);                // ⑮ 字节位置 = 4 × 4
    }

    // --- 3. 二维非连续：转置视图，同一块存储的另一种读法 ---
    {
        TensorDesc b({3, 2}, Dtype::Int32, {1, 3}, 0);      // A 的转置：交换 strides
        assert(!b.is_contiguous());                         // ⑯ (3,2)/(1,3) 不连续
        assert(b.numel() == 6);                             // ⑰ 元素数与布局无关
        assert(b.element_offset({0, 1}) == 3);              // ⑱ B(0,1) = A(1,0)
        assert(b.element_offset({2, 0}) == 2);              // ⑲ B(2,0) = A(0,2)
        assert(b.element_offset({2, 1}) == 5);              // ⑳ B(2,1) = A(1，2)，同一格子
    }

    // --- 4. 三维：行主序 strides 由外向内 6,3,1 ---
    {
        TensorDesc d = TensorDesc::make_contiguous({2, 2, 3}, Dtype::Int32);
        assert(d.strides()[0] == 6 && d.strides()[1] == 3 && d.strides()[2] == 1); // ㉑
        assert(d.numel() == 12 && d.nbytes() == 48);        // ㉒
        assert(d.is_contiguous());                          // ㉓
        assert(d.element_offset({1, 0, 0}) == 6);           // ㉔ 第一维 +6
        assert(d.element_offset({1, 1, 2}) == 11);          // ㉕ 6 + 3 + 2
        assert(d.byte_offset({1, 1, 2}) == 44);             // ㉖ 字节 = 11 × 4

        TensorDesc dt({3, 2, 2}, Dtype::Int32, {1, 3, 6}, 0); // D 的转置（交换 strides）
        assert(!dt.is_contiguous());                        // ㉗ 三维非连续
        assert(dt.element_offset({2, 1, 1}) == 11);         // ㉘ 与 (1,1,2) 同一格子
    }

    // --- 5. 非连续：从 (2,4) 大矩阵切出前 3 列 ---
    {
        TensorDesc s({2, 3}, Dtype::Int32, {4, 1}, 0);      // 每行 4 列里取 3 列
        assert(!s.is_contiguous());                         // ㉙ 最后一维 stride=1 但整体不连续
        assert(s.element_offset({0, 1}) == 1);              // ㉚
        assert(s.element_offset({1, 2}) == 6);              // ㉛ 第二行要跳过被跳过的第 4 列
    }

    // --- 6. storage_offset：切片视图从中间开始 ---
    {
        TensorDesc e({3}, Dtype::Int32, {1}, 3);            // A[1,:]
        assert(e.storage_offset() == 3);                    // ㉜ 从第 3 个元素开始
        assert(e.element_offset({0}) == 3);                 // ㉝ 下标 0 也要加上 offset
        assert(e.element_offset({2}) == 5);                 // ㉞
        assert(e.is_contiguous());                          // ㉟ offset 不影响连续性
        assert(e.numel() == 3 && e.nbytes() == 12);         // ㊱
    }

    // --- 7. 尺寸为 1 的维度：步长多少都不破坏连续性 ---
    {
        TensorDesc u({2, 1, 3}, Dtype::Int32, {3, 5, 1}, 0);
        assert(u.is_contiguous());                          // ㊲ 中间维 size=1，stride=5 也算连续
        assert(u.element_offset({1, 0, 2}) == 5);           // ㊳ 1×3 + 0×5 + 2×1
    }

    // --- 8. Dtype：同样的 shape，不同的字节数 ---
    {
        assert(itemsize(Dtype::Float32) == 4);              // ㊴
        assert(itemsize(Dtype::Float16) == 2);              // ㊵
        assert(itemsize(Dtype::Int8) == 1);                 // ㊶
        TensorDesc f = TensorDesc::make_contiguous({2, 3}, Dtype::Float16);
        assert(f.nbytes() == 12);                           // ㊷ 6 × 2
        assert(f.byte_offset({1, 2}) == 10);                // ㊸ 5 × 2
        assert(std::string(to_string(Dtype::Float16)) == "float16"); // ㊹
    }

    // --- 9. 昨日挑战的答案：TensorDesc 是纯值类型，拷贝即正确语义 ---
    {
        TensorDesc a = TensorDesc::make_contiguous({2, 3}, Dtype::Int32);
        TensorDesc copy = a;                                // 没写 = delete，也不需要
        assert(copy.element_offset({1, 2}) == a.element_offset({1, 2})); // ㊺
        assert(copy.to_string() == a.to_string());          // ㊻ 两份说明书完全一致
    }

    // --- 10. 边界与非法输入 ---
    {
        TensorDesc a = TensorDesc::make_contiguous({2, 3}, Dtype::Int32);
        bool threw = false;
        try { a.element_offset({2, 0}); }                   // 第 0 维只有 0..1
        catch (const std::out_of_range&) { threw = true; }
        assert(threw);                                      // ㊼ 下标越界被拦截
        threw = false;
        try { a.element_offset({0}); }                      // 少给一个下标
        catch (const std::invalid_argument&) { threw = true; }
        assert(threw);                                      // ㊽ 下标个数不符被拦截
        threw = false;
        try { TensorDesc bad({-1, 3}, Dtype::Int32, {3, 1}); }
        catch (const std::invalid_argument&) { threw = true; }
        assert(threw);                                      // ㊾ 负维度被拦截
        threw = false;
        try { TensorDesc bad({2, 3}, Dtype::Int32, {1}); }  // strides 维数不匹配
        catch (const std::invalid_argument&) { threw = true; }
        assert(threw);                                      // ㊾
        threw = false;
        try { TensorDesc bad({2}, Dtype::Int32, {1}, -1); } // 负 storage_offset
        catch (const std::invalid_argument&) { threw = true; }
        assert(threw);                                      // ㊿
    }

    std::printf("all 50 assertions passed\n");
    return 0;
}
