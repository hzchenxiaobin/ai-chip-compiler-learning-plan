// 反面教材（二）：三个构造期廉价检查的真实输出。
// 每个错误都用 try/catch 接住并打印——异常消息指名道姓，
// 定位时不需要调试器。如果不接住，进程会直接终止（非零退出码）。

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
    run_case("内维不匹配", [] {
        Graph g("t");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {2, 3}});  // 忘了 transpose_b
        g.add_matmul(a, b, "C");
    });

    run_case("dtype 不一致", [] {
        Graph g("t");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F16, {3, 2}});
        g.add_matmul(a, b, "C");
    });

    run_case("常量数据个数与 Shape 不符", [] {
        Graph g("t");
        g.add_constant("c", {Dtype::F32, {2, 2}}, {1.0, 2.0, 3.0});  // 少给一个
    });

    run_case("逐元素算子 Shape 不一致", [] {
        Graph g("t");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Value* y = g.add_input("y", {Dtype::F32, {2, 3}});
        g.add_elementwise(OpKind::Add, x, y, "z");
    });
    return 0;
}
