#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "Dtype.h"

// TensorType：一个值（Value）的类型 = 元素类型 + 逻辑 Shape。
// 今天只做「记录」，不做推导（推导在第 43～44 天）、不做布局
//（Stride/Layout 是第 57 天以后的事）——所以没有 stride 成员。
struct TensorType {
    Dtype dtype = Dtype::F32;
    std::vector<std::int64_t> shape;

    std::int64_t rank() const noexcept { return static_cast<std::int64_t>(shape.size()); }

    std::int64_t num_elements() const noexcept {
        std::int64_t n = 1;
        for (std::int64_t d : shape) {
            n *= d;
        }
        return n;
    }

    std::int64_t bytes() const noexcept { return num_elements() * element_bytes(dtype); }

    bool same_shape(const TensorType& other) const noexcept { return shape == other.shape; }

    bool operator==(const TensorType& other) const noexcept {
        return dtype == other.dtype && shape == other.shape;
    }

    // 打印成 MLIR 风格：f32<2x3>
    std::string to_string() const {
        std::string s = dtype_name(dtype) + "<";
        for (std::size_t i = 0; i < shape.size(); ++i) {
            if (i != 0) {
                s += "x";
            }
            s += std::to_string(shape[i]);
        }
        return s + ">";
    }
};
