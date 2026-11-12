#pragma once

#include <cstdint>
#include <string>

// Dtype：元素类型。第 4 天的 TensorDesc 练过同名概念；
// 区别：那边是给数据容器用的，这边是给 IR 里的值用的。
enum class Dtype : std::uint8_t {
    F32,
    F16,
    I32,
    I64,
};

inline std::string dtype_name(Dtype d) {
    switch (d) {
        case Dtype::F32: return "f32";
        case Dtype::F16: return "f16";
        case Dtype::I32: return "i32";
        case Dtype::I64: return "i64";
    }
    return "?";
}

inline std::int64_t element_bytes(Dtype d) {
    switch (d) {
        case Dtype::F32: return 4;
        case Dtype::F16: return 2;
        case Dtype::I32: return 4;
        case Dtype::I64: return 8;
    }
    return 0;
}
