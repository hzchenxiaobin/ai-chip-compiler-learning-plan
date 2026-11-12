#include "Graph.h"

#include <algorithm>
#include <functional>
#include <stdexcept>
#include <unordered_set>
#include <utility>

#include "Node.h"
#include "NodeVisitor.h"
#include "Value.h"

namespace {

// 廉价检查：构造/变换时就该发现的错误直接抛异常。
// 注意这不是 Verifier（第 12 天）：全套合法性检查不在今天。
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

// 输入槽的类型是 const Value*（节点只读它的数据），但登记/注销 use
// 必须改 Value 的账本。值本体住在 values_ 里、生来非 const，
// 只有 Graph 会做这个 const_cast——写权限收在唯一登记员手里。
Value* mutable_value(const Value* v) {
    return const_cast<Value*>(v);
}

// 第 11 天：to_string() 的「节点行」打印改走 Visitor。
// 这个类只负责每个节点那一行（属性段随算子不同），
// 图的框架（头部、输入表、输出表）仍由 to_string() 自己负责。
// 输出必须与 v3 的 if/else 版本一字不差——
// tests/test_visitor.cpp 用整串字面量比较盯着这一点。
class NodeLinePrinter : public NodeVisitor {
public:
    explicit NodeLinePrinter(std::string& out) : out_(out) {}

    void visit_constant(const Node& n) override {
        head(n);
        out_ += " {data = [";
        for (std::size_t i = 0; i < n.attrs().data.size(); ++i) {
            if (i != 0) {
                out_ += ", ";
            }
            out_ += trim_number(n.attrs().data[i]);
        }
        out_ += "]}";
        tail(n);
    }

    void visit_matmul(const Node& n) override {
        head(n);
        if (n.attrs().transpose_a || n.attrs().transpose_b) {
            out_ += " {";
            if (n.attrs().transpose_a) {
                out_ += "transpose_a";
            }
            if (n.attrs().transpose_b) {
                if (n.attrs().transpose_a) {
                    out_ += ", ";
                }
                out_ += "transpose_b";
            }
            out_ += "}";
        }
        tail(n);
    }

    void visit_add(const Node& n) override { head(n); tail(n); }
    void visit_relu(const Node& n) override { head(n); tail(n); }

private:
    // 公共段："  %n1 = matmul(%A, %B)"——与算子无关的部分放这里。
    void head(const Node& n) {
        out_ += "  %n" + std::to_string(n.id()) + " = " + op_name(n.kind()) + "(";
        for (std::size_t i = 0; i < n.num_inputs(); ++i) {
            if (i != 0) {
                out_ += ", ";
            }
            out_ += "%" + n.input(i)->name();
        }
        out_ += ")";
    }

    // 公共段：" -> %C : f32<2x2>\n"。
    void tail(const Node& n) {
        out_ += " -> %" + n.result()->name() + " : " + n.result()->type().to_string() + "\n";
    }

    std::string& out_;
};

}  // namespace

Value* Graph::add_input(std::string name, TensorType type) {
    std::unique_ptr<Value> value(new Value(next_value_id_++, std::move(name), std::move(type)));
    Value* raw = value.get();
    values_.push_back(std::move(value));
    inputs_.push_back(raw);
    return raw;
}

Node* Graph::make_node_impl(OpKind kind, std::vector<const Value*> inputs, Attrs attrs,
                            TensorType result_type, std::string result_name, bool check_nulls) {
    if (check_nulls) {
        for (std::size_t i = 0; i < inputs.size(); ++i) {
            require(inputs[i] != nullptr,
                    op_name(kind) + ": 第 " + std::to_string(i) + " 个输入是空指针");
        }
    }

    // 1) 先造结果值，再造节点——两样都归图所有，地址从此稳定；
    // 2) 节点借用结果、结果回指生产者（def 双向可见）；
    // 3) 登记使用：第 i 个输入槽用了我，就往我的账本里写一条 (我, i)。
    //    raw 路径的空槽不登记——nullptr 没有账本可写；这条「缺失的
    //    记录」正是 Verifier 账本检查要抓的缺口之一。
    std::unique_ptr<Value> result(
        new Value(next_value_id_++, std::move(result_name), std::move(result_type)));
    std::unique_ptr<Node> node(
        new Node(next_node_id_++, kind, std::move(inputs), std::move(attrs)));
    node->result_ = result.get();
    result->producer_ = node.get();

    Node* raw = node.get();
    for (std::size_t i = 0; i < raw->inputs_.size(); ++i) {
        if (raw->inputs_[i] != nullptr) {
            mutable_value(raw->inputs_[i])->uses_.push_back(Use{raw, i});
        }
    }

    values_.push_back(std::move(result));
    nodes_.push_back(std::move(node));
    return raw;
}

Node* Graph::add_raw_node(OpKind kind, std::vector<const Value*> inputs, Attrs attrs,
                          TensorType result_type, std::string result_name) {
    return make_node_impl(kind, std::move(inputs), std::move(attrs), std::move(result_type),
                          std::move(result_name), /*check_nulls=*/false);
}

Node* Graph::add_constant(std::string result_name, TensorType type, std::vector<double> data) {
    require(data.size() == static_cast<std::size_t>(type.num_elements()),
            "constant: 数据个数 " + std::to_string(data.size()) + " 与元素数 " +
                std::to_string(type.num_elements()) + " 不符（" + type.to_string() + "）");
    Attrs attrs;
    attrs.data = std::move(data);
    return make_node_impl(OpKind::Constant, {}, std::move(attrs), std::move(type),
                          std::move(result_name), /*check_nulls=*/true);
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
    return make_node_impl(OpKind::MatMul, {a, b}, std::move(attrs), std::move(out),
                          std::move(result_name), /*check_nulls=*/true);
}

Node* Graph::add_elementwise(OpKind kind, const Value* x, const Value* y,
                             std::string result_name) {
    require(x != nullptr && y != nullptr, op_name(kind) + ": 输入是空指针");
    require(x->type() == y->type(),
            op_name(kind) + ": 类型必须完全一致 " + where(x) + " vs " + where(y));
    return make_node_impl(kind, {x, y}, Attrs{}, x->type(), std::move(result_name),
                          /*check_nulls=*/true);
}

Node* Graph::add_relu(const Value* x, std::string result_name) {
    require(x != nullptr, "relu: 输入是空指针");
    return make_node_impl(OpKind::Relu, {x}, Attrs{}, x->type(), std::move(result_name),
                          /*check_nulls=*/true);
}

void Graph::mark_output(const Value* v) {
    require(v != nullptr, "mark_output: 输出是空指针");
    outputs_.push_back(v);
}

void Graph::replace_all_uses_of(const Value* from, const Value* to) {
    require(from != nullptr && to != nullptr, "replace: 空指针");
    require(from != to, "replace: from 和 to 是同一个值 %" + from->name());
    require(from->type() == to->type(),
            "replace: 类型不一致 %" + from->name() + " : " + from->type().to_string() +
                " vs %" + to->name() + " : " + to->type().to_string());

    // 先把账本拷一份再遍历：改写输入槽的同时会往 to 的账本里添记录，
    // 若 to 恰好也是 from 的使用者，边遍历边改 from->uses_ 就是
    // 「迭代中修改容器」的经典错误（漏改、越界都可能出现）。
    const std::vector<Use> moved = from->uses_;
    for (const Use& u : moved) {
        u.user->inputs_[u.operand] = to;  // 槽位改指向 to（Graph 是 Node 的友元）
        mutable_value(to)->uses_.push_back(u);
    }
    mutable_value(from)->uses_.clear();
    // 不变量保持：每个指向 to 的槽位，to 的账本里恰有一条对应记录；
    // from 的账本清空，从此无人使用 from——但节点还活着，删除是另一步。
}

void Graph::erase_node(Node* n) {
    require(n != nullptr, "erase_node: 空指针");
    const auto node_it = std::find_if(
        nodes_.begin(), nodes_.end(),
        [n](const std::unique_ptr<Node>& p) { return p.get() == n; });
    require(node_it != nodes_.end(), "erase_node: 节点不属于本图");

    // 删节点的前提：它的结果没人用、也不是图输出。
    // 图输出也是「使用者」——只是不住在 use 表里，住在 outputs_ 里
    //（第 25 天 DCE 的规则同款：无使用者的纯算子可删，图输出必须保留）。
    const Value* result = n->result_;
    if (result->has_uses()) {
        std::string users;
        for (const Use& u : result->users()) {
            users += " " + op_name(u.user->kind()) + "%n" + std::to_string(u.user->id()) +
                     "(第" + std::to_string(u.operand) + "槽)";
        }
        throw std::invalid_argument("erase_node: %" + result->name() + " 仍有 " +
                                    std::to_string(result->num_uses()) + " 个使用者：" + users);
    }
    require(std::find(outputs_.begin(), outputs_.end(), result) == outputs_.end(),
            "erase_node: %" + result->name() + " 是图输出，不能删除");

    // 1) 注销本节点的全部使用登记：第 i 个槽不再使用 inputs_[i]。
    for (std::size_t i = 0; i < n->inputs_.size(); ++i) {
        remove_use(mutable_value(n->inputs_[i]), n, i);
    }
    // 2) 从所有人名单里摘掉结果值和节点本体（unique_ptr 在此析构）。
    values_.erase(std::remove_if(values_.begin(), values_.end(),
                                 [result](const std::unique_ptr<Value>& p) {
                                     return p.get() == result;
                                 }),
                  values_.end());
    nodes_.erase(node_it);
    // 从这一行起，n 和 result 的指针全部失效——调用方不许再碰。
}

void Graph::remove_use(Value* v, const Node* n, std::size_t operand) {
    const auto it = std::remove_if(v->uses_.begin(), v->uses_.end(),
                                   [n, operand](const Use& u) {
                                       return u.user == n && u.operand == operand;
                                   });
    v->uses_.erase(it, v->uses_.end());
    // 不变量说这里恰好删掉一条；用 remove_if 而不是定位单条，
    // 是为了将来放宽不变量时（如允许重复槽位）不用回来改这里。
}

std::vector<const Node*> Graph::topological_order() const {
    std::vector<const Node*> order;
    // 用指针做键，而不是「id 当下标」：erase_node 之后 id 不再连续，
    // 拿 id 索引数组会越界（这个坑是今天真实踩到并修复的，见正文第 6 节）。
    std::unordered_set<const Node*> visited;

    std::function<void(const Node*)> visit = [&](const Node* n) {
        if (!visited.insert(n).second) {
            return;
        }
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
    // 节点行改走 Visitor：kind 的分发收拢到 apply_visitor 的唯一 switch，
    // 本函数只剩「图的框架」。新增一种算子时，这里一行不用改。
    NodeLinePrinter printer(text);
    for (const std::unique_ptr<Node>& n : nodes_) {
        apply_visitor(printer, *n);
    }
    for (const Value* v : outputs_) {
        text += "  output %" + v->name() + "\n";
    }
    text += "}";
    return text;
}

std::string Graph::uses_to_string() const {
    std::string text = "use 表（def 在左，use 在右）\n";
    for (const std::unique_ptr<Value>& v : values_) {
        text += "  %" + v->name() + "\tdef: ";
        if (v->producer() == nullptr) {
            text += "图输入    \t";
        } else {
            text += op_name(v->producer()->kind()) + "%n" +
                    std::to_string(v->producer()->id()) + "\t";
        }
        text += "uses: ";
        if (v->uses_.empty()) {
            const bool is_output =
                std::find(outputs_.begin(), outputs_.end(), v.get()) != outputs_.end();
            text += is_output ? "（无节点使用，图输出）" : "（无）";
        }
        for (const Use& u : v->uses_) {
            text += op_name(u.user->kind()) + "%n" + std::to_string(u.user->id()) +
                    "(第" + std::to_string(u.operand) + "槽) ";
        }
        text += "\n";
    }
    return text;
}
