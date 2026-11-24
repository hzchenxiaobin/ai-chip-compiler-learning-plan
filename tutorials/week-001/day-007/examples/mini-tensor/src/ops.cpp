#include "ops.h"

#include <stdexcept>
#include <string>

Tensor add(const Tensor& a, const Tensor& b) {
    // 异常安全顺序（第 6 天 3.3 节的纪律）：会抛的检查全部排在分配之前——
    // 检查失败时，一个字节都还没拿。三种拒绝都在这一段：
    if (a.desc().dtype() != Dtype::Float32 || b.desc().dtype() != Dtype::Float32) {
        throw std::invalid_argument(
            "add: 只支持 float32，实际 a=" + std::string(::to_string(a.desc().dtype())) +
            " b=" + std::string(::to_string(b.desc().dtype())));
    }
    if (a.desc().shape() != b.desc().shape()) {
        throw std::invalid_argument("add: shape 不一致——" + a.desc().to_string() + " vs " +
                                    b.desc().to_string());
    }
    const int rank = a.rank();
    if (rank < 1 || rank > 2) {
        throw std::invalid_argument("add: 今天只支持 1～2 维，实际秩 " + std::to_string(rank));
    }

    // 检查全过了才分配结果（零值仓库），再逐元素写入。
    // at() 沿各自的说明书翻译下标——a、b 的 strides 可以不同，照样算对。
    Tensor result = Tensor::zeros(a.desc().shape(), Dtype::Float32);
    if (rank == 1) {
        const std::int64_t n = a.desc().shape()[0];
        for (std::int64_t i = 0; i < n; ++i) {
            result.at({i}) = a.at({i}) + b.at({i});
        }
    } else {  // rank == 2
        const std::int64_t rows = a.desc().shape()[0];
        const std::int64_t cols = a.desc().shape()[1];
        for (std::int64_t i = 0; i < rows; ++i) {
            for (std::int64_t j = 0; j < cols; ++j) {
                result.at({i, j}) = a.at({i, j}) + b.at({i, j});
            }
        }
    }
    return result;  // 局部对象按值返回：移动接管，仓库指针直接过户
}
