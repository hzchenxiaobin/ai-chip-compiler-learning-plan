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

// 第 14 天复盘：element_bytes（每个元素几字节）随 TensorType::bytes()
// 一起删了——它唯一的调用方就是 bytes()，而 bytes() 一周零调用。
// 第 73 天估算片上空间时再回来写。
