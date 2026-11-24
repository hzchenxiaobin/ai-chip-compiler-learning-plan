#include "TensorDesc.h"

#include <numeric>
#include <stdexcept>
#include <utility>

const char* to_string(Dtype dt) {
    switch (dt) {
        case Dtype::Float32: return "float32";
        case Dtype::Float16: return "float16";
        case Dtype::Int32:   return "int32";
        case Dtype::Int8:    return "int8";
    }
    return "?";
}

std::size_t itemsize(Dtype dt) {
    switch (dt) {
        case Dtype::Float32: return 4;
        case Dtype::Float16: return 2;
        case Dtype::Int32:   return 4;
        case Dtype::Int8:    return 1;
    }
    return 0;
}

TensorDesc::TensorDesc(std::vector<std::int64_t> shape, Dtype dtype,
                       std::vector<std::int64_t> strides,
                       std::int64_t storage_offset)
    : shape_(std::move(shape)),
      strides_(std::move(strides)),
      storage_offset_(storage_offset),
      dtype_(dtype) {
    // 构造期只检查“说明书自身写得通不通”，查不了“和真实数据配不配”
    // （比如 stride 越界要看 buffer 大小才知道，那是第 6 天 Tensor 的职责）。
    if (shape_.size() != strides_.size()) {
        throw std::invalid_argument("TensorDesc: shape 维数 " +
                                    std::to_string(shape_.size()) + " 与 strides 维数 " +
                                    std::to_string(strides_.size()) + " 不一致");
    }
    for (std::int64_t d : shape_) {
        if (d < 0) {
            throw std::invalid_argument("TensorDesc: shape 不允许负维度 " + std::to_string(d));
        }
    }
    for (std::int64_t s : strides_) {
        if (s < 0) {
            throw std::invalid_argument("TensorDesc: 暂不支持负 stride " + std::to_string(s));
        }
    }
    if (storage_offset_ < 0) {
        throw std::invalid_argument("TensorDesc: storage_offset 不允许负值");
    }
}

TensorDesc TensorDesc::make_contiguous(std::vector<std::int64_t> shape, Dtype dtype) {
    const std::size_t rank = shape.size();
    std::vector<std::int64_t> strides(rank, 1);
    for (std::size_t i = rank; i-- > 1;) {  // 从倒数第二维往前累乘
        strides[i - 1] = strides[i] * shape[i];
    }
    return TensorDesc(std::move(shape), dtype, std::move(strides), 0);
}

std::int64_t TensorDesc::numel() const {
    return std::accumulate(shape_.begin(), shape_.end(), std::int64_t{1},
                           std::multiplies<std::int64_t>());
}

std::size_t TensorDesc::nbytes() const {
    return static_cast<std::size_t>(numel()) * itemsize(dtype_);
}

bool TensorDesc::is_contiguous() const {
    std::int64_t expected = 1;
    for (std::size_t i = shape_.size(); i-- > 0;) {
        if (shape_[i] == 1) {
            continue;  // 尺寸为 1 的维度不影响“逐元素挨着放”
        }
        if (strides_[i] != expected) {
            return false;
        }
        expected *= shape_[i];
    }
    return true;
}

std::int64_t TensorDesc::element_offset(std::initializer_list<std::int64_t> idx) const {
    if (idx.size() != shape_.size()) {
        throw std::invalid_argument("element_offset: 下标个数 " + std::to_string(idx.size()) +
                                    " 与秩 " + std::to_string(shape_.size()) + " 不一致");
    }
    std::int64_t offset = storage_offset_;
    std::size_t d = 0;
    for (std::int64_t i : idx) {
        if (i < 0 || i >= shape_[d]) {
            throw std::out_of_range("element_offset: 第 " + std::to_string(d) + " 维下标 " +
                                    std::to_string(i) + " 越界（0.." +
                                    std::to_string(shape_[d] - 1) + "）");
        }
        offset += i * strides_[d];
        ++d;
    }
    return offset;
}

std::int64_t TensorDesc::byte_offset(std::initializer_list<std::int64_t> idx) const {
    return element_offset(idx) * static_cast<std::int64_t>(itemsize(dtype_));
}

std::string TensorDesc::to_string() const {
    std::string s = "shape=(";
    for (std::size_t i = 0; i < shape_.size(); ++i) {
        if (i) s += ",";
        s += std::to_string(shape_[i]);
    }
    if (shape_.size() == 1) s += ",";  // 一维写作 (6,)，和数学/Python 习惯一致
    s += ") strides=(";
    for (std::size_t i = 0; i < strides_.size(); ++i) {
        if (i) s += ",";
        s += std::to_string(strides_[i]);
    }
    if (strides_.size() == 1) s += ",";
    s += ") offset=" + std::to_string(storage_offset_);
    s += " dtype=";
    s += ::to_string(dtype_);  // :: 限定：避开同名成员函数的遮蔽
    return s;
}
