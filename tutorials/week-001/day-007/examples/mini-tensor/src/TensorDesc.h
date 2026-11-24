#pragma once
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <string>
#include <vector>

// Dtype：元素类型。只关心两件事——名字和每个元素占几个字节。
// 数值语义（范围、精度）第 78 天再管。
enum class Dtype {
    Float32,
    Float16,
    Int32,
    Int8,
};

const char* to_string(Dtype dt);
std::size_t itemsize(Dtype dt);  // 每个元素的字节数

// TensorDesc：Tensor 的“取数说明书”——只记录元信息，不拥有任何数据。
//   shape_          每个维度有多少个元素（逻辑形状）
//   strides_        沿每个维度前进一格，底层存储要跳过多少个【元素】
//   storage_offset_ 这个视图从底层存储的第几个元素开始
//   dtype_          元素类型（决定 itemsize）
//
// 约定（写清楚，防止两种主流约定打架）：
//   本类的 stride 以“元素”为单位（同 PyTorch、MLIR MemRef）；
//   NumPy 的 ndarray.strides 以“字节”为单位，换算关系：字节步长 = 元素步长 × itemsize。
//
// TensorDesc 是纯值类型：只有几个整数和两个 vector，拷贝便宜且语义正确
// （对应到技术上是可平凡拷贝的元数据）。第 4 天的选做挑战已经论证过“不该禁止拷贝”。
class TensorDesc {
public:
    // 第 6 天新增：空状态。Tensor 需要默认构造 / moved-from 的“空壳”，
    // 成员 TensorDesc 必须可以默认构造（shape/strides 为空、offset 0、float32）。
    TensorDesc() = default;

    // 通用构造：显式给出 strides 和 storage_offset，用于描述转置、切片等视图。
    TensorDesc(std::vector<std::int64_t> shape, Dtype dtype,
               std::vector<std::int64_t> strides,
               std::int64_t storage_offset = 0);

    // 工厂：按行主序（row-major）连续布局推导 strides。
    // (2,3) → strides (3,1)：最后一维步长 1，往前每维步长 = 后面所有维度大小之积。
    static TensorDesc make_contiguous(std::vector<std::int64_t> shape, Dtype dtype);

    const std::vector<std::int64_t>& shape() const { return shape_; }
    const std::vector<std::int64_t>& strides() const { return strides_; }
    std::int64_t storage_offset() const { return storage_offset_; }
    Dtype dtype() const { return dtype_; }
    int rank() const { return static_cast<int>(shape_.size()); }

    // 元素总数 = 各维大小之积。注意单位是“元素”，不是“字节”。
    std::int64_t numel() const;

    // 字节数 = numel × itemsize。第 99～101 天内存规划的输入。
    std::size_t nbytes() const;

    // 行主序连续判断（PyTorch 语义）：
    // 从最后一维往前累乘得到“期望步长”，逐维比对；
    // 尺寸为 1 的维度走一步也走不出它，步长是多少都视为满足。
    bool is_contiguous() const;

    // 多维下标 → 底层存储的元素位置：storage_offset_ + Σ idx[d]·strides_[d]
    // 这是编译器 Lowering 生成 load/store 地址的公式（第 88～89 天）。
    //
    // 第 6 天新增：指针区间版核心。运行期才知道秩的调用方
    // （比如 Tensor::to_string 的递归打印）拿不出 initializer_list，用它。
    std::int64_t element_offset(const std::int64_t* idx, std::size_t n) const;
    std::int64_t element_offset(std::initializer_list<std::int64_t> idx) const {
        return element_offset(idx.begin(), idx.size());
    }

    // 多维下标 → 字节位置：element_offset × itemsize。
    std::int64_t byte_offset(std::initializer_list<std::int64_t> idx) const;

    std::string to_string() const;

private:
    std::vector<std::int64_t> shape_;
    std::vector<std::int64_t> strides_;
    std::int64_t storage_offset_ = 0;
    Dtype dtype_ = Dtype::Float32;
};
