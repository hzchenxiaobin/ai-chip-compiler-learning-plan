// 反面教材：想要「两张一样的图」，直接按值拷贝 Graph。
// 编译器在这一行拒绝——Graph 的拷贝被成员里的 unique_ptr 连带删除。

#include <cstdio>

#include "Graph.h"
#include "Node.h"
#include "Value.h"

Graph build_one() {
    Graph g("add-relu");
    Value* a = g.add_input("a");
    Value* b = g.add_input("b");
    Node* add = g.add_node("add", {a, b}, "t");
    Node* relu = g.add_node("relu", {add->result()}, "y");
    g.mark_output(relu->result());
    return g;  // 返回局部图：移动接管（合法），不是拷贝
}

int main() {
    Graph g1 = build_one();
    Graph g2 = g1;  // ← 编译错误：Graph 的拷贝构造被删除
    std::printf("%s\n", g2.to_string().c_str());
    return 0;
}
