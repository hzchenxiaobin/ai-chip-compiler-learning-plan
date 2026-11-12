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
#include "Value.h"
#include "Verifier.h"

namespace {

// 把一串 double 按二维 shape 打成矩阵的样子（同第 9～12 天）。
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

// 打印一份验证报告：通过一行带统计，失败逐条列出（同第 12 天）。
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

// 本周的目标模型：Y = relu(A × B + bias)。
// A: f32<2x3>，B: f32<3x2>，bias: f32<2x2>——第 9 天起的经典形状。
Model target_model() {
    Model m;
    m.name = "matmul-bias-relu";
    m.inputs = {{"A", {Dtype::F32, {2, 3}}}, {"B", {Dtype::F32, {3, 2}}}};
    m.weights = {{"bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0}}};
    m.layers = {
        {"MatMul", {"A", "B"}, "C"},
        {"Add", {"C", "bias"}, "D"},
        {"Relu", {"D"}, "Y"},
    };
    m.outputs = {"Y"};
    return m;
}

// 拓扑打印：执行时间表——第 k 步执行哪个节点、读哪些值、写哪个值。
// 解释器（以及将来的 Lowering 代码生成）走的就是这个顺序。
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

    // 定理（第 8 天）：本 API 只能引用已存在的值，所以创建顺序必是拓扑序。
    // 文本 IR 的节点行因此天然按可执行顺序排列——今天用肉眼对照一次。
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
    // ================= 第一幕：一张模型，一条流水线 =================
    // 学习计划的第 13 天目标图：MatMul → Add → Relu。
    // 模型 → 图 IR（映射）→ 文本 IR（拓扑打印）→ 验证 → use-def 检查 → 执行。
    Model m = target_model();

    std::printf("== 第一幕：模型侧（写下来的计算） ==\n%s\n", model_to_string(m).c_str());

    Graph g = lower_model_to_graph(m);

    std::printf("== lower 之后：文本形式 IR（Graph::to_string） ==\n%s\n", g.to_string().c_str());

    std::printf("== 合法性检查（第 12 天的 Verifier 上岗） ==\n");
    print_report(g, verify_graph(g));

    std::printf("\n== 拓扑打印（执行时间表） ==\n");
    print_schedule(g);

    std::printf("\n== Use-Def 检查（第 10 天的账本） ==\n%s\n", g.uses_to_string().c_str());

    // 端到端的最后一公里：解释器按拓扑序把图算一遍。
    // A = 1 2 3 / 4 5 6，B = 7 8 / 9 10 / 11 12：
    //   C = A×B = 58 64 / 139 154；D = C + bias = 58 -36 / -11 104；
    //   Y = relu(D) = 58 0 / 0 104。
    std::printf("== 端到端执行（解释器按拓扑序求值） ==\n");
    Interpreter interp;
    interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});
    interp.bind(g.inputs()[1], {7, 8, 9, 10, 11, 12});
    interp.run(g);
    print_matrix("Y", g.outputs()[0]->type(), interp.of(g.outputs()[0]));

    // ================= 第二幕：写错模型的三个现场 =================
    // 模型世界的数据（字符串名字）不受编译器保护；映射是第一道关卡。
    // 三个错误全部是「构造失败」：当场抛、消息带层号/槽位/名字。
    std::printf("\n== 第二幕：写错模型的三个现场（全部构造失败） ==\n");

    // 现场一：手工编辑后层序乱了——relu 排在 add 前面（前向引用）。
    Model m1 = target_model();
    m1.layers = {
        {"Relu", {"D"}, "Y"},
        {"Add", {"C", "bias"}, "D"},
        {"MatMul", {"A", "B"}, "C"},
    };
    try_lower("现场一（层序不是拓扑序，先用了还没生产的 D）：", std::move(m1));

    // 现场二：名字拼错——"bias" 写成了 "biasx"。
    Model m2 = target_model();
    m2.layers[1].inputs[1] = "biasx";
    try_lower("现场二（名字拼错，整个模型里没有 biasx）：", std::move(m2));

    // 现场三：两个层都写 "C"——名字身份模糊。
    Model m3 = target_model();
    m3.layers[2].output = "C";
    try_lower("现场三（relu 的输出也叫 C，名字撞车）：", std::move(m3));

    return 0;
}
