// 第 14 天的对照实验：同一个 mask，插在不同的位置。
//
// 变体 A（mask 在最后）：Y_A = relu(A×B + bias) ⊙ mask
//   C = 58 64/139 154 → D = 58 -36/-11 104 → R = 58 0/0 104
//   → Y_A = 58 0/0 208
// 变体 B（mask 在最前）：Y_B = relu((A×B ⊙ mask) + bias)
//   C = 58 64/139 154 → M = 58 0/0 308 → D' = 58 -100/-150 258
//   → Y_B = 58 0/0 258
//
// 两个模型只差「Mul 层插在哪一行」，数字却完全不同——
// Mul 是有真实语义的算子，不是图上的装饰；位置就是语义。
// 编译：见同目录 mask-position.sh（脚本会保存两份 IR 的 diff 到日志）。

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

Model base_model(const char* name) {
    Model m;
    m.name = name;
    m.inputs = {{"A", {Dtype::F32, {2, 3}}}, {"B", {Dtype::F32, {3, 2}}}};
    m.weights = {
        {"bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0}},
        {"mask", {Dtype::F32, {2, 2}}, {1.0, 0.0, 0.0, 2.0}},
    };
    m.outputs = {"Y"};
    return m;
}

void print_report(const Graph& g, const VerifyReport& rep) {
    if (rep.ok) {
        std::printf("verify: PASS（%lld 个节点、%lld 个值）\n",
                    static_cast<long long>(g.num_nodes()),
                    static_cast<long long>(g.num_values()));
    } else {
        std::printf("verify: FAIL，共 %zu 个问题\n", rep.errors.size());
    }
}

void run_and_print(const char* title, Model m) {
    std::printf("== %s ==\n", title);
    try {
        const Graph g = lower_model_to_graph(m);
        std::printf("%s\n", g.to_string().c_str());
        print_report(g, verify_graph(g));
        Interpreter interp;
        interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});
        interp.bind(g.inputs()[1], {7, 8, 9, 10, 11, 12});
        interp.run(g);
        const std::vector<double>& y = interp.of(g.outputs()[0]);
        std::printf("Y =\n  %g %g\n  %g %g\n\n", y[0], y[1], y[2], y[3]);
    } catch (const std::invalid_argument& e) {
        std::printf("lower 失败：%s\n\n", e.what());
    }
}

}  // namespace

int main() {
    // 变体 A：Mul 垫底——先算完 bias 和 relu，最后套 mask。
    Model a = base_model("A-mask-last");
    a.layers = {
        {"MatMul", {"A", "B"}, "C"},
        {"Add", {"C", "bias"}, "D"},
        {"Relu", {"D"}, "R"},
        {"Mul", {"R", "mask"}, "Y"},
    };
    run_and_print("变体 A：Y = relu(A×B + bias) ⊙ mask（Mul 在最后）", std::move(a));

    // 变体 B：Mul 打头阵——先给乘积套 mask，再加 bias、过 relu。
    Model b = base_model("B-mask-first");
    b.layers = {
        {"MatMul", {"A", "B"}, "C"},
        {"Mul", {"C", "mask"}, "M"},
        {"Add", {"M", "bias"}, "D"},
        {"Relu", {"D"}, "Y"},
    };
    run_and_print("变体 B：Y = relu((A×B ⊙ mask) + bias)（Mul 在最前）", std::move(b));

    return 0;
}
