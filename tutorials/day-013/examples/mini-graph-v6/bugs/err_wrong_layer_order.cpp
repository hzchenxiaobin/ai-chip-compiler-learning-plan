// 反面教材（第 13 天）：三种「名字用错」的模型，三种诊断怎么读。
// 模型世界的数据（字符串名字）不受编译器保护——手滑、拼错、编辑后
// 层序乱了，都要到映射（lower_model_to_graph）这一刻才被抓。
// 三种错误，三种消息，都带「第几层 / 第几个槽 / 哪个名字」：
//   现场一：手工编辑模型后层序乱了（前向引用）→ 「还没有生产者——
//           层的顺序必须是拓扑序」；
//   现场二：名字拼错 → 「在整个模型里都不存在」；
//   现场三：一层的输入是它自己的输出 → 「名字成环」。第 16 天会在
//           可变图上正式做环检测；今天名字世界的环在构造期就死了。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Graph.cpp ../src/Interpreter.cpp ../src/Verifier.cpp ../src/Frontend.cpp \
//     err_wrong_layer_order.cpp -o err_wrong_layer_order && ./err_wrong_layer_order
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include "Frontend.h"
#include "Graph.h"
#include "Model.h"
#include "Node.h"
#include "Value.h"

namespace {

void show(const char* title, Model m, const char* fix) {
    std::printf("%s\n", title);
    try {
        Graph g = lower_model_to_graph(m);
        (void)g;
        std::printf("  竟然成功了？不该走到这里\n");
    } catch (const std::invalid_argument& e) {
        std::printf("  what(): %s\n", e.what());
    }
    std::printf("  → 修复方向：%s\n\n", fix);
}

}  // namespace

int main() {
    // 现场一：编辑模型时把层挪乱了——relu 排到了 add 前面。
    {
        Model m;
        m.name = "edited-by-hand";
        m.inputs = {{"A", {Dtype::F32, {2, 3}}}, {"B", {Dtype::F32, {3, 2}}}};
        m.weights = {{"bias", {Dtype::F32, {2, 2}}, {0, -1, -2, -3}}};
        m.layers = {
            {"Relu", {"D"}, "Y"},
            {"Add", {"C", "bias"}, "D"},
            {"MatMul", {"A", "B"}, "C"},
        };
        m.outputs = {"Y"};
        show("现场一（层序不是拓扑序，先用了还没生产的 D）：", std::move(m),
             "把层排回拓扑序（定义先于使用），消息里写明了它在哪里才定义");
    }

    // 现场二：bias 拼成了 biasx。
    {
        Model m;
        m.name = "typo";
        m.inputs = {{"A", {Dtype::F32, {2, 3}}}, {"B", {Dtype::F32, {3, 2}}}};
        m.weights = {{"bias", {Dtype::F32, {2, 2}}, {0, -1, -2, -3}}};
        m.layers = {
            {"MatMul", {"A", "B"}, "C"},
            {"Add", {"C", "biasx"}, "D"},
            {"Relu", {"D"}, "Y"},
        };
        m.outputs = {"Y"};
        show("现场二（名字拼错，整个模型里没有 biasx）：", std::move(m),
             "改正拼写：biasx → bias（消息里写明是第几层第几个输入）");
    }

    // 现场三：自环——一层的输入是它自己的输出。
    {
        Model m;
        m.name = "self-loop";
        m.inputs = {{"A", {Dtype::F32, {2, 2}}}};
        m.layers = {{"Relu", {"R"}, "R"}, {"Add", {"A", "R"}, "S"}};
        m.outputs = {"S"};
        show("现场三（relu 的输入是它自己的输出 R）：", std::move(m),
             "给这层的输出换个名字，或重新设计依赖（值要先产生才能被用）");
    }
    return 0;
}
