#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "Value.h"

namespace {

// 把一串 double 按二维 shape 打成矩阵的样子（同第 9 天）。
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
    // ================= 第一幕：经典图 + use 表 =================
    Graph g("matmul-bias-relu");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
    Node* relu = g.add_relu(add->result(), "Y");
    g.mark_output(relu->result());

    std::printf("== 第一幕：Y = relu(A x B + bias)，先看 use 表 ==\n%s\n\n",
                g.to_string().c_str());
    std::printf("%s\n\n", g.uses_to_string().c_str());

    // 反面对照：没有 use 表时，「谁在用 %C」只能扫全图。
    // 这里只数访问过的输入槽个数——不做计时，计数本身就是证据。
    std::size_t slots = 0;
    std::size_t hits = 0;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            ++slots;
            if (n->input(i) == mm->result()) {
                ++hits;
            }
        }
    }
    std::printf("问「谁在用 %%C」：扫全图 = 访问 %zu 个节点、%zu 个输入槽，找到 %zu 个使用者；\n",
                static_cast<std::size_t>(g.num_nodes()), slots, hits);
    std::printf("use 表直读 = num_uses() 返回 %zu（图越长扫描越慢，账本永远是常数次）\n\n",
                mm->result()->num_uses());

    // 解释器算出基准数字（第三幕要回来对照它）。
    Interpreter interp;
    interp.bind(a, {1, 2, 3, 4, 5, 6});
    interp.bind(b, {7, 8, 9, 10, 11, 12});
    interp.run(g);
    std::printf("== 解释器基准（第三幕回来对照）==\n");
    print_matrix("Y", relu->result()->type(), interp.of(relu->result()));

    // ================= 第二幕：迷你 CSE =================
    Graph g2("duplicate-matmul");
    Value* a2 = g2.add_input("A", {Dtype::F32, {2, 3}});
    Value* b2 = g2.add_input("B", {Dtype::F32, {3, 2}});
    Node* mm1 = g2.add_matmul(a2, b2, "C1");
    Node* mm2 = g2.add_matmul(a2, b2, "C2");  // 和 mm1 输入、属性完全相同的一次计算
    Node* add2 = g2.add_elementwise(OpKind::Add, mm1->result(), mm2->result(), "D");
    Node* relu2 = g2.add_relu(add2->result(), "Y");
    g2.mark_output(relu2->result());

    std::printf("== 第二幕：两个一模一样的 matmul（第 26 天 CSE 的靶子）==\n%s\n\n",
                g2.to_string().c_str());
    std::printf("%s\n\n", g2.uses_to_string().c_str());

    // 替换前先算基准：C1 与 C2 逐元素相等，所以 D = C1 + C2 = 2 x C1。
    Interpreter before;
    before.bind(a2, {1, 2, 3, 4, 5, 6});
    before.bind(b2, {7, 8, 9, 10, 11, 12});
    before.run(g2);
    std::printf("== 替换前，解释器先算基准 ==\n");
    print_matrix("D", add2->result()->type(), before.of(add2->result()));
    print_matrix("Y", relu2->result()->type(), before.of(relu2->result()));

    // CSE 的两步：先把 %C2 的使用者改指 %C1，再删除变成死代码的 mm2。
    g2.replace_all_uses_of(mm2->result(), mm1->result());
    std::printf("\n== replace_all_uses_of(%%C2, %%C1) 之后：账本搬家 ==\n%s\n\n",
                g2.uses_to_string().c_str());

    // 想一步到位删掉 mm1（它的结果 %C1 此刻有 2 个使用者）？当场被拦：
    try {
        g2.erase_node(mm1);
    } catch (const std::invalid_argument& e) {
        std::printf("试图删除仍被使用的 mm1 → std::invalid_argument: %s\n\n", e.what());
    }

    const long nodes_before = static_cast<long>(g2.num_nodes());
    const long values_before = static_cast<long>(g2.num_values());
    g2.erase_node(mm2);  // %C2 已无人使用，可以删了
    std::printf("== erase_node(mm2) 之后：节点 %ld -> %ld，值 %ld -> %ld ==\n%s\n\n",
                nodes_before, static_cast<long>(g2.num_nodes()), values_before,
                static_cast<long>(g2.num_values()), g2.to_string().c_str());

    // 用一个全新的解释器再算一遍——数字必须与替换前一字不差。
    Interpreter after;
    after.bind(a2, {1, 2, 3, 4, 5, 6});
    after.bind(b2, {7, 8, 9, 10, 11, 12});
    after.run(g2);
    std::printf("== 替换后，解释器再算一遍（语义不变的证明）==\n");
    print_matrix("D", add2->result()->type(), after.of(add2->result()));
    print_matrix("Y", relu2->result()->type(), after.of(relu2->result()));

    // ================= 第三幕：结构合法 ≠ 语义等价 =================
    Graph g3("semantic-replace");
    Value* a3 = g3.add_input("A", {Dtype::F32, {2, 3}});
    Value* b3 = g3.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias3 = g3.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm3 = g3.add_matmul(a3, b3, "C");
    Node* add3 = g3.add_elementwise(OpKind::Add, mm3->result(), bias3->result(), "D");
    Node* relu3 = g3.add_relu(add3->result(), "Y");
    g3.mark_output(relu3->result());

    // 同类型、不同数值的常量：replace 只核对类型，从不核对数值——
    // 「该不该替换」是 Pass 的判断，不是账本的判断。
    Node* bias_new = g3.add_constant("bias2", {Dtype::F32, {2, 2}}, {10.0, 20.0, 30.0, 40.0});
    g3.replace_all_uses_of(bias3->result(), bias_new->result());
    g3.erase_node(bias3);  // 旧常量已无人使用

    std::printf("== 第三幕：把 %%bias 的使用者改指数值不同的 %%bias2（类型一致，数值不同）==\n%s\n\n",
                g3.to_string().c_str());

    Interpreter interp3;
    interp3.bind(a3, {1, 2, 3, 4, 5, 6});
    interp3.bind(b3, {7, 8, 9, 10, 11, 12});
    interp3.run(g3);
    std::printf("== 解释器：结构变换全部成功，数字却变了 ==\n");
    print_matrix("Y", relu3->result()->type(), interp3.of(relu3->result()));
    std::printf("  （第一幕同款图的 Y = [58, 0; 0, 104]；bias 换了数值，Y 就跟着变——\n");
    std::printf("   账本保证「每个使用者都被改到」，不保证「改了还等于原来」）\n");
    return 0;
}
