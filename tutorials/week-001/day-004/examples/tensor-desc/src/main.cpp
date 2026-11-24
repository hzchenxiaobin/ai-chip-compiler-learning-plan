#include "TensorDesc.h"

#include <cstdio>
#include <vector>

// 今天 TensorDesc 只描述“怎么取数”，数据先用一个普通数组顶着。
// 第 6 天的 Tensor = TensorDesc（说明书）＋ Buffer（真正的存储）。

// 安全读取：TensorDesc 自己不知道底层存储多大（这是它的设计边界），
// 观察程序替它做越界检查，顺便模拟“编译器按说明书取数”。
static int read_at(const std::vector<int>& storage, const TensorDesc& d,
                   std::initializer_list<std::int64_t> idx) {
    std::int64_t off = d.element_offset(idx);
    if (off < 0 || off >= static_cast<std::int64_t>(storage.size())) {
        std::printf("  【越界】元素 %lld 超出存储的 0..%zu\n",
                    static_cast<long long>(off), storage.size() - 1);
        return -1;
    }
    return storage[static_cast<std::size_t>(off)];
}

static void dump_2d(const char* name, const TensorDesc& d, const std::vector<int>& storage) {
    std::printf("%s：shape=(%lld,%lld) strides=(%lld,%lld) offset=%lld dtype=int32\n",
                name, d.shape()[0], d.shape()[1], d.strides()[0], d.strides()[1],
                d.storage_offset());
    for (std::int64_t i = 0; i < d.shape()[0]; ++i) {
        for (std::int64_t j = 0; j < d.shape()[1]; ++j) {
            std::int64_t off = d.element_offset({i, j});
            std::printf("  %s(%lld,%lld) → 元素 %lld → 值 %d\n", name,
                        static_cast<long long>(i), static_cast<long long>(j),
                        static_cast<long long>(off), read_at(storage, d, {i, j}));
        }
    }
    std::printf("  元素数 numel = %lld，字节数 nbytes = %zu，连续？ %s\n\n",
                static_cast<long long>(d.numel()), d.nbytes(),
                d.is_contiguous() ? "yes" : "no");
}

int main() {
    std::printf("== 0. 数据准备：一块 6 个 int32 的底层存储 ==\n");
    std::vector<int> storage = {1, 2, 3, 4, 5, 6};
    std::printf("storage = [");
    for (std::size_t i = 0; i < storage.size(); ++i) {
        std::printf("%d%s", storage[i], i + 1 == storage.size() ? "" : ", ");
    }
    std::printf("]  （%zu 字节，每个 int32 占 %zu 字节）\n\n",
                storage.size() * sizeof(int), sizeof(int));

    std::printf("== 1. 视图 A：行主序 (2,3)，说明书由 make_contiguous 推导 ==\n");
    TensorDesc a = TensorDesc::make_contiguous({2, 3}, Dtype::Int32);
    dump_2d("A", a, storage);

    std::printf("== 2. 视图 B = A 的转置 (3,2)：只改元信息，数据一比特不动 ==\n");
    TensorDesc b({3, 2}, Dtype::Int32, {1, 3}, 0);  // 交换 A 的 strides
    dump_2d("B", b, storage);
    std::printf("  对照：A(1,2) 与 B(2,1) 的元素位置都是 %lld —— 同一个格子，两种坐标。\n\n",
                static_cast<long long>(a.element_offset({1, 2})));

    std::printf("== 3. 视图 C = 拉平 (6,)：仍是同一块存储 ==\n");
    TensorDesc c({6}, Dtype::Int32, {1}, 0);
    std::printf("C：%s\n", c.to_string().c_str());
    std::printf("  C(4) → 元素 %lld → 值 %d；连续？ %s\n\n",
                static_cast<long long>(c.element_offset({4})),
                read_at(storage, c, {4}), c.is_contiguous() ? "yes" : "no");

    std::printf("== 4. 三维 (2,2,3)：行主序 strides 由外向内 6,3,1 ==\n");
    TensorDesc d3 = TensorDesc::make_contiguous({2, 2, 3}, Dtype::Int32);
    std::printf("D3：%s\n", d3.to_string().c_str());
    std::printf("  D3(1,1,2) → 元素 %lld（= 1×6 + 1×3 + 2×1）；连续？ %s\n\n",
                static_cast<long long>(d3.element_offset({1, 1, 2})),
                d3.is_contiguous() ? "yes" : "no");

    std::printf("== 5. 切片视图 E = A[1,:]（第 2 行）：shape 变小，offset 前移 ==\n");
    TensorDesc e({3}, Dtype::Int32, {1}, 3);  // 从底层第 3 个元素开始
    std::printf("E：%s\n", e.to_string().c_str());
    std::printf("  E(0) → 元素 %lld → 值 %d\n", static_cast<long long>(e.element_offset({0})),
                read_at(storage, e, {0}));
    std::printf("  E(2) → 元素 %lld → 值 %d\n", static_cast<long long>(e.element_offset({2})),
                read_at(storage, e, {2}));
    std::printf("  连续？ %s（storage_offset 不参与连续性判断）\n\n", e.is_contiguous() ? "yes" : "no");

    std::printf("== 6. 换个 Dtype：同样的 (2,3)，float16 只要 12 字节 ==\n");
    TensorDesc f = TensorDesc::make_contiguous({2, 3}, Dtype::Float16);
    std::printf("F：%s\n  numel = %lld，nbytes = %zu；A(1,2) 的字节位置 = %lld，F(1,2) 的字节位置 = %lld\n",
                f.to_string().c_str(), static_cast<long long>(f.numel()), f.nbytes(),
                static_cast<long long>(a.byte_offset({1, 2})),
                static_cast<long long>(f.byte_offset({1, 2})));
    return 0;
}
