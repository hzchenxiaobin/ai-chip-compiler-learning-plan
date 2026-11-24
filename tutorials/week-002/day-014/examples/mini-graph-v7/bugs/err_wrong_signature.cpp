// 反面教材：给访问者补 visit_mul 时签名写错——override 拯救了你。
//
// 现象：编译失败，编译器同时给出两层信息：
//   1) error: cannot declare variable ... to be of abstract type —— 类还是抽象的；
//   2) note: virtual void NodeVisitor::visit_mul(const Node&) —— 缺的正是它。
// 原因：visit_mul(Node&) 写成了非 const 参数（少了 const），
//       它不是重写（override），而是一个新的虚函数；
//       纯虚的 visit_mul(const Node&) 仍未实现。
// 修复：签名必须与接口完全一致；写上 override 关键字，
//       签名不匹配时编译器直接在那一行报错，不用猜。
//
// 编译（在 bugs/ 目录下，预期失败）：
//   g++ -std=c++17 -g -Wall -Wextra -I ../src err_wrong_signature.cpp \
//       ../src/Graph.cpp ../src/Verifier.cpp -o err_wrong_signature
//
// 把下面的参数补上 const、函数签名对齐接口并加上 override，
// 再编译一次，对照错误信息的读法。

#include <cstdio>
#include <string>

#include "Graph.h"
#include "Node.h"
#include "NodeVisitor.h"
#include "Value.h"

namespace {

class BadCounter : public NodeVisitor {
public:
    void visit_constant(const Node&) override { ++constant_; }
    void visit_matmul(const Node&) override { ++matmul_; }
    void visit_add(const Node&) override { ++add_; }
    void visit_relu(const Node&) override { ++relu_; }
    // 下面的参数少了 const：不是 override，是新增的虚函数。
    void visit_mul(Node& n) /* 这里本该有 override，但签名对不上 */ {
        ++mul_;
        (void)n;
    }

    std::int64_t constant_ = 0, matmul_ = 0, add_ = 0, relu_ = 0, mul_ = 0;
};

}  // namespace

int main() {
    Graph g("demo");
    Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
    Node* w = g.add_constant("w", {Dtype::F32, {2, 2}}, {1, 0, 0, 2});
    Node* m = g.add_elementwise(OpKind::Mul, x, w->result(), "M");
    g.mark_output(m->result());

    BadCounter counter;  // ← 编译器在这一行报「抽象类」：BadCounter 没有真正实现
                         //    NodeVisitor::visit_mul(const Node&)
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        apply_visitor(counter, *n);
    }
    std::printf("mul 计数 = %lld\n", static_cast<long long>(counter.mul_));
    return 0;
}
