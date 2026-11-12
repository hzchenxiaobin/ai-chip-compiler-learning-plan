// 反面教材（二）：结果被 mark_output 的节点不能删——
// 图输出也是一种「使用者」，只是不住在 use 表里，住在 outputs_ 里。
// 这正是第 25 天 DCE 的规则：无使用者的纯算子可删，图输出必须保留。

#include <cstdio>
#include <stdexcept>

#include "Graph.h"
#include "Node.h"
#include "Value.h"

namespace {

void run_case(const char* title, void (*fn)()) {
    std::printf("== %s ==\n", title);
    try {
        fn();
        std::printf("  没有抛异常（不应该发生）\n");
    } catch (const std::invalid_argument& e) {
        std::printf("  std::invalid_argument: %s\n", e.what());
    }
}

}  // namespace

int main() {
    run_case("删除产出图输出 %Y 的 relu", [] {
        Graph g("t");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Node* relu = g.add_relu(x, "Y");
        g.mark_output(relu->result());
        g.erase_node(relu);  // %Y 无节点使用者，但它是图输出
    });

    run_case("删除结果直接被 mark_output 的 matmul", [] {
        Graph g("t");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_matmul(a, b, "C");
        g.mark_output(mm->result());
        g.erase_node(mm);
    });

    std::printf("\n要点：先取消输出（或换成别的输出）再删节点；\n");
    std::printf("      今天还没有「取消输出」的接口——需要时再加，不预支。\n");
    return 0;
}
