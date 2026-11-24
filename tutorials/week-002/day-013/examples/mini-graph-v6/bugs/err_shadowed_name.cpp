// 反面教材（第 13 天核心）：没有重名检查的前端，名字身份模糊的代价。
// 模型作者想写：Y = relu(X + X)（先加再 relu），但复制层模板时忘了改
// 输出名——第二层把输出也叫 "C"：
//   layer 1: Add(X, X) -> C
//   layer 2: Relu(X)   -> C   ← 手滑：本该叫别的名字
//   layer 3: Relu(C)   -> Y
// 下面的 lower_unchecked 是迷你版前端：只做名字→指针翻译，不查重名，
// 符号表条目直接覆盖（named[l.output] = ...）。于是：
//   1) 第 1 层算出的 %C 无人使用（静默死掉）；
//   2) 第 3 层的 "C" 译到了第 2 层的结果——图算的是 relu(relu(X))，
//      不是模型作者想要的 relu(X+X)；
//   3) 文本 IR 里出现两个 %C，从文本读回来的人无法知道该接哪个
//      （第 41 天的解析器会在这里跪掉）；
//   4) verify_graph 照样 PASS——图在结构上完全合法，名字唯一性是
//      前端的合同，不是 Verifier 的检查项；
//   5) 解释器给出「像模像样」的错答案，退出码 0——静默错误，最难抓。
// 最后用真正的前端（带重名检查）lower 同一个模型：构造失败，当场点名。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Graph.cpp ../src/Interpreter.cpp ../src/Verifier.cpp ../src/Frontend.cpp \
//     err_shadowed_name.cpp -o err_shadowed_name && ./err_shadowed_name
#include <cstdio>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "Frontend.h"
#include "Graph.h"
#include "Interpreter.h"
#include "Model.h"
#include "Node.h"
#include "OpKind.h"
#include "Value.h"
#include "Verifier.h"

namespace {

Model shadowed_model() {
    Model m;
    m.name = "who-wrote-two-Cs";
    m.inputs = {{"X", {Dtype::F32, {2, 2}}}};
    m.layers = {
        {"Add", {"X", "X"}, "C"},
        {"Relu", {"X"}, "C"},  // ← 手滑：两个层都写 "C"
        {"Relu", {"C"}, "Y"},
    };
    m.outputs = {"Y"};
    return m;
}

// 迷你版前端（反面教材）：不做任何检查。名字直接覆盖符号表。
Graph lower_unchecked(const Model& m) {
    Graph g(m.name);
    std::unordered_map<std::string, const Value*> named;
    for (const ModelInput& in : m.inputs) {
        named[in.name] = g.add_input(in.name, in.type);
    }
    for (const ModelWeight& w : m.weights) {
        named[w.name] = g.add_constant(w.name, w.type, w.data)->result();
    }
    for (const ModelLayer& l : m.layers) {
        std::vector<const Value*> ins;
        for (const std::string& s : l.inputs) {
            ins.push_back(named.at(s));
        }
        Node* n = nullptr;
        if (l.op == "MatMul") {
            n = g.add_matmul(ins[0], ins[1], l.output);
        } else if (l.op == "Add") {
            n = g.add_elementwise(OpKind::Add, ins[0], ins[1], l.output);
        } else if (l.op == "Relu") {
            n = g.add_relu(ins[0], l.output);
        }
        named[l.output] = n->result();  // ← 重名？直接覆盖，旧定义被遮蔽
    }
    for (const std::string& out : m.outputs) {
        g.mark_output(named.at(out));
    }
    return g;
}

}  // namespace

int main() {
    // 崩溃演示专用：关掉 stdout 缓冲，保证输出顺序稳定。
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    const Model m = shadowed_model();
    std::printf("模型（作者本意：Y = relu(X + X)）：\n%s\n", model_to_string(m).c_str());

    Graph g = lower_unchecked(m);
    std::printf("== 无检查前端的产物：文本 IR（两个 %%C！） ==\n%s\n", g.to_string().c_str());
    std::printf("== use 表（第一个 %%C 静默死掉） ==\n%s\n", g.uses_to_string().c_str());
    std::printf("== verify_graph 的意见 ==\n");
    const VerifyReport rep = verify_graph(g);
    std::printf("%s\n", rep.ok ? "PASS（图结构合法——名字唯一不归它管）"
                               : "FAIL（不该走到这里）");

    Interpreter interp;
    interp.bind(g.inputs()[0], {1, -2, -3, 4});
    interp.run(g);
    const std::vector<double>& y = interp.of(g.outputs()[0]);
    std::printf("== 解释器结果 ==\n  relu(relu(X)) = %g %g / %g %g\n", y[0], y[1], y[2], y[3]);
    std::printf("  作者想要的 relu(X+X) = 2 0 / 0 8\n");
    std::printf("  全程零报错，退出码还是 0——静默的错答案。\n\n");

    std::printf("== 真正的前端（带重名检查）lower 同一个模型 ==\n");
    try {
        Graph g2 = lower_model_to_graph(m);
        (void)g2;
    } catch (const std::invalid_argument& e) {
        std::printf("  what(): %s\n", e.what());
    }
    return 0;
}
