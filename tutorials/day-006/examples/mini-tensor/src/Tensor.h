#pragma once
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <string>
#include <vector>

#include "Buffer.h"
#include "TensorDesc.h"

// 最小 Tensor：把「说明书」和「仓库」装进同一个对象。
//
// 职责分工（为什么是“拥有一个 TensorDesc”，而不是“继承 TensorDesc”）：
//   TensorDesc  只描述「多维下标怎么翻译成元素位置」——纯值类型，拷贝便宜；
//   Buffer      只负责「这块堆内存归谁管」——独占所有权，按字节持有；
//   Tensor      把两者配成一对，并在构造期完成第 4 天欠下的配套检查：
//               说明书的最远一格，必须还落在仓库里。
//
// 今天的边界（刻意不做，写在明处）：
//   - 读写只支持 float32（其他 Dtype 的编解码不在最小闭环里，第 78 天展开）；
//   - 不做视图/共享存储——transpose、slice 共用一块 Buffer 是第 57 天；
//   - 不做 reshape/broadcast——第 59/60 天。
class Tensor {
public:
    Tensor() = default;

    // 低级入口：说明书 + 仓库，自带配套检查。
    // 先检查、后转移：检查抛异常时，两个按值传进来的实参还完好（强异常保证）。
    Tensor(TensorDesc desc, Buffer storage);

    // 工厂：连续布局的全零 Tensor，支持全部 Dtype（zeros 只管分配，不涉及编解码）。
    static Tensor zeros(std::vector<std::int64_t> shape, Dtype dtype);

    // 工厂：float32 专用，元素个数必须等于 numel。
    static Tensor from_data(std::vector<std::int64_t> shape,
                            std::initializer_list<float> data);

    const TensorDesc& desc() const { return desc_; }
    int rank() const { return desc_.rank(); }
    std::int64_t numel() const { return desc_.numel(); }
    std::size_t nbytes() const { return desc_.nbytes(); }
    bool is_contiguous() const { return desc_.is_contiguous(); }

    // 空壳 = 不持有存储（默认构造或已被移动），沿用第 5 天的约定：
    // 空壳只允许判空、析构、赋新值。
    bool empty() const { return storage_.empty(); }

    // 借用仓库（只读），不转让所有权。
    const Buffer& storage() const { return storage_; }

    // 元素访问。防线从外到里：
    //   ① require_float32：今天的读写只做 float32；
    //   ② element_offset：下标个数 = 秩、逐维边界（第 4 天的检查）——
    //      moved-from 的 Tensor 连说明书（vector）都被搬空，秩先变 0，误用在这里就被拦下；
    //   ③ 空壳检查：秩恰好对上却不持有存储（如默认构造后 at({})）时兜底。
    //      第 5 天错误二（整型 shape 还在 + 空指针）在这层翻车成 SEGV，今天全是可读异常。
    // 配套检查在构造期就保证了：合法下标算出的元素位置一定在仓库范围内。
    float at(std::initializer_list<std::int64_t> idx) const;   // 读：值拷贝，永不悬垂
    float& at(std::initializer_list<std::int64_t> idx);        // 写：借用，主人要活得比引用久

    std::string info() const;       // 一行元信息
    std::string to_string() const;  // 元信息 + 按 desc 解释的数据

private:
    // 配套检查：说明书最远一格 ≤ 仓库容量（元素单位）。第 4 天欠的账。
    static void check_fit(const TensorDesc& desc, const Buffer& storage);

    void require_float32(const char* who) const;

    // 全部检查通过后，返回元素位置（元素单位，0 起）。
    std::int64_t checked_element(const std::int64_t* idx, std::size_t n) const;

    const float* element_ptr(std::int64_t elem) const;
    float* element_ptr(std::int64_t elem);

    // to_string 的递归打印：打印第 dim 维的一个切片。
    static void append_slice(const Tensor& t, std::vector<std::int64_t>& idx,
                             std::size_t dim, std::string& out);

    TensorDesc desc_;   // 说明书：纯值类型，移动 = 拷贝
    Buffer storage_;    // 仓库：独占所有权，移动 = 换主人
};
