// 反面教材（一）：删除仍有使用者的节点——被 use 表当场拦下。
// 异常消息点名剩余使用者和槽位，定位不需要调试器。
// 如果不接住异常，进程会以非零退出码终止。

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
    run_case("删除仍被 add 使用的 matmul（add 还重复用了两次）", [] {
        Graph g("t");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_matmul(a, b, "C");
        g.add_elementwise(OpKind::Add, mm->result(), mm->result(), "D");  // add(%C, %C)
        g.erase_node(mm);  // %C 身上还挂着两条 use 记录
    });

    run_case("删除仍被 relu 使用的 add", [] {
        Graph g("t");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Value* y = g.add_input("y", {Dtype::F32, {2, 2}});
        Node* add = g.add_elementwise(OpKind::Add, x, y, "D");
        g.add_relu(add->result(), "Y");
        g.erase_node(add);  // %D 还被 relu 用着
    });

    std::printf("\n要点：被拦下的删除不会留下半套修改——异常抛出前账本一个字都没动。\n");
    return 0;
}
