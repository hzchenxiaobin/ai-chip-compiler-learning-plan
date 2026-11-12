#include <cstdio>
#include <string>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "Value.h"

namespace {

// 把一串 double 按二维 shape 打成矩阵的样子。
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

}  // namespace

int main() {
    Graph g("matmul-bias-relu");

    // 贯穿全文的例子：Y = relu(A x B + bias)——最终项目的迷你版。
    // A: 2x3, B: 3x2 -> C: 2x2；bias 是常量（数据在属性里）；D、Y 同为 2x2。
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
    Node* relu = g.add_relu(add->result(), "Y");
    g.mark_output(relu->result());

    std::printf("== Y = relu(A x B + bias) 的图 ==\n%s\n\n", g.to_string().c_str());

    std::printf("== 四种节点的关键信息 ==\n");
    std::printf("  constant: 输入 %zu 个，数据 %zu 个，结果类型 %s\n",
                bias->num_inputs(), bias->attrs().data.size(),
                bias->result()->type().to_string().c_str());
    std::printf("  matmul:   输入 %zu 个，结果类型 %s（由 [2x3]x[3x2] 算出）\n",
                mm->num_inputs(), mm->result()->type().to_string().c_str());
    std::printf("  add:      输入 %zu 个，结果类型 %s（与两个输入完全一致）\n",
                add->num_inputs(), add->result()->type().to_string().c_str());
    std::printf("  relu:     输入 %zu 个，结果类型 %s\n\n",
                relu->num_inputs(), relu->result()->type().to_string().c_str());

    // 小解释器：按拓扑序算出每个值的具体数字，验证记录的类型/属性足够还原语义。
    Interpreter interp;
    interp.bind(a, {1, 2, 3, 4, 5, 6});
    interp.bind(b, {7, 8, 9, 10, 11, 12});
    interp.run(g);

    std::printf("== 小解释器：按拓扑序算出每个值 ==\n");
    print_matrix("C", mm->result()->type(), interp.of(mm->result()));
    print_matrix("D", add->result()->type(), interp.of(add->result()));
    print_matrix("Y", relu->result()->type(), interp.of(relu->result()));

    // 对照实验：同一个 B 换个存法（存成 2x3 的 B^T），用 transpose_b 属性标记。
    // 数学结果必须一字不差——属性记录的是「怎么读」，不是「另一个算子」。
    Graph g2("transpose-variant");
    Value* a2 = g2.add_input("A", {Dtype::F32, {2, 3}});
    Value* bt = g2.add_input("Bt", {Dtype::F32, {2, 3}});  // 存的是 B 的转置
    Node* mm2 = g2.add_matmul(a2, bt, "C2", /*transpose_a=*/false, /*transpose_b=*/true);
    g2.mark_output(mm2->result());

    std::printf("\n== 对照实验：B 存成转置，transpose_b 属性记录读法 ==\n%s\n\n",
                g2.to_string().c_str());

    Interpreter interp2;
    interp2.bind(a2, {1, 2, 3, 4, 5, 6});
    interp2.bind(bt, {7, 9, 11, 8, 10, 12});  // B^T，按行存
    interp2.run(g2);
    print_matrix("C2", mm2->result()->type(), interp2.of(mm2->result()));
    std::printf("  （与上面的 %%C 完全相同：属性改变读法，不改变数学）\n");
    return 0;
}
