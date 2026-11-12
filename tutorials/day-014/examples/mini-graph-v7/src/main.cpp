#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include "Frontend.h"
#include "Graph.h"
#include "Interpreter.h"
#include "Model.h"
#include "Node.h"
#include "NodeVisitor.h"
#include "OpCardPrinter.h"
#include "Value.h"
#include "Verifier.h"

namespace {

// 把一串 double 按二维 shape 打成矩阵的样子（同第 9～13 天）。
void print_matrix(const char* name, const TensorType& type, const std::vector<double>& data) {
    std::printf("  %%%s (%s) =\n", name, type.to_string().c_str());
    for (std::int64_t i = 0; i < type.shape[0]; ++i) {
        std::printf("   ");
        for (std::int64_t j = 0; j < type.shape[1]; ++j) {
            std::printf(" %g", data[static_cast<std::size_t>(i * type.shape[1] + j)]);
        }
        std::printf("\n");
    }
}

// 打印一份验证报告：通过一行带统计，失败逐条列出（同第 12～13 天）。
void print_report(const Graph& g, const VerifyReport& rep) {
    if (rep.ok) {
        std::printf("verify: PASS（%lld 个节点、%lld 个值、%lld 个输出，全部检查通过）\n",
                    static_cast<long long>(g.num_nodes()),
                    static_cast<long long>(g.num_values()),
                    static_cast<long long>(g.outputs().size()));
    } else {
        std::printf("verify: FAIL，共 %zu 个问题：\n", rep.errors.size());
        for (const std::string& e : rep.errors) {
            std::printf("  error: %s\n", e.c_str());
        }
    }
}

// 第 14 天的主角模型：在整周经典链条上再接一层 Mul。
// Y = relu(A × B + bias) ⊙ mask。
// A: f32<2x3>，B: f32<3x2>，bias/mask: f32<2x2>；
// mask = [1, 0, 0, 2]：放行左上、清零右上、翻倍右下。
// 手算：C = 58 64/139 154 → D = 58 -36/-11 104 → R = 58 0/0 104
//      → Y = R ⊙ mask = 58 0/0 208。
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

// 拓扑打印：执行时间表（同第 13 天）。
void print_schedule(const Graph& g) {
    const std::vector<const Node*> order = g.topological_order();

    std::printf("  执行顺序：");
    for (const Node* n : order) {
        std::printf(" %s%%n%lld", op_name(n->kind()).c_str(), static_cast<long long>(n->id()));
    }
    std::printf("\n");

    for (std::size_t step = 0; step < order.size(); ++step) {
        const Node* n = order[step];
        std::printf("  step %zu: %s%%n%lld reads [", step + 1, op_name(n->kind()).c_str(),
                    static_cast<long long>(n->id()));
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            if (i != 0) {
                std::printf(", ");
            }
            std::printf("%%%s", n->input(i)->name().c_str());
        }
        std::printf("] writes %%%s\n", n->result()->name().c_str());
    }

    bool same = order.size() == static_cast<std::size_t>(g.num_nodes());
    for (std::size_t i = 0; same && i < order.size(); ++i) {
        same = order[i] == g.nodes()[i].get();
    }
    std::printf("  （与创建顺序%s——第 8 天的定理：只能引用已存在的值 ⇒ 创建序即拓扑序）\n",
                same ? "一致" : "不一致？！不该发生");
}

// 第二幕的小工具：构造注定失败的模型，打印 lower 抛出的错误。
void try_lower(const char* title, Model m) {
    std::printf("%s\n", title);
    try {
        Graph g = lower_model_to_graph(m);
        std::printf("  竟然成功了？不该走到这里（图：%s）\n", g.name().c_str());
    } catch (const std::invalid_argument& e) {
        std::printf("  what(): %s\n", e.what());
    }
}

}  // namespace

int main() {
    // ================= 第一幕：新算子 Mul 走完整流水线 =================
    // 一行枚举（OpKind::Mul）＋五个访问者＋一处执行语义＋一处分发——
    // 第 5 节的账单兑现之后，新算子自动获得整周的全部设施：
    // 工厂守卫、Verifier、文本 IR、拓扑打印、use-def 账本、解释器。
    Model m = masked_model();

    std::printf("== 第一幕：模型侧（写下来的计算） ==\n%s\n", model_to_string(m).c_str());

    Graph g = lower_model_to_graph(m);

    std::printf("== lower 之后：文本形式 IR（Graph::to_string） ==\n%s\n", g.to_string().c_str());

    std::printf("== 合法性检查（Verifier 的 visit_mul 上岗） ==\n");
    print_report(g, verify_graph(g));

    std::printf("\n== 拓扑打印（执行时间表） ==\n");
    print_schedule(g);

    std::printf("\n== Use-Def 检查（第 10 天的账本） ==\n%s\n", g.uses_to_string().c_str());

    // 端到端：A = 1 2 3 / 4 5 6，B = 7 8 / 9 10 / 11 12。
    //   C = 58 64/139 154 → D = 58 -36/-11 104 → R = 58 0/0 104
    //   → Y = R ⊙ mask = 58 0/0 208。
    std::printf("== 端到端执行（解释器按拓扑序求值） ==\n");
    Interpreter interp;
    interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});
    interp.bind(g.inputs()[1], {7, 8, 9, 10, 11, 12});
    interp.run(g);
    print_matrix("Y", g.outputs()[0]->type(), interp.of(g.outputs()[0]));

    // ================= 第二幕：每个访问者的名片（含新算子） =================
    // OpCardPrinter 是第 11 天「对扩展开放、对修改关闭」的直观体验：
    // 今天它被编译器点名必须表态，表态的代价是一行 card(...)。
    std::printf("== 第二幕：算子名片（OpCardPrinter） ==\n");
    std::string cards;
    OpCardPrinter printer(cards);
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        apply_visitor(printer, *n);
    }
    std::printf("%s", cards.c_str());

    // ================= 第三幕：写错算子名的现场 =================
    // 模型世界的算子名是字符串：拼错要在前端分发处被拦下，
    // 合法清单里已经能看到 Mul——它是今天刚搬进来的住户。
    std::printf("\n== 第三幕：写错算子名的现场（构造失败） ==\n");

    Model m1 = masked_model();
    m1.layers[3].op = "Mull";  // 手滑多打了一个 l
    try_lower("现场一（算子名拼错，Mull 不是合法算子）：", std::move(m1));

    Model m2 = masked_model();
    m2.layers[3].inputs = {"R"};  // Mul 要两个输入
    try_lower("现场二（Mul 只给了 1 个输入）：", std::move(m2));

    return 0;
}
