#include "Tensor.h"

#include <cstdio>
#include <stdexcept>
#include <utility>

Tensor Tensor::zeros(std::int64_t rows, std::int64_t cols) {
    if (rows <= 0 || cols <= 0) {
        throw std::invalid_argument("zeros: rows/cols 必须为正数");
    }
    Tensor t;
    t.rows_ = rows;
    t.cols_ = cols;
    // make_unique<float[]>(n) 会把 n 个 float 数值初始化为 0.0f。
    t.data_ = std::make_unique<float[]>(rows * cols);
    return t;
}

Tensor Tensor::from_data(std::int64_t rows, std::int64_t cols,
                         std::initializer_list<float> data) {
    if (rows <= 0 || cols <= 0) {
        throw std::invalid_argument("from_data: rows/cols 必须为正数");
    }
    if (static_cast<std::int64_t>(data.size()) != rows * cols) {
        throw std::invalid_argument("from_data: 元素个数不等于 rows*cols");
    }
    Tensor t;
    t.rows_ = rows;
    t.cols_ = cols;
    t.data_ = std::make_unique<float[]>(rows * cols);
    std::int64_t k = 0;
    for (float v : data) {
        t.data_[static_cast<std::size_t>(k)] = v;  // unique_ptr<T[]> 自带 operator[]
        ++k;
    }
    return t;
}

float& Tensor::at(std::int64_t i, std::int64_t j) {
    if (i < 0 || i >= rows_ || j < 0 || j >= cols_) {
        throw std::out_of_range("at(" + std::to_string(i) + "," + std::to_string(j) +
                                ") 越界：shape 是 " + std::to_string(rows_) + "x" +
                                std::to_string(cols_));
    }
    return data_[static_cast<std::size_t>(i * cols_ + j)];
}

float Tensor::at(std::int64_t i, std::int64_t j) const {
    if (i < 0 || i >= rows_ || j < 0 || j >= cols_) {
        throw std::out_of_range("at(" + std::to_string(i) + "," + std::to_string(j) +
                                ") 越界：shape 是 " + std::to_string(rows_) + "x" +
                                std::to_string(cols_));
    }
    return data_[static_cast<std::size_t>(i * cols_ + j)];
}

float& Tensor::at_unchecked(std::int64_t i, std::int64_t j) {
    return data_[static_cast<std::size_t>(i * cols_ + j)];  // 没有任何检查
}

std::string Tensor::to_string() const {
    std::string s = std::to_string(rows_) + "x" + std::to_string(cols_) + " float:";
    char buf[32];
    for (std::int64_t i = 0; i < rows_; ++i) {
        s += "\n  [";
        for (std::int64_t j = 0; j < cols_; ++j) {
            std::snprintf(buf, sizeof(buf), "%s%g", j ? " " : "",
                          data_[static_cast<std::size_t>(i * cols_ + j)]);
            s += buf;
        }
        s += "]";
    }
    return s;
}
