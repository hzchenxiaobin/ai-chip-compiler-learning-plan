#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "Value.h"
#include "Verifier.h"

namespace {

// 把一串 double 按二维 shape 打成矩阵的样子（同第 9～11 天）。
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

// 打印一份验证报告：通过一行带统计，失败逐条列出。
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

}  // namespace

int main() {
    // ================= 第一幕：合法图的完整旅程 =================
    // 经典图与第 9～11 天完全同款：Y = relu(A x B + bias)。
    Graph g("matmul-bias-relu");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
    Node* relu = g.add_relu(add->result(), "Y");
    g.mark_output(relu->result());

    std::printf("== 第一幕：先构造，再验证，然后才敢碰 ==\n%s\n", g.to_string().c_str());
    print_report(g, verify_graph(g));

    // 改图之后账本还在吗？replace ＋ erase 之后立刻重验：
    // 第 10 天的两个入口动过账本，Verifier 的账本核对负责盯住不变量。
    Node* bias2 = g.add_constant("bias2", {Dtype::F32, {2, 2}}, {1.0, 1.0, 1.0, 1.0});
    g.replace_all_uses_of(bias->result(), bias2->result());
    g.erase_node(bias);
    std::printf("\n（replace ＋ erase 之后，账本必须仍然自洽）\n");
    print_report(g, verify_graph(g));

    // 验证只读：跑完 verify，解释器算出的数字应与第 10/11 天一致
    //（bias 换成了全 1，D = C + 1）。
    Interpreter interp;
    interp.bind(a, {1, 2, 3, 4, 5, 6});
    interp.bind(b, {7, 8, 9, 10, 11, 12});
    interp.run(g);
    std::printf("\n（验证是只读的：解释器照常算）\n");
    print_matrix("Y", relu->result()->type(), interp.of(relu->result()));

    // ================= 第二幕：三种失败，三个现场 =================
    // 同一个Shape错误：2x3 的 A 乘 2x2 的 B，内维 3 ≠ 2。
    std::printf("\n== 第二幕：同一个错误（2x3 × 2x2），三种命运 ==\n");

    // 命运一：走工厂——构造失败，当场抛异常。
    Graph g1("via-factory");
    Value* a23 = g1.add_input("A", {Dtype::F32, {2, 3}});
    Value* b22 = g1.add_input("B", {Dtype::F32, {2, 2}});
    try {
        g1.add_matmul(a23, b22, "C");
        std::printf("命运一（工厂）：竟然造出来了？不该走到这里\n");
    } catch (const std::invalid_argument& e) {
        std::printf("命运一（构造失败，当场抛）：\n  what(): %s\n", e.what());
    }

    // 命运二：走 raw 后门——图造出来了，Verifier 报告一次列全。
    Graph g2("via-raw");
    Value* a23b = g2.add_input("A", {Dtype::F32, {2, 3}});
    Value* b22b = g2.add_input("B", {Dtype::F32, {2, 2}});
    g2.add_raw_node(OpKind::MatMul, {a23b, b22b}, Attrs{}, {Dtype::F32, {2, 2}}, "C");
    g2.mark_output(g2.nodes()[0]->result());
    std::printf("命运二（验证失败，一次列全）：\n");
    print_report(g2, verify_graph(g2));

    // 命运三：图是合法的，数据是错的——运行失败，解释器在 bind 时抛。
    //（第四种命运「不验证直接跑」在 bugs/err_oob_read.cpp：那是未定义行为。）
    Graph g3("via-runtime");
    Value* a3 = g3.add_input("A", {Dtype::F32, {2, 3}});
    Value* b3 = g3.add_input("B", {Dtype::F32, {3, 2}});
    Node* mm3 = g3.add_matmul(a3, b3, "C");
    g3.mark_output(mm3->result());
    Interpreter interp3;
    try {
        interp3.bind(a3, {1, 2, 3, 4});  // A 需要 6 个元素，只给 4 个
        interp3.run(g3);
    } catch (const std::invalid_argument& e) {
        std::printf("命运三（运行失败，数据与类型不符）：\n  what(): %s\n", e.what());
    }

    // ================= 第三幕：多错误一次报全 =================
    // 四个错误藏在一张图里：假 kind、输入数量错、常量数据不够、
    // 没有输出。工厂世界一次只能抛第一个；Verifier 一张单子列全。
    std::printf("\n== 第三幕：一张图藏四个错，Verifier 一次列全 ==\n");
    Graph g4("four-errors");
    Value* x = g4.add_input("x", {Dtype::F32, {2, 2}});
    Value* y = g4.add_input("y", {Dtype::F32, {2, 2}});
    // 错误 1：枚举外的野 kind（第 11 天 bugs/err_silent_fake_kind.cpp 的主角）。
    g4.add_raw_node(static_cast<OpKind>(99), {x, y}, Attrs{}, {Dtype::F32, {2, 2}}, "G");
    // 错误 2：relu 塞了两个输入。
    g4.add_raw_node(OpKind::Relu, {x, y}, Attrs{}, {Dtype::F32, {2, 2}}, "R");
    // 错误 3：常量声明 f32<2x2> 却只给 3 个数。
    Attrs kAttrs;
    kAttrs.data = {1, 2, 3};
    g4.add_raw_node(OpKind::Constant, {}, kAttrs, {Dtype::F32, {2, 2}}, "k");
    // 错误 4：整张图没有 mark_output。
    print_report(g4, verify_graph(g4));
    return 0;
}
