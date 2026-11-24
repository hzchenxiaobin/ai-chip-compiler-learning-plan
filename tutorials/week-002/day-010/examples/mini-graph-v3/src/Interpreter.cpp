#include "Interpreter.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

#include "Node.h"
#include "Value.h"

namespace {

// 按二维 shape 取元素；transpose 时交换下标。
double at(const std::vector<double>& data, std::int64_t cols, std::int64_t r,
          std::int64_t c, bool transposed) {
    if (transposed) {
        std::swap(r, c);
    }
    return data[static_cast<std::size_t>(r * cols + c)];
}

}  // namespace

void Interpreter::bind(const Value* input, std::vector<double> data) {
    if (static_cast<std::int64_t>(data.size()) != input->type().num_elements()) {
        throw std::invalid_argument("bind: %" + input->name() + " 需要 " +
                                    std::to_string(input->type().num_elements()) +
                                    " 个元素，实给 " + std::to_string(data.size()) + " 个");
    }
    storage_[input] = std::move(data);
}

void Interpreter::run(const Graph& g) {
    for (const Node* n : g.topological_order()) {
        const TensorType& out = n->result()->type();
        std::vector<double> result(static_cast<std::size_t>(out.num_elements()), 0.0);

        switch (n->kind()) {
            case OpKind::Constant:
                result = n->attrs().data;  // 常量值一直在属性里，直接抄
                break;
            case OpKind::MatMul: {
                const std::vector<double>& a = of(n->input(0));
                const std::vector<double>& b = of(n->input(1));
                const std::int64_t m = out.shape[0];
                const std::int64_t k = n->input(0)->type().shape[n->attrs().transpose_a ? 0 : 1];
                const std::int64_t n_dim = out.shape[1];
                const auto& ta = n->input(0)->type().shape;
                const auto& tb = n->input(1)->type().shape;
                for (std::int64_t i = 0; i < m; ++i) {
                    for (std::int64_t j = 0; j < n_dim; ++j) {
                        double sum = 0.0;
                        for (std::int64_t p = 0; p < k; ++p) {
                            sum += at(a, ta[1], i, p, n->attrs().transpose_a) *
                                   at(b, tb[1], p, j, n->attrs().transpose_b);
                        }
                        result[static_cast<std::size_t>(i * n_dim + j)] = sum;
                    }
                }
                break;
            }
            case OpKind::Add: {
                const std::vector<double>& x = of(n->input(0));
                const std::vector<double>& y = of(n->input(1));
                for (std::size_t i = 0; i < x.size(); ++i) {
                    result[i] = x[i] + y[i];
                }
                break;
            }
            case OpKind::Relu: {
                const std::vector<double>& x = of(n->input(0));
                for (std::size_t i = 0; i < x.size(); ++i) {
                    result[i] = std::max(0.0, x[i]);
                }
                break;
            }
        }
        storage_[n->result()] = std::move(result);
    }
}

const std::vector<double>& Interpreter::of(const Value* v) const {
    auto it = storage_.find(v);
    if (it == storage_.end()) {
        throw std::invalid_argument("解释器: %" + v->name() + " 没有数据（输入未绑定？）");
    }
    return it->second;
}
