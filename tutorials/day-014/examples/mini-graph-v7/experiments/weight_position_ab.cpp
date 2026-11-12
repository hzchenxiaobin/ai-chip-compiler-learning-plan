// 第 13 天对照实验：同一个模型，权重放两种位置。
//   变体 A：bias 进 weights（initializer）→ lower 成 Constant 节点；
//   变体 B：bias 进 inputs（图输入）  → 运行期由解释器 bind 提供。
// 三个观察点：
//   1) IR 的差别只有一行（%bias 的来历）与一行（bind 的责任方）；
//   2) verify 双双 PASS——两种放法都是合法图，语义数字完全相同；
//   3) 合同不同：A 的 bias 数据编译期就在图里（将来可参与常量折叠，
//      第 24/47 天），B 的 bias 运行期才存在，编译器永远拿不到它的值。
// ONNX 的历史注脚：IR v4 之前 initializer 被要求同时出现在 inputs 里
//（很多旧模型仍然这样），现代约定把两者分开——正是 A/B 的分界线。
// 编译运行（在 experiments/ 目录下）：
//   g++ -std=c++17 -g -I ../src ../src/Graph.cpp ../src/Interpreter.cpp \
//     ../src/Verifier.cpp ../src/Frontend.cpp weight_position_ab.cpp -o weight_position_ab
#include <cstdio>
#include <vector>

#include "Frontend.h"
#include "Graph.h"
#include "Interpreter.h"
#include "Model.h"
#include "Node.h"
#include "Value.h"
#include "Verifier.h"

namespace {

void run_variant(const char* title, Model m, bool bind_bias) {
    std::printf("== %s ==\n", title);
    std::printf("%s\n", model_to_string(m).c_str());
    Graph g = lower_model_to_graph(m);
    std::printf("%s\n", g.to_string().c_str());
    const VerifyReport rep = verify_graph(g);
    std::printf("verify: %s\n\n", rep.ok ? "PASS" : "FAIL");

    Interpreter interp;
    interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});  // A
    interp.bind(g.inputs()[1], {7, 8, 9, 10, 11, 12});  // B
    if (bind_bias) {
        interp.bind(g.inputs()[2], {0, -100, -150, -50});  // bias 在变体 B 是图输入
    }
    interp.run(g);
    const std::vector<double>& y = interp.of(g.outputs()[0]);
    std::printf("Y =\n %g %g\n %g %g\n\n", y[0], y[1], y[2], y[3]);
}

}  // namespace

int main() {
    // 变体 A：bias 是权重（今天的主线做法）。
    Model a;
    a.name = "A-bias-as-weight";
    a.inputs = {{"A", {Dtype::F32, {2, 3}}}, {"B", {Dtype::F32, {3, 2}}}};
    a.weights = {{"bias", {Dtype::F32, {2, 2}}, {0, -100, -150, -50}}};
    a.layers = {
        {"MatMul", {"A", "B"}, "C"},
        {"Add", {"C", "bias"}, "D"},
        {"Relu", {"D"}, "Y"},
    };
    a.outputs = {"Y"};
    run_variant("变体 A：bias 放 weights → Constant 节点（编译期数据）", std::move(a),
                /*bind_bias=*/false);

    // 变体 B：bias 是图输入（运行期数据）。只改一个参数：bias 挪个家。
    Model b;
    b.name = "B-bias-as-input";
    b.inputs = {{"A", {Dtype::F32, {2, 3}}},
                {"B", {Dtype::F32, {3, 2}}},
                {"bias", {Dtype::F32, {2, 2}}}};
    b.layers = {
        {"MatMul", {"A", "B"}, "C"},
        {"Add", {"C", "bias"}, "D"},
        {"Relu", {"D"}, "Y"},
    };
    b.outputs = {"Y"};
    run_variant("变体 B：bias 放 inputs → 运行期 bind（只改一个参数）", std::move(b),
                /*bind_bias=*/true);

    std::printf("== 对照结论 ==\n");
    std::printf("1) 语义相同：两份 Y 都是 58 0 / 0 104；verify 都 PASS。\n");
    std::printf("2) IR 不同一行：A 的 %%bias 来自 constant 节点，B 的 %%bias 是 input。\n");
    std::printf("3) 合同不同：A 的 bias 编译期就在图里（可参与常量折叠，第 24/47 天），\n");
    std::printf("   B 的 bias 运行期才存在，编译器永远看不到它的值。\n");
    return 0;
}
