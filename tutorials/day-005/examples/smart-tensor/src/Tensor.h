#pragma once
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <memory>
#include <string>

// Tensor 初版：只把一件事做对——「这块堆内存归谁管」。
// 数据用 std::unique_ptr<float[]> 独占持有，由此自动获得三件事：
//   1) 拷贝构造 / 拷贝赋值被删除——想复制必须显式写 clone（防 double free）；
//   2) 移动构造 / 移动赋值自动生成且正确——源对象置空（第 3 天手写的语义搬进类型系统）；
//   3) 析构自动 delete[]——只要没人绕过封装裸 new，就不泄漏。
// 第 4 天的 TensorDesc（多维坐标）今天不并入，那是第 6 天的整合任务；
// 今天用 rows/cols 的连续公式 位置 = i*cols + j（第 4 天 strides=(3,1) 的特例）。
class Tensor {
public:
    Tensor() = default;

    // 工厂：shape 为 (rows, cols) 的全零 float Tensor。要求 rows、cols > 0。
    static Tensor zeros(std::int64_t rows, std::int64_t cols);

    // 工厂：从 initializer_list 构造，元素个数必须等于 rows*cols。
    static Tensor from_data(std::int64_t rows, std::int64_t cols,
                            std::initializer_list<float> data);

    std::int64_t rows() const { return rows_; }
    std::int64_t cols() const { return cols_; }
    std::int64_t numel() const { return rows_ * cols_; }
    bool empty() const { return data_ == nullptr; }

    // 带边界检查：越界抛 std::out_of_range（沿用第 2 天 Buffer::at 的约定）。
    float& at(std::int64_t i, std::int64_t j);       // 可写：返回引用
    float at(std::int64_t i, std::int64_t j) const;  // 只读：返回值拷贝

    // 不做边界检查的版本：只用于「故意越界给 Sanitizer 抓」的演示程序。
    // 正常代码永远用 at()。
    float& at_unchecked(std::int64_t i, std::int64_t j);

    const float* raw() const { return data_.get(); }  // 借用指针，不转让所有权

    std::string to_string() const;

private:
    std::int64_t rows_ = 0;
    std::int64_t cols_ = 0;
    std::unique_ptr<float[]> data_;  // 独占所有权：Tensor 是这 rows*cols*4 字节的唯一主人
};
