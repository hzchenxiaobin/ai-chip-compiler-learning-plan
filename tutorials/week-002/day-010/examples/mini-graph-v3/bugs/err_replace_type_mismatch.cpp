// 反面教材（三）：replace 的两个廉价检查。
//   1) 类型不一致的替换：槽位上的类型契约会被静默破坏，当场拒绝；
//   2) 自己替换自己：语义上是空操作，但多半是调用方写错了方向。

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
    run_case("把 f32<2x2> 的使用者改指 f32<2x3>", [] {
        Graph g("t");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_matmul(a, b, "C");          // %C : f32<2x2>
        g.add_relu(mm->result(), "Y");
        Value* other = g.add_input("X", {Dtype::F32, {2, 3}});
        g.replace_all_uses_of(mm->result(), other);  // relu 的输入会变成 2x3
    });

    run_case("from 和 to 是同一个值", [] {
        Graph g("t");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Node* relu = g.add_relu(x, "Y");
        g.mark_output(relu->result());
        g.replace_all_uses_of(x, x);
    });

    std::printf("\n要点：replace 只核对类型，不核对数值——\n");
    std::printf("      「类型一致但数值不同」的替换能通过（见正文 5.4 节实验），\n");
    std::printf("      等价性判断是 Pass 的职责，不是账本的职责。\n");
    return 0;
}
