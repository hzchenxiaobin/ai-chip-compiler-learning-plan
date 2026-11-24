// 第 11 天的验收测试：Visitor 分发的正确性、只读性与重构安全性。
// 重构安全性是重点：Graph::to_string() 改走 NodeLinePrinter 之后，
// 输出必须与 v3 一字不差——这里用整串字面量比较盯着。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <string>
#include <utility>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "NodeVisitor.h"
#include "OpCardPrinter.h"
#include "OpKind.h"
#include "Value.h"

namespace {

int g_checks = 0;

#define CHECK(cond)                                                      \
    do {                                                                 \
        if (!(cond)) {                                                   \
            std::fprintf(stderr, "CHECK 失败：%s（第 %d 行）\n", #cond,   \
                         __LINE__);                                      \
            return 1;                                                    \
        }                                                                \
        ++g_checks;                                                      \
    } while (0)

// 经典图：Y = relu(A x B + bias)（第 9/10 天同款）。
struct Example {
    Graph graph{"matmul-bias-relu"};
    Value* a = nullptr;
    Value* b = nullptr;
    Node* bias = nullptr;
    Node* mm = nullptr;
    Node* add = nullptr;
    Node* relu = nullptr;

    Example() {
        a = graph.add_input("A", {Dtype::F32, {2, 3}});
        b = graph.add_input("B", {Dtype::F32, {3, 2}});
        bias = graph.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
        mm = graph.add_matmul(a, b, "C");
        add = graph.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
        relu = graph.add_relu(add->result(), "Y");
        graph.mark_output(relu->result());
    }
};

// 第 10 天的不变量检查，原样借来：访问者跑完后必须仍然成立。
bool use_def_consistent(const Graph& g) {
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            std::size_t cnt = 0;
            for (const Use& u : n->input(i)->users()) {
                if (u.user == n.get() && u.operand == i) {
                    ++cnt;
                }
            }
            if (cnt != 1) {
                return false;
            }
        }
    }
    for (const std::unique_ptr<Value>& v : g.values()) {
        for (const Use& u : v->users()) {
            if (u.user->input(u.operand) != v.get()) {
                return false;
            }
        }
    }
    return true;
}

// 记录每次分发的 (算子类型, 节点 id)，用于核对分发序列。
struct Call {
    OpKind kind;
    std::int64_t id;
};

class RecordingVisitor : public NodeVisitor {
public:
    void visit_constant(const Node& n) override { calls_.push_back({OpKind::Constant, n.id()}); }
    void visit_matmul(const Node& n) override { calls_.push_back({OpKind::MatMul, n.id()}); }
    void visit_add(const Node& n) override { calls_.push_back({OpKind::Add, n.id()}); }
    void visit_relu(const Node& n) override { calls_.push_back({OpKind::Relu, n.id()}); }
    void visit_mul(const Node& n) override { calls_.push_back({OpKind::Mul, n.id()}); }

    const std::vector<Call>& calls() const noexcept { return calls_; }
    std::size_t count_of(OpKind k) const {
        std::size_t c = 0;
        for (const Call& call : calls_) {
            if (call.kind == k) {
                ++c;
            }
        }
        return c;
    }

private:
    std::vector<Call> calls_;
};

// 计数访问者（与 main.cpp 里同款思路，独立实现一份给测试用）。
class CounterVisitor : public NodeVisitor {
public:
    void visit_constant(const Node&) override { ++constant_; }
    void visit_matmul(const Node&) override { ++matmul_; }
    void visit_add(const Node&) override { ++add_; }
    void visit_relu(const Node&) override { ++relu_; }
    void visit_mul(const Node&) override { ++mul_; }

    std::int64_t constant_ = 0, matmul_ = 0, add_ = 0, relu_ = 0, mul_ = 0;
};

void run_visitor(const Graph& g, NodeVisitor& v) {
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        apply_visitor(v, *n);
    }
}

}  // namespace

int main() {
    // ---------- 第 1 组：apply_visitor 的分发序列 ----------
    {
        Example ex;
        RecordingVisitor rec;
        run_visitor(ex.graph, rec);

        CHECK(rec.calls().size() == 4);
        CHECK(rec.calls()[0].kind == OpKind::Constant && rec.calls()[0].id == 0);
        CHECK(rec.calls()[1].kind == OpKind::MatMul && rec.calls()[1].id == 1);
        CHECK(rec.calls()[2].kind == OpKind::Add && rec.calls()[2].id == 2);
        CHECK(rec.calls()[3].kind == OpKind::Relu && rec.calls()[3].id == 3);
        CHECK(rec.count_of(OpKind::Constant) == 1);
        CHECK(rec.count_of(OpKind::MatMul) == 1);
        CHECK(rec.count_of(OpKind::Add) == 1);
        CHECK(rec.count_of(OpKind::Relu) == 1);

        // 同一个图、第二个访问者：分发序列必须相同。
        RecordingVisitor rec2;
        run_visitor(ex.graph, rec2);
        CHECK(rec2.calls().size() == rec.calls().size());
        CHECK(rec2.calls()[3].id == rec.calls()[3].id);
    }

    // ---------- 第 2 组：空图与只有输入的图 ----------
    {
        Graph empty("empty");
        RecordingVisitor rec;
        run_visitor(empty, rec);
        CHECK(rec.calls().empty());

        Graph only_input("only-input");
        Value* x = only_input.add_input("x", {Dtype::F32, {2, 2}});
        only_input.mark_output(x);
        run_visitor(only_input, rec);
        CHECK(rec.calls().empty());
        CHECK(only_input.to_string() ==
              "graph \"only-input\" (1 inputs, 1 outputs) {\n"
              "  %x = input : f32<2x2>\n"
              "  output %x\n"
              "}");
    }

    // ---------- 第 3 组：重构安全性——to_string 与 v3 一字不差 ----------
    {
        Example ex;
        const std::string text = ex.graph.to_string();
        CHECK(text ==
              "graph \"matmul-bias-relu\" (2 inputs, 1 outputs) {\n"
              "  %A = input : f32<2x3>\n"
              "  %B = input : f32<3x2>\n"
              "  %n0 = constant() {data = [0, -100, -150, -50]} -> %bias : f32<2x2>\n"
              "  %n1 = matmul(%A, %B) -> %C : f32<2x2>\n"
              "  %n2 = add(%C, %bias) -> %D : f32<2x2>\n"
              "  %n3 = relu(%D) -> %Y : f32<2x2>\n"
              "  output %Y\n"
              "}");
    }

    // ---------- 第 4 组：带 transpose 属性的打印（visitor 版）----------
    {
        Graph g("transposed");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_matmul(a, b, "C", /*transpose_a=*/true, /*transpose_b=*/true);
        g.mark_output(mm->result());
        CHECK(g.to_string() ==
              "graph \"transposed\" (2 inputs, 1 outputs) {\n"
              "  %A = input : f32<2x3>\n"
              "  %B = input : f32<3x2>\n"
              "  %n0 = matmul(%A, %B) {transpose_a, transpose_b} -> %C : f32<3x3>\n"
              "  output %C\n"
              "}");
    }

    // ---------- 第 5 组：改图之后（replace + erase）打印仍正确 ----------
    {
        Graph g("duplicate-matmul");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm1 = g.add_matmul(a, b, "C1");
        Node* mm2 = g.add_matmul(a, b, "C2");
        Node* add = g.add_elementwise(OpKind::Add, mm1->result(), mm2->result(), "D");
        g.mark_output(add->result());

        g.replace_all_uses_of(mm2->result(), mm1->result());
        g.erase_node(mm2);

        const std::string text = g.to_string();
        CHECK(text ==
              "graph \"duplicate-matmul\" (2 inputs, 1 outputs) {\n"
              "  %A = input : f32<2x3>\n"
              "  %B = input : f32<3x2>\n"
              "  %n0 = matmul(%A, %B) -> %C1 : f32<2x2>\n"
              "  %n2 = add(%C1, %C1) -> %D : f32<2x2>\n"
              "  output %D\n"
              "}");

        // 访问者看到的也是删除后的图：只剩 2 个节点。
        RecordingVisitor rec;
        run_visitor(g, rec);
        CHECK(rec.calls().size() == 2);
        CHECK(rec.calls()[0].kind == OpKind::MatMul);
        CHECK(rec.calls()[1].kind == OpKind::Add);
    }

    // ---------- 第 6 组：OpCardPrinter 的名片 ----------
    {
        Example ex;
        std::string cards;
        OpCardPrinter printer(cards);
        run_visitor(ex.graph, printer);

        // 4 行名片，按创建顺序。
        std::size_t lines = 0;
        for (char c : cards) {
            if (c == '\n') {
                ++lines;
            }
        }
        CHECK(lines == 4);
        CHECK(cards.find("[constant%n0] 常量：0 个输入，值写在属性里；data[4 个元素]") !=
              std::string::npos);
        CHECK(cards.find("[matmul%n1] 矩阵乘：2 个输入（%A × %B）") != std::string::npos);
        CHECK(cards.find("[add%n2] 逐元素加：2 个同形输入（%C + %bias）") != std::string::npos);
        CHECK(cards.find("[relu%n3] 取正：1 个输入（%D），逐元素 max(0, x)") != std::string::npos);
        CHECK(cards.find("→ 结果 %Y : f32<2x2>") != std::string::npos);
        CHECK(cards.find("→ 结果 %bias : f32<2x2>") != std::string::npos);
    }

    // ---------- 第 7 组：只读性——访问者跑完，图毫发无损 ----------
    {
        Example ex;
        const std::string before = ex.graph.to_string();

        RecordingVisitor rec;
        std::string cards;
        OpCardPrinter printer(cards);
        CounterVisitor counter;
        run_visitor(ex.graph, rec);
        run_visitor(ex.graph, printer);
        run_visitor(ex.graph, counter);

        CHECK(ex.graph.to_string() == before);      // IR 一字不差
        CHECK(use_def_consistent(ex.graph));        // 账本不变量成立
        CHECK(ex.graph.num_nodes() == 4);           // 节点数没变
        CHECK(ex.graph.num_values() == 6);          // 值数没变
        CHECK(counter.constant_ == 1 && counter.matmul_ == 1);
        CHECK(counter.add_ == 1 && counter.relu_ == 1);

        // 解释器数字与第 10 天一致：58 0 / 0 104。
        Interpreter interp;
        interp.bind(ex.a, {1, 2, 3, 4, 5, 6});
        interp.bind(ex.b, {7, 8, 9, 10, 11, 12});
        interp.run(ex.graph);
        const std::vector<double>& y = interp.of(ex.relu->result());
        CHECK(y.size() == 4);
        CHECK(y[0] == 58 && y[1] == 0 && y[2] == 0 && y[3] == 104);
    }

    // ---------- 第 8 组：混合图上的计数与手写 switch 对照 ----------
    {
        Graph g("mixed");
        const Value* v = g.add_input("x", {Dtype::F32, {2, 2}});
        for (int i = 0; i < 7; ++i) {
            const std::string tag = std::to_string(i);
            Node* w = g.add_constant("w" + tag, {Dtype::F32, {2, 2}}, {1, 0, 0, 1});
            Node* m = g.add_matmul(v, w->result(), "m" + tag);
            Node* b = g.add_constant("b" + tag, {Dtype::F32, {2, 2}}, {1, 2, 3, 4});
            Node* a = g.add_elementwise(OpKind::Add, m->result(), b->result(), "a" + tag);
            Node* r = g.add_relu(a->result(), "r" + tag);
            v = r->result();
        }
        g.mark_output(v);

        CounterVisitor counter;
        run_visitor(g, counter);
        CHECK(counter.constant_ == 14);
        CHECK(counter.matmul_ == 7);
        CHECK(counter.add_ == 7);
        CHECK(counter.relu_ == 7);

        // 手写 switch 的对照组：数出同样的结果。
        std::int64_t sw_c = 0, sw_m = 0, sw_a = 0, sw_r = 0, sw_u = 0;
        for (const std::unique_ptr<Node>& n : g.nodes()) {
            switch (n->kind()) {
                case OpKind::Constant: ++sw_c; break;
                case OpKind::MatMul:   ++sw_m; break;
                case OpKind::Add:      ++sw_a; break;
                case OpKind::Relu:     ++sw_r; break;
                case OpKind::Mul:      ++sw_u; break;
            }
        }
        CHECK(sw_c == counter.constant_ && sw_m == counter.matmul_);
        CHECK(sw_a == counter.add_ && sw_r == counter.relu_);
        CHECK(sw_u == counter.mul_);
    }

    // ---------- 第 9 组：图移动之后，visitor 依然可用 ----------
    {
        Example ex;
        Graph moved = std::move(ex.graph);
        RecordingVisitor rec;
        run_visitor(moved, rec);
        CHECK(rec.calls().size() == 4);
        CHECK(rec.calls()[0].kind == OpKind::Constant);
        CHECK(moved.to_string().find("%n3 = relu(%D) -> %Y") != std::string::npos);
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
