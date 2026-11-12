#include "Frontend.h"

#include <cstddef>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>

#include "Node.h"
#include "Value.h"

// 今天唯一的主题：从模型算子到图 IR 的映射。
// 模型世界用「字符串名字」引用张量；IR 世界用「对象身份」（指针）引用值。
// lower_model_to_graph 按拓扑序走一遍层列表，把每个名字换成对象：
//
//   图输入（运行期数据）      → add_input 造的 Value（producer 为空）
//   权重 initializer（常数据）→ add_constant 造的 Constant 节点
//   层（字符串算子名）        → OpKind 枚举 + 工厂函数造的 Node
//   层属性（transpose…）      → Attrs（原样搬运，非 MatMul 带属性会被拒）
//   层之间的名字连接          → 输入槽里的指针（经符号表翻译）
//   图输出（名字）            → mark_output（经符号表反查）
//
// 三条纪律，全部来自前几天的教训：
//   1) 名字唯一：两个定义撞名会被当场拒绝——名字是模型世界的身份，
//      身份模糊会让文本 IR 产生两个 %C（第 13 天 bugs/err_shadowed_name.cpp）；
//   2) 定义先于使用：层必须按拓扑序排列（ONNX 同款契约）。查不到名字时
//      区分「乱序」（后面才定义）和「拼错」（根本没有），报错各自成句；
//   3) 错误消息带上下文：第几层、第几个输入槽、哪个名字。工厂只认得
//      指针不认得名字——认得名字的报错只有前端能做，这是它的岗位价值。

namespace {

[[noreturn]] void fail(const std::string& msg) {
    throw std::invalid_argument(msg);
}

std::string quote(const std::string& s) {
    return "\"" + s + "\"";
}

// 错误消息里的位置：如「第 2 层 add」。
std::string layer_where(std::size_t index, const ModelLayer& l) {
    return "第 " + std::to_string(index + 1) + " 层 " + l.op;
}

std::string count_of(std::size_t n) {
    return std::to_string(n) + " 个";
}

}  // namespace

Graph lower_model_to_graph(const Model& m) {
    Graph g(m.name);

    // 符号表：名字 → 值。两个世界之间唯一的桥。
    std::unordered_map<std::string, const Value*> named;
    // 「后面的层才定义的名字」集合：把乱序和拼错区分开，诊断更准。
    // 代价只是一遍层列表的预扫描。
    std::unordered_set<std::string> defined_later;
    for (const ModelLayer& l : m.layers) {
        defined_later.insert(l.output);
    }

    // 登记一个新名字；重名当场拒绝。
    const auto define = [&](const std::string& name, const Value* v, const std::string& who) {
        if (!named.emplace(name, v).second) {
            fail("lower: " + who + "：名字 " + quote(name) +
                 " 已存在——模型世界一个名字只许一个定义");
        }
    };

    // 用名字查值；查不到时区分「乱序」与「拼错」。
    const auto resolve = [&](const std::string& name, const std::string& who) -> const Value* {
        const auto it = named.find(name);
        if (it != named.end()) {
            return it->second;
        }
        if (defined_later.count(name) != 0) {
            fail("lower: " + who + " " + quote(name) +
                 " 还没有生产者——层的顺序必须是拓扑序（" + quote(name) +
                 " 在后面的层里才定义）");
        }
        fail("lower: " + who + " " + quote(name) +
             " 在整个模型里都不存在（拼错名字？忘了声明？）");
    };

    // ---- 1) 图输入：运行期数据，住在图的边界上 ----
    for (const ModelInput& in : m.inputs) {
        define(in.name, g.add_input(in.name, in.type), "图输入");
    }

    // ---- 2) 权重：编译期已知的数据，作为 Constant 节点进图 ----
    // 数据个数的预检查本可以交给 add_constant 的工厂守卫，但工厂只认得
    // 指针不认得名字——报错带上「哪个权重」只有前端能做。
    for (const ModelWeight& w : m.weights) {
        if (static_cast<std::int64_t>(w.data.size()) != w.type.num_elements()) {
            fail("lower: 权重 " + quote(w.name) + " 的数据 " + count_of(w.data.size()) +
                 "，与类型 " + w.type.to_string() + " 的元素数 " +
                 std::to_string(w.type.num_elements()) + " 不符");
        }
        define(w.name, g.add_constant(w.name, w.type, w.data)->result(), "权重");
    }

    // ---- 3) 层：字符串算子名 → OpKind + 工厂；名字连接 → 指针 ----
    for (std::size_t i = 0; i < m.layers.size(); ++i) {
        const ModelLayer& l = m.layers[i];
        const std::string where = layer_where(i, l);

        // 属性搬运的纪律：要么完整搬运，要么明确拒绝——静默丢弃
        // 是映射失真（模型说的事和图做的事从此不一致）。
        if (l.transpose_a || l.transpose_b) {
            if (l.op != "MatMul") {
                fail("lower: " + where + " 带着 transpose 属性，但 " + l.op +
                     " 没有这个属性——是放错层了？");
            }
        }

        // 名字世界的环：一层的输入是它自己的输出，且这个名字别处没有
        // 定义——「还没产生就想用」。名字撞上图输入的情况不走这里，
        // 由下面 define 的「已存在」点名（遮蔽与成环是两种病）。
        // 第 16 天的环检测会在可变图上再遇到它的亲戚。
        for (std::size_t j = 0; j < l.inputs.size(); ++j) {
            if (l.inputs[j] == l.output && named.find(l.inputs[j]) == named.end()) {
                fail("lower: " + where + " 的第 " + std::to_string(j) + " 个输入 " +
                     quote(l.inputs[j]) + " 是这一层自己的输出——值要先产生才能被用（名字成环）");
            }
        }

        // 输入名字 → 值。查不到就在这里报，带着层号和槽位。
        std::vector<const Value*> ins;
        ins.reserve(l.inputs.size());
        for (std::size_t j = 0; j < l.inputs.size(); ++j) {
            ins.push_back(resolve(l.inputs[j], where + " 的第 " + std::to_string(j) + " 个输入"));
        }

        Node* n = nullptr;
        if (l.op == "MatMul") {
            if (l.inputs.size() != 2) {
                fail("lower: " + where + " 需要 2 个输入，实际 " + count_of(l.inputs.size()));
            }
            // 类型/内维检查由工厂守卫负责（第 9 天）；属性在这里原样搬进 Attrs。
            n = g.add_matmul(ins[0], ins[1], l.output, l.transpose_a, l.transpose_b);
        } else if (l.op == "Add") {
            if (l.inputs.size() != 2) {
                fail("lower: " + where + " 需要 2 个输入，实际 " + count_of(l.inputs.size()));
            }
            n = g.add_elementwise(OpKind::Add, ins[0], ins[1], l.output);
        } else if (l.op == "Relu") {
            if (l.inputs.size() != 1) {
                fail("lower: " + where + " 需要 1 个输入，实际 " + count_of(l.inputs.size()));
            }
            n = g.add_relu(ins[0], l.output);
        } else if (l.op == "Constant") {
            // 常量不是层：模型世界把它放 weights（initializer），映射成
            // Constant 节点是前端的事，不是模型作者的事。
            fail("lower: " + where + " 想造常量——常量请放进 weights，不要作为层");
        } else {
            fail("lower: " + where + " 的算子名 " + quote(l.op) +
                 " 不认识（合法：MatMul / Add / Relu；常量放 weights）");
        }
        define(l.output, n->result(), where + " 的输出");
    }

    // ---- 4) 图输出：名字反查值。中间值也可以当输出（合法且常见）----
    std::unordered_set<std::string> seen_outputs;
    for (const std::string& out : m.outputs) {
        if (!seen_outputs.insert(out).second) {
            fail("lower: 图输出 " + quote(out) + " 写了两次");
        }
        g.mark_output(resolve(out, "图输出"));
    }

    // 按值返回：Graph 是 move-only，这里搬走的是 unique_ptr 名单
    //（第 8 天的「房产证」），节点和值一个都不动。
    return g;
}
