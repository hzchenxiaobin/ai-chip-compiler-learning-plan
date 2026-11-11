// 错误二：说明书装不进仓库——第 4 天 TensorDesc 自己查不了的事，今天由 Tensor 构造期兜住。
// shape (2,3)、strides (5,1) 的最远元素 = 1×5 + 2×1 = 7，需要 8 格；仓库只有 6 格。
#include "Buffer.h"
#include "Tensor.h"
#include "TensorDesc.h"
#include <cstdio>
#include <stdexcept>

int main() {
    TensorDesc bad_desc({2, 3}, Dtype::Float32, {5, 1});  // 说明书自身合法：维数、非负都对
    std::printf("说明书本身写得通：%s\n", bad_desc.to_string().c_str());
    std::printf("但仓库只有 24 字节（6 格）...\n");
    try {
        Tensor bad(std::move(bad_desc), Buffer(24));
        (void)bad;
        std::printf("不应该走到这里\n");
    } catch (const std::invalid_argument& e) {
        std::printf("caught: %s\n", e.what());
    }
    // 同一份说明书配大仓库（32 字节 = 8 格）就装得下
    Tensor good(TensorDesc({2, 3}, Dtype::Float32, {5, 1}), Buffer(32));
    std::printf("换成 32 字节仓库：at({1,2}) 落在元素 %lld，读出 %g\n",
                static_cast<long long>(good.desc().element_offset({1, 2})), good.at({1, 2}));
    return 0;
}
