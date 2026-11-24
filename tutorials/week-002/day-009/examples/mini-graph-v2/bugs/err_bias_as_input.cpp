// 反面教材（三）：把常量值做成图输入——能编译、能打印、解释器照样算对，
// 但它是一个设计错误：编译期本该知道的数据被藏到了运行期。
// 对比 err_bias_as_input 与正文 main.cpp 打印的 IR：
//   正确版本：1 个 constant 节点，数据在属性里，图输入只有 A、B；
//   错误版本：图输入变成 A、B、bias 三个，数据消失在 IR 之外。
// 后果：第 24/47 天的常量折叠要读 bias 的值，输入的值编译期不可见——
// 优化机会直接丢失。判据：优化时要读它的值 → 属性；不要 → 输入。

#include <cstdio>

#include "Graph.h"
#include "Node.h"
#include "Value.h"
#include "Interpreter.h"

int main() {
    Graph g("bias-as-input");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Value* bias = g.add_input("bias", {Dtype::F32, {2, 2}});  // ← 错在这一行
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias, "D");
    Node* relu = g.add_relu(add->result(), "Y");
    g.mark_output(relu->result());

    std::printf("%s\n\n", g.to_string().c_str());
    std::printf("图输入 %zu 个（正确版本是 2 个）：\n", g.inputs().size());
    for (const Value* v : g.inputs()) {
        std::printf("  %%%s : %s  ← 数值必须由运行期喂数据\n", v->name().c_str(),
                    v->type().to_string().c_str());
    }
    std::printf("图里没有任何地方记录 bias 的具体数值——编译期看不见它。\n");

    // 解释器仍然能算对：因为运行期我们手动绑定了数据。
    Interpreter interp;
    interp.bind(a, {1, 2, 3, 4, 5, 6});
    interp.bind(b, {7, 8, 9, 10, 11, 12});
    interp.bind(bias, {0.0, -100.0, -150.0, -50.0});
    interp.run(g);
    std::printf("（解释器算出的 %%Y 与正确版本相同——错误不体现在数值，体现在可优化性）\n");
    return 0;
}
