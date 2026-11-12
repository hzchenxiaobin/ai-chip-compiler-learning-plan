#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "Dtype.h"

// TensorType：一个值（Value）的类型 = 元素类型 + 逻辑 Shape。
// 今天只做「记录」，不做推导（推导在第 43～44 天）、不做布局
//（Stride/Layout 是第 57 天以后的事）——所以没有 stride 成员。
// 第 14 天复盘：v6 里还写过一个 bytes()（字节数）——一周过去零调用方，
// 按 YAGNI 删除：第 73 天资源估算真正需要时，连同 element_bytes
// 一起回来写（那时的「字节数」要按目标硬件的 dtype 宽度算，今天的
// 版本到时候多半也不对）。
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
