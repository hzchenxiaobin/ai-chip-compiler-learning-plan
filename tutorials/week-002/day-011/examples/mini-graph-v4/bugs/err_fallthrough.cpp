// 反面教材：手写 switch 漏了一个 break——add 的 case 直接掉进 relu，
// 计数悄悄翻倍。这正是「分发散落在用户代码里」的日常事故：
// 图能跑、数字看着也像回事，只有对照真相时才露馅。
// -Wextra 会给一行 -Wimplicit-fallthrough 警告——但你不看警告它就不存在。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -Wall -Wextra -I ../src ../src/Graph.cpp ../src/Interpreter.cpp err_fallthrough.cpp -o err_fallthrough && ./err_fallthrough
#include <cstdio>
#include <memory>

#include "Graph.h"
#include "Node.h"
#include "NodeVisitor.h"
#include "OpKind.h"
#include "Value.h"

namespace {

// 对照组：用今天的 apply_visitor 数 relu——分发入口只有一份、
// 每个节点恰好一次，想写漏都没地方下手。
int count_relu_visitor(const Graph& g) {
    int relu_count = 0;
    class ReluCounter : public NodeVisitor {
    public:
        void visit_constant(const Node&) override {}
        void visit_matmul(const Node&) override {}
        void visit_add(const Node&) override {}
        void visit_relu(const Node&) override { ++count; }
        int count = 0;
    } counter;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        apply_visitor(counter, *n);
    }
    relu_count = counter.count;
    return relu_count;
}

}  // namespace

int main() {
    Graph g("g");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    g.add_constant("bias", {Dtype::F32, {2, 2}}, {0, -100, -150, -50});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), g.nodes()[0]->result(), "D");
    Node* relu = g.add_relu(add->result(), "Y");
    g.mark_output(relu->result());

    // 事故现场：数完 add 忘了 break，直接掉进 relu 的 case。
    int add_count = 0;
    int relu_count = 0;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        switch (n->kind()) {
            case OpKind::Constant: break;
            case OpKind::MatMul:   break;
            case OpKind::Add:  ++add_count;    // ← 这里漏了 break
            case OpKind::Relu: ++relu_count; break;
        }
    }

    const int truth = count_relu_visitor(g);
    std::printf("图中 relu 实际 %d 个；手写 switch 数出 %d 个（add 掉进来背了锅）。\n",
                truth, relu_count);
    std::printf("编译时其实给过提示：-Wimplicit-fallthrough（在 -Wextra 里）。\n");
    return 0;
}
