// 反面教材（第 13 天）：lower 的返回值是一张全新的图——重新 lower
// 会整体换掉旧图，之前拿到的指针全部失效。
// 情节：第一次 lower 之后记下了输出值的指针 %Y，想「换个权重再跑一次」，
// 于是 g = lower_model_to_graph(m2)（移动赋值：旧图的 unique_ptr 名单
// 先析构、再接新名单——第 8 天的房产证换主人）。然后还想用旧指针……
// 现象（分构建）：
//   ASan 构建：heap-use-after-free READ of size 32，释放栈一路指到
//   unique_ptr<Value> 的析构（发生在 Graph 的移动赋值里）；
//   普通构建：未定义行为，可能打印出垃圾名字，也可能碰巧「正常」。
// 第 8 天的借用规则在今天的 API 上原样成立：主人要活得比引用久——
// 现在的主人是 g 本身，g 被重新赋值的那一刻，旧引用一起失效。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Graph.cpp ../src/Interpreter.cpp ../src/Verifier.cpp ../src/Frontend.cpp \
//     err_outlived_graph.cpp -o err_outlived_graph && ./err_outlived_graph
#include <cstdio>
#include <string>
#include <vector>

#include "Frontend.h"
#include "Graph.h"
#include "Model.h"
#include "Node.h"
#include "Value.h"

int main() {
    // 崩溃演示专用：关掉 stdout 缓冲，保证 ASan 报告前的输出能落地。
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    Model m1;
    m1.name = "first";
    m1.inputs = {{"A", {Dtype::F32, {2, 3}}}, {"B", {Dtype::F32, {3, 2}}}};
    m1.weights = {{"bias", {Dtype::F32, {2, 2}}, {0, -1, -2, -3}}};
    m1.layers = {
        {"MatMul", {"A", "B"}, "C"},
        {"Add", {"C", "bias"}, "D"},
        {"Relu", {"D"}, "Y"},
    };
    m1.outputs = {"Y"};

    Graph g = lower_model_to_graph(m1);
    const Value* y = g.outputs()[0];  // 记下「门牌号」——借用，不是所有权
    std::printf("第一次 lower：%s，输出叫 %%%s（指针 %p）\n", g.name().c_str(),
                y->name().c_str(), static_cast<const void*>(y));

    // 换个模型重新 lower：g 被移动赋值，旧图的值和节点在这行里析构。
    Model m2;
    m2.name = "second";
    m2.inputs = {{"X", {Dtype::F32, {2, 2}}}};
    m2.layers = {{"Relu", {"X"}, "R"}};
    m2.outputs = {"R"};
    g = lower_model_to_graph(m2);
    std::printf("第二次 lower：图换成了 \"%s\"（旧图已整体析构）\n", g.name().c_str());

    // 还想用旧指针？主人已经不在了。
    std::printf("现在去读旧图的输出名字……\n");
    std::printf("旧 %%%s\n", y->name().c_str());  // ← ASan 在这里抓到悬空读
    return 0;
}
