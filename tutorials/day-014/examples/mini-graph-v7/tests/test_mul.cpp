// 第 14 天的验收测试：新增 Mul（逐元素乘）算子的全链路检查。
// 一条主线贯穿：OpKind 枚举 → 工厂守卫（复用 add_elementwise）→
// Verifier 语义（复用逐元素二元检查）→ 文本 IR 打印 → Visitor 分发 →
// 前端 "Mul" 字符串层 → 解释器数字。每一组都在回答同一个问题：
// 「新增一种算子，哪些设施自动获得它，哪些设施必须手工接上」。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "Frontend.h"
#include "Graph.h"
#include "Interpreter.h"
#include "Model.h"
#include "Node.h"
#include "NodeVisitor.h"
#include "OpCardPrinter.h"
#include "OpKind.h"
#include "Value.h"
#include "Verifier.h"

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

#define CHECK_THROW(expr, fragment)                                      \
    do {                                                                 \
        bool threw = false;                                              \
        try {                                                            \
            expr;                                                        \
        } catch (const std::invalid_argument& e) {                       \
            threw = true;                                                \
            CHECK(std::string(e.what()).find(fragment) !=                \
                  std::string::npos);                                    \
        }                                                                \
        CHECK(threw);                                                    \
    } while (0)

// 本周的经典链条再往上加一层：Y = relu(A×B + bias) ⊙ mask。
// A: f32<2x3>，B: f32<3x2>，bias/mask: f32<2x2>。
// mask = [1, 0, 0, 2]：左上角照常放行、右上角清零、右下角翻倍。
Model masked_model() {
    Model m;
    m.name = "matmul-bias-relu-mask";
    m.inputs = {{"A", {Dtype::F32, {2, 3}}}, {"B", {Dtype::F32, {3, 2}}}};
    m.weights = {
        {"bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0}},
        {"mask", {Dtype::F32, {2, 2}}, {1.0, 0.0, 0.0, 2.0}},
    };
    m.layers = {
        {"MatMul", {"A", "B"}, "C"},
        {"Add", {"C", "bias"}, "D"},
        {"Relu", {"D"}, "R"},
        {"Mul", {"R", "mask"}, "Y"},
    };
    m.outputs = {"Y"};
    return m;
}

// 记录分发序列的访问者（只记 kind + id，与 test_visitor 同思路的小份拷贝——
// 测试文件之间不共享辅助代码，各自独立可读）。
class KindRecorder : public NodeVisitor {
public:
    struct Call {
        OpKind kind;
        std::int64_t id;
    };

    void visit_constant(const Node& n) override { push(OpKind::Constant, n); }
    void visit_matmul(const Node& n) override { push(OpKind::MatMul, n); }
    void visit_add(const Node& n) override { push(OpKind::Add, n); }
    void visit_relu(const Node& n) override { push(OpKind::Relu, n); }
    void visit_mul(const Node& n) override { push(OpKind::Mul, n); }

    std::size_t count_of(OpKind k) const {
        std::size_t c = 0;
        for (const Call& call : calls_) {
            if (call.kind == k) {
                ++c;
            }
        }
        return c;
    }
    const std::vector<Call>& calls() const noexcept { return calls_; }

private:
    void push(OpKind k, const Node& n) { calls_.push_back({k, n.id()}); }
    std::vector<Call> calls_;
};

// 手算对照：A = 1..6，B = 7..12。
//   C = A×B = 58 64 / 139 154；D = C + bias = 58 -36 / -11 104；
//   R = relu(D) = 58 0 / 0 104；Y = R ⊙ mask = 58 0 / 0 208。
bool is_y(const std::vector<double>& y) {
    return y.size() == 4 && y[0] == 58 && y[1] == 0 && y[2] == 0 && y[3] == 208;
}

}  // namespace

int main() {
    // ---------- 第 1 组：枚举与名字（OpKind.h 的三处 switch 接上了）----------
    {
        CHECK(op_name(OpKind::Mul) == "mul");
        CHECK(is_valid_kind(OpKind::Mul));
        CHECK(!is_valid_kind(static_cast<OpKind>(5)));  // 野值仍然被拦
    }

    // ---------- 第 2 组：工厂——add_elementwise 直接收编 Mul ----------
    {
        Graph g("mul-basic");
        Value* x = g.add_input("X", {Dtype::F32, {2, 2}});
        Node* w = g.add_constant("W", {Dtype::F32, {2, 2}}, {1, 0, 0, 2});
        Node* m = g.add_elementwise(OpKind::Mul, x, w->result(), "M");
        g.mark_output(m->result());

        CHECK(m->kind() == OpKind::Mul);
        CHECK(m->num_inputs() == 2);
        CHECK(m->input(0) == x && m->input(1) == w->result());
        const TensorType want{Dtype::F32, {2, 2}};
        CHECK(m->result()->type() == want);
        CHECK(g.to_string().find("%n1 = mul(%X, %W) -> %M : f32<2x2>") !=
              std::string::npos);

        // 工厂守卫对 Mul 自动生效（第 9 天写的检查，零新增代码）：
        Value* other = g.add_input("O", {Dtype::F32, {2, 3}});
        CHECK_THROW(g.add_elementwise(OpKind::Mul, x, other, "M3"),
                    "mul: 类型必须完全一致");
        CHECK_THROW(g.add_elementwise(OpKind::Mul, x, nullptr, "M4"),
                    "mul: 输入是空指针");
        CHECK(g.num_nodes() == 2);  // 上面的失败没有留下半个节点

        // Verifier 对新算子的语义检查（NodeVerifier::visit_mul）：
        CHECK(verify_graph(g).ok);
    }

    // ---------- 第 3 组：Verifier 反例——raw 后门造非法 Mul ----------
    {
        Graph g("mul-raw");
        Value* a = g.add_input("a", {Dtype::F32, {2, 2}});
        Node* one = g.add_raw_node(OpKind::Mul, {a}, Attrs{}, {Dtype::F32, {2, 2}}, "r1");
        g.mark_output(one->result());
        const VerifyReport rep1 = verify_graph(g);
        CHECK(!rep1.ok);
        CHECK(rep1.errors.size() == 1);
        CHECK(rep1.errors[0].find("[mul%n0]: 需要 2 个输入，实际有 1 个") !=
              std::string::npos);
    }
    {
        Graph g("mul-raw2");
        Value* a = g.add_input("a", {Dtype::F32, {2, 2}});
        Value* b = g.add_input("b", {Dtype::F32, {2, 3}});
        Node* bad = g.add_raw_node(OpKind::Mul, {a, b}, Attrs{}, {Dtype::F32, {2, 2}},
                                    "r");
        g.mark_output(bad->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(rep.errors.size() == 1);
        CHECK(rep.errors[0].find("两个输入类型不一致") != std::string::npos);
        CHECK(rep.errors[0].find("f32<2x2> vs f32<2x3>") != std::string::npos);
    }
    {
        Graph g("mul-raw3");
        Value* a = g.add_input("a", {Dtype::F32, {2, 2}});
        Value* i32 = g.add_input("c", {Dtype::I32, {2, 2}});
        Node* mixed = g.add_raw_node(OpKind::Mul, {a, i32}, Attrs{}, {Dtype::F32, {2, 2}},
                                      "r");
        g.mark_output(mixed->result());
        CHECK(verify_graph(g).errors[0].find("两个输入类型不一致") != std::string::npos);
    }
    {
        Graph g("mul-raw4");
        Value* a = g.add_input("a", {Dtype::F32, {2, 2}});
        Node* wrong_result = g.add_raw_node(OpKind::Mul, {a, a}, Attrs{},
                                             {Dtype::F32, {2, 3}}, "r");
        g.mark_output(wrong_result->result());
        CHECK(verify_graph(g).errors[0].find(
                  "结果类型应与输入一致（f32<2x2>）") != std::string::npos);
    }
    {
        // 合法值清单里出现了 mul；野值 5（Mul 之后的第一格）被拦下。
        Graph g("mul-raw5");
        Value* a = g.add_input("a", {Dtype::F32, {2, 2}});
        Node* wild = g.add_raw_node(static_cast<OpKind>(5), {a}, Attrs{},
                                     {Dtype::F32, {2, 2}}, "r");
        g.mark_output(wild->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(rep.errors[0].find("未知的算子类型 5") != std::string::npos);
        CHECK(rep.errors[0].find("constant / matmul / add / relu / mul") !=
              std::string::npos);
    }

    // ---------- 第 4 组：解释器——Mul 的执行语义 ----------
    {
        Graph g("mul-interp");
        Value* x = g.add_input("X", {Dtype::F32, {2, 2}});
        Node* w = g.add_constant("W", {Dtype::F32, {2, 2}}, {1, 0, 0, 2});
        Node* m = g.add_elementwise(OpKind::Mul, x, w->result(), "M");
        g.mark_output(m->result());

        Interpreter interp;
        interp.bind(x, {1, 2, 3, 4});
        interp.run(g);
        const std::vector<double>& y = interp.of(m->result());
        CHECK(y.size() == 4 && y[0] == 1 && y[1] == 0 && y[2] == 0 && y[3] == 8);
    }
    {
        // 负数穿过 Mul：符号随乘积走（这把它和 relu 区分开）。
        Graph g("mul-negative");
        Value* x = g.add_input("X", {Dtype::F32, {1, 2}});
        Node* w = g.add_constant("W", {Dtype::F32, {1, 2}}, {3, -4});
        Node* m = g.add_elementwise(OpKind::Mul, x, w->result(), "M");
        g.mark_output(m->result());

        Interpreter interp;
        interp.bind(x, {-1, 2});
        interp.run(g);
        const std::vector<double>& y = interp.of(m->result());
        CHECK(y[0] == -3 && y[1] == -8);
    }

    // ---------- 第 5 组：前端——字符串 "Mul" 层走进整条流水线 ----------
    {
        Model m = masked_model();
        const Graph g = lower_model_to_graph(m);

        // 2 个 Constant（bias、mask）＋ matmul/add/relu/mul 四层 = 6 节点；
        // 值：2 输入 + 2 常量 + C/D/R/Y = 8。
        CHECK(g.num_nodes() == 6);
        CHECK(g.num_values() == 8);
        CHECK(g.inputs().size() == 2);
        CHECK(g.outputs().size() == 1);

        const std::string text = g.to_string();
        CHECK(text.find("%n1 = constant() {data = [1, 0, 0, 2]} -> %mask : f32<2x2>") !=
              std::string::npos);
        CHECK(text.find("%n5 = mul(%R, %mask) -> %Y : f32<2x2>") != std::string::npos);
        CHECK(text.find("mul(%C") == std::string::npos);  // mul 只吃 R 和 mask

        // Verifier：六节点整图全绿。
        const VerifyReport rep = verify_graph(g);
        CHECK(rep.ok);

        // use-def 账本：%R 和 %mask 各有一条 mul 使用记录（槽位 0/1）。
        const Node* mul_node = g.nodes()[5].get();
        CHECK(mul_node->kind() == OpKind::Mul);
        CHECK(mul_node->result()->name() == "Y");
        CHECK(mul_node->result()->num_uses() == 0);  // 图输出，账本无记录
        CHECK(mul_node->input(0)->users().size() == 1);
        CHECK(mul_node->input(0)->users()[0].user == mul_node);
        CHECK(mul_node->input(0)->users()[0].operand == 0);
        CHECK(mul_node->input(1)->users().size() == 1);
        CHECK(mul_node->input(1)->users()[0].user == mul_node);
        CHECK(mul_node->input(1)->users()[0].operand == 1);

        // 解释器数字与手算一致：58 0 / 0 208。
        Interpreter interp;
        interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});
        interp.bind(g.inputs()[1], {7, 8, 9, 10, 11, 12});
        interp.run(g);
        CHECK(is_y(interp.of(g.outputs()[0])));

        // 拓扑序仍是创建序（第 8 天定理对新算子照样成立）。
        const std::vector<const Node*> order = g.topological_order();
        CHECK(order.size() == 6);
        CHECK(order.back() == mul_node);
        CHECK(order.back()->kind() == OpKind::Mul);
    }

    // ---------- 第 6 组：Visitor——三种访问者都认得 Mul 了 ----------
    {
        const Graph g = lower_model_to_graph(masked_model());

        KindRecorder rec;
        for (const std::unique_ptr<Node>& n : g.nodes()) {
            apply_visitor(rec, *n);
        }
        CHECK(rec.calls().size() == 6);
        CHECK(rec.count_of(OpKind::Mul) == 1);
        CHECK(rec.calls().back().kind == OpKind::Mul);
        CHECK(rec.calls().back().id == 5);

        // 名片打印：新算子的名片随 visit_mul 到位。
        std::string cards;
        OpCardPrinter printer(cards);
        for (const std::unique_ptr<Node>& n : g.nodes()) {
            apply_visitor(printer, *n);
        }
        CHECK(cards.find("[mul%n5] 逐元素乘：2 个同形输入（%R × %mask）") !=
              std::string::npos);
        CHECK(cards.find("→ 结果 %Y : f32<2x2>") != std::string::npos);

        // 只读性：两个访问者跑完，图一字不差。
        const std::string before = g.to_string();
        CHECK(g.to_string() == before);
        CHECK(verify_graph(g).ok);
    }

    // ---------- 第 7 组：改图——账本与改图入口对 Mul 同样生效 ----------
    {
        Graph g = lower_model_to_graph(masked_model());
        Node* mask = nullptr;
        for (const std::unique_ptr<Node>& n : g.nodes()) {
            if (n->kind() == OpKind::Constant && n->result()->name() == "mask") {
                mask = n.get();
            }
        }
        CHECK(mask != nullptr);

        // 换一个全 1 掩码：replace + erase（第 10 天的入口，与新算子无关地生效）。
        Node* ones = g.add_constant("mask2", {Dtype::F32, {2, 2}}, {1, 1, 1, 1});
        g.replace_all_uses_of(mask->result(), ones->result());
        g.erase_node(mask);

        CHECK(g.num_nodes() == 6);  // 7 - 1：mask 走了，mask2 来了
        CHECK(verify_graph(g).ok);
        CHECK(g.to_string().find("%n5 = mul(%R, %mask2) -> %Y : f32<2x2>") !=
              std::string::npos);
        CHECK(ones->result()->users().size() == 1);
        CHECK(ones->result()->users()[0].operand == 1);

        // 全 1 掩码之下 Y 退回 relu 的结果：58 0 / 0 104。
        Interpreter interp;
        interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});
        interp.bind(g.inputs()[1], {7, 8, 9, 10, 11, 12});
        interp.run(g);
        const std::vector<double>& y = interp.of(g.outputs()[0]);
        CHECK(y.size() == 4 && y[0] == 58 && y[1] == 0 && y[2] == 0 && y[3] == 104);
    }

    // ---------- 第 8 组：前端的算子名纪律对 Mul 同样生效 ----------
    {
        Model m = masked_model();
        m.layers[3].op = "Mull";  // 拼错
        CHECK_THROW(lower_model_to_graph(m), "不认识");
        CHECK_THROW(lower_model_to_graph(m), "MatMul / Add / Mul / Relu");

        Model m2 = masked_model();
        m2.layers[3].inputs = {"R"};  // 只给 1 个输入
        CHECK_THROW(lower_model_to_graph(m2), "需要 2 个输入，实际 1 个");

        Model m3 = masked_model();
        m3.layers[3].transpose_a = true;  // Mul 没有 transpose 属性
        CHECK_THROW(lower_model_to_graph(m3), "没有这个属性");
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
