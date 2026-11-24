#include "Graph.h"

#include <functional>
#include <stdexcept>
#include <utility>

#include "Node.h"
#include "Value.h"

namespace {

// 廉价检查：构造时就该发现的错误直接抛异常。
// 注意这不是 Verifier（第 12 天）：是否属于本图、输出是否合法等全套检查不在今天。
void require(bool ok, const std::string& msg) {
    if (!ok) {
        throw std::invalid_argument(msg);
    }
}

// 打印 double：去掉多余的尾零（1 → "1"，2.5 → "2.5"），让 IR 可读。
std::string trim_number(double v) {
    std::string s = std::to_string(v);
    s.erase(s.find_last_not_of('0') + 1, std::string::npos);
    if (!s.empty() && s.back() == '.') {
        s.pop_back();
    }
    return s;
}

std::string where(const Value* v) {
    return "（输入 %" + v->name() + " : " + v->type().to_string() + "）";
}

}  // namespace

Value* Graph::add_input(std::string name, TensorType type) {
    // make_unique 无法调用 private 构造（friend 不会传递给它），
    // 所以由唯一所有人 Graph 亲自 new——友元关系恰好覆盖这一行。
    std::unique_ptr<Value> value(new Value(next_value_id_++, std::move(name), std::move(type)));
    Value* raw = value.get();
    values_.push_back(std::move(value));
    inputs_.push_back(raw);
    return raw;
}

Node* Graph::make_node(OpKind kind, std::vector<const Value*> inputs, Attrs attrs,
                       TensorType result_type, std::string result_name) {
    for (std::size_t i = 0; i < inputs.size(); ++i) {
        require(inputs[i] != nullptr,
                op_name(kind) + ": 第 " + std::to_string(i) + " 个输入是空指针");
    }

    // 1) 先造结果值，再造节点——两样都归图所有，地址从此稳定；
    // 2) 节点借用结果、结果回指生产者（双向借用，不构成所有权环）。
    std::unique_ptr<Value> result(
        new Value(next_value_id_++, std::move(result_name), std::move(result_type)));
    std::unique_ptr<Node> node(
        new Node(next_node_id_++, kind, std::move(inputs), std::move(attrs)));
    node->result_ = result.get();
    result->producer_ = node.get();

    Node* raw = node.get();
    values_.push_back(std::move(result));
    nodes_.push_back(std::move(node));
    return raw;
}

Node* Graph::add_constant(std::string result_name, TensorType type, std::vector<double> data) {
    // 想记录结果的 Shape，就必须先确认数据个数对得上——
    // 这是「记录」的一部分，不是提前实现 Verifier。
    require(data.size() == static_cast<std::size_t>(type.num_elements()),
            "constant: 数据个数 " + std::to_string(data.size()) + " 与元素数 " +
                std::to_string(type.num_elements()) + " 不符（" + type.to_string() + "）");
    Attrs attrs;
    attrs.data = std::move(data);
    return make_node(OpKind::Constant, {}, std::move(attrs), std::move(type),
                     std::move(result_name));
}

Node* Graph::add_matmul(const Value* a, const Value* b, std::string result_name,
                        bool transpose_a, bool transpose_b) {
    require(a != nullptr && b != nullptr, "matmul: 输入是空指针");
    const TensorType& ta = a->type();
    const TensorType& tb = b->type();
    require(ta.rank() == 2 && tb.rank() == 2,
            "matmul: 今天只支持二维" + where(a) + where(b));
    require(ta.dtype == tb.dtype,
            "matmul: dtype 不一致 " + dtype_name(ta.dtype) + " vs " + dtype_name(tb.dtype));

    // 有效形状：transpose 只影响「怎么读」，不改动存储（第 57 天再展开布局话题）。
    const std::int64_t m = transpose_a ? ta.shape[1] : ta.shape[0];
    const std::int64_t k = transpose_a ? ta.shape[0] : ta.shape[1];
    const std::int64_t k2 = transpose_b ? tb.shape[1] : tb.shape[0];
    const std::int64_t n = transpose_b ? tb.shape[0] : tb.shape[1];
    require(k == k2, "matmul: 内维不匹配 " + std::to_string(k) + " vs " + std::to_string(k2) +
                         where(a) + where(b));

    TensorType out{ta.dtype, {m, n}};
    Attrs attrs;
    attrs.transpose_a = transpose_a;
    attrs.transpose_b = transpose_b;
    return make_node(OpKind::MatMul, {a, b}, std::move(attrs), std::move(out),
                     std::move(result_name));
}

Node* Graph::add_elementwise(OpKind kind, const Value* x, const Value* y,
                             std::string result_name) {
    require(x != nullptr && y != nullptr, op_name(kind) + ": 输入是空指针");
    // 今天只支持完全一致的类型（dtype + shape 都相同）；
    // 广播是第 60 天的话题，这里明确拒绝。
    require(x->type() == y->type(),
            op_name(kind) + ": 类型必须完全一致 " + where(x) +
                " vs " + where(y));
    return make_node(kind, {x, y}, Attrs{}, x->type(), std::move(result_name));
}

Node* Graph::add_relu(const Value* x, std::string result_name) {
    require(x != nullptr, "relu: 输入是空指针");
    return make_node(OpKind::Relu, {x}, Attrs{}, x->type(), std::move(result_name));
}

void Graph::mark_output(const Value* v) {
    require(v != nullptr, "mark_output: 输出是空指针");
    outputs_.push_back(v);
}

std::vector<const Node*> Graph::topological_order() const {
    std::vector<const Node*> order;
    std::vector<char> visited(static_cast<std::size_t>(num_nodes()), 0);

    // DFS 后序：先把输入的依赖走完，再记录自己 → 依赖一定排在前面。
    std::function<void(const Node*)> visit = [&](const Node* n) {
        if (visited[static_cast<std::size_t>(n->id())]) {
            return;
        }
        visited[static_cast<std::size_t>(n->id())] = 1;
        for (const Value* in : n->inputs()) {
            if (const Node* producer = in->producer()) {
                visit(producer);
            }
        }
        order.push_back(n);
    };
    for (const std::unique_ptr<Node>& n : nodes_) {
        visit(n.get());
    }
    return order;
}

std::string Graph::to_string() const {
    std::string text = "graph \"" + name_ + "\" (" + std::to_string(inputs_.size()) +
                       " inputs, " + std::to_string(outputs_.size()) + " outputs) {\n";
    for (const Value* v : inputs_) {
        text += "  %" + v->name() + " = input : " + v->type().to_string() + "\n";
    }
    for (const std::unique_ptr<Node>& n : nodes_) {
        text += "  %n" + std::to_string(n->id()) + " = " + op_name(n->kind()) + "(";
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            if (i != 0) {
                text += ", ";
            }
            text += "%" + n->input(i)->name();
        }
        text += ")";
        // 属性：只打印非默认值，跟在算子名后面（MLIR 风格）。
        if (n->kind() == OpKind::Constant) {
            text += " {data = [";
            for (std::size_t i = 0; i < n->attrs().data.size(); ++i) {
                if (i != 0) {
                    text += ", ";
                }
                text += trim_number(n->attrs().data[i]);
            }
            text += "]}";
        } else if (n->attrs().transpose_a || n->attrs().transpose_b) {
            text += " {";
            if (n->attrs().transpose_a) {
                text += "transpose_a";
            }
            if (n->attrs().transpose_b) {
                if (n->attrs().transpose_a) {
                    text += ", ";
                }
                text += "transpose_b";
            }
            text += "}";
        }
        text += " -> %" + n->result()->name() + " : " + n->result()->type().to_string() + "\n";
    }
    for (const Value* v : outputs_) {
        text += "  output %" + v->name() + "\n";
    }
    text += "}";
    return text;
}
