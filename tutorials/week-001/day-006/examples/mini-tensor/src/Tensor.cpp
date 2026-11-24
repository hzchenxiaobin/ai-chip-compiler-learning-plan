#include "Tensor.h"

#include <cstdio>
#include <stdexcept>
#include <utility>

Tensor::Tensor(TensorDesc desc, Buffer storage) {
    // 先检查、后转移：check_fit 抛异常时，desc / storage 还是完好的按值实参，
    // 成员 desc_ / storage_ 仍是默认的空状态——对象“从未碰过资源”（强异常保证）。
    // 反过来（先 move 进成员再检查）也不会泄漏——unique_ptr 成员在栈展开时自动释放
    // ——但调用方传进来的参数已经被搬空，只算弱保证。两种写法的差别，正文 3.3 节展开。
    check_fit(desc, storage);
    desc_ = std::move(desc);          // TensorDesc 是纯值类型，这一步便宜
    storage_ = std::move(storage);    // Buffer 换主人，字节一比特不动
}

void Tensor::check_fit(const TensorDesc& desc, const Buffer& storage) {
    if (desc.numel() == 0) {
        return;  // 没有元素要放，天然装得下
    }
    // 说明书能摸到的最远一格（元素单位，0 起）：offset + Σ (shape[d]-1)·strides[d]，再 +1 变成“格数”。
    // numel > 0 时每一维都 ≥ 1，所以 (shape[d]-1) 不会是负数。
    std::int64_t need = desc.storage_offset() + 1;
    for (int d = 0; d < desc.rank(); ++d) {
        const std::size_t du = static_cast<std::size_t>(d);
        need += (desc.shape()[du] - 1) * desc.strides()[du];
    }
    // 仓库容量换算成元素个数（向下取整，宁严勿松）。
    const std::int64_t have =
        static_cast<std::int64_t>(storage.size() / itemsize(desc.dtype()));
    if (need > have) {
        throw std::invalid_argument(
            "Tensor: 说明书装不进仓库——最远需要 " + std::to_string(need) +
            " 个元素，仓库只有 " + std::to_string(have) + " 个（" + desc.to_string() + "）");
    }
}

Tensor Tensor::zeros(std::vector<std::int64_t> shape, Dtype dtype) {
    // 异常安全的顺序：先做会抛的元信息工作（此时还没分配任何东西），
    // 再做唯一可能失败的分配（bad_alloc），最后才是不会抛的组装。
    TensorDesc desc = TensorDesc::make_contiguous(std::move(shape), dtype);
    Buffer buf(desc.nbytes());  // make_unique<std::byte[]> 全部清零
    return Tensor(std::move(desc), std::move(buf));
}

Tensor Tensor::from_data(std::vector<std::int64_t> shape,
                         std::initializer_list<float> data) {
    TensorDesc desc = TensorDesc::make_contiguous(std::move(shape), Dtype::Float32);
    if (static_cast<std::int64_t>(data.size()) != desc.numel()) {
        throw std::invalid_argument("from_data: 元素个数 " + std::to_string(data.size()) +
                                    " != numel " + std::to_string(desc.numel()));
    }
    Buffer buf(desc.nbytes());
    Tensor t(std::move(desc), std::move(buf));
    // 连续布局：第 k 个元素就是仓库的第 k 格。
    float* p = t.element_ptr(0);
    std::int64_t k = 0;
    for (float v : data) {
        p[static_cast<std::size_t>(k)] = v;
        ++k;
    }
    return t;
}

void Tensor::require_float32(const char* who) const {
    if (desc_.dtype() != Dtype::Float32) {
        throw std::logic_error(std::string(who) + ": 今天的元素读写只支持 float32，实际 dtype=" +
                               ::to_string(desc_.dtype()));
    }
}

std::int64_t Tensor::checked_element(const std::int64_t* idx, std::size_t n) const {
    require_float32("at");
    const std::int64_t elem = desc_.element_offset(idx, n);  // 秩 + 逐维边界
    if (storage_.empty()) {
        // 秩检查先拦掉 moved-from（说明书也被搬空 → rank 0）；这一层兜住
        // 「秩恰好对上却不持有存储」的情况（如默认构造后 at({})）。
        throw std::logic_error("at: 这个 Tensor 不持有存储（默认构造或已被移动）");
    }
    return elem;
}

const float* Tensor::element_ptr(std::int64_t elem) const {
    // 字节仓库按 dtype 解释：元素位置 × itemsize = 字节偏移。
    // operator new[] 返回按最大对齐对齐的内存，float32 的 4 字节对齐天然满足。
    return reinterpret_cast<const float*>(
        storage_.data() + static_cast<std::size_t>(elem) * itemsize(desc_.dtype()));
}

float* Tensor::element_ptr(std::int64_t elem) {
    return reinterpret_cast<float*>(
        storage_.data() + static_cast<std::size_t>(elem) * itemsize(desc_.dtype()));
}

float Tensor::at(std::initializer_list<std::int64_t> idx) const {
    return *element_ptr(checked_element(idx.begin(), idx.size()));
}

float& Tensor::at(std::initializer_list<std::int64_t> idx) {
    return *element_ptr(checked_element(idx.begin(), idx.size()));
}

std::string Tensor::info() const {
    std::string s = desc_.to_string();
    s += " | numel=" + std::to_string(numel());
    s += " nbytes=" + std::to_string(nbytes());
    s += is_contiguous() ? " contiguous=yes" : " contiguous=no";
    s += empty() ? " empty=yes" : " empty=no";
    return s;
}

void Tensor::append_slice(const Tensor& t, std::vector<std::int64_t>& idx,
                          std::size_t dim, std::string& out) {
    out += "[";
    const std::int64_t n = t.desc_.shape()[dim];
    for (std::int64_t i = 0; i < n; ++i) {
        idx[dim] = i;
        if (dim + 1 == idx.size()) {  // 最后一维：打印元素值
            char buf[32];
            std::snprintf(buf, sizeof(buf), "%s%g", i ? " " : "",
                          *t.element_ptr(t.checked_element(idx.data(), idx.size())));
            out += buf;
        } else {  // 还有内层维度：递归打印子切片
            if (i) out += " ";
            append_slice(t, idx, dim + 1, out);
        }
    }
    out += "]";
}

std::string Tensor::to_string() const {
    std::string s = info();
    if (desc_.dtype() != Dtype::Float32) {
        s += "\n  [数值打印今天只支持 float32]";
        return s;
    }
    if (storage_.empty()) {
        s += "\n  [空壳：不持有存储]";
        return s;
    }
    if (desc_.rank() == 0) {  // 零秩 = 标量：numel = 1，也按说明书能读出来
        char buf[32];
        std::snprintf(buf, sizeof(buf), "[%g]",
                      *element_ptr(checked_element(nullptr, 0)));
        s += buf;
        return s;
    }
    s += "\n  ";
    std::vector<std::int64_t> idx(static_cast<std::size_t>(desc_.rank()), 0);
    append_slice(*this, idx, 0, s);
    return s;
}
