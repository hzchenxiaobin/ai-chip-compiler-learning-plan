// 反面教材：在非法图上调用 to_string() —— 连打印都可能崩。
// raw 后门可以造出带空指针输入的节点；Verifier 会先查空指针、
// 跳过语义检查、安全地报告。但 to_string() 没有这层防护：
// NodeLinePrinter::head() 直接 n.input(i)->name() —— 解引用空指针。
// 教训：对「来源不可信」的图，任何接触（打印、解释、遍历）之前
// 先 verify；verify_graph 自己从头到尾不解引用任何可疑指针。
// 现象：SEGV（段错误），ASan 下报 SEGV on unknown address 0x000000000000。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src ../src/Graph.cpp err_print_on_invalid.cpp -o err_print_on_invalid && ./err_print_on_invalid
#include <cstdio>

#include "Graph.h"
#include "Node.h"
#include "Value.h"
#include "Verifier.h"

int main() {
    // 崩溃演示专用：关掉 stdout 缓冲，保证段错误前的输出能落地。
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    Graph g("null-slot");
    Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
    Node* r = g.add_raw_node(OpKind::Relu, {nullptr}, Attrs{}, {Dtype::F32, {2, 2}}, "R");
    g.mark_output(r->result());

    // 正确顺序：先验证——报告空指针，全程不崩。
    const VerifyReport rep = verify_graph(g);
    std::printf("verify 先行：%s\n", rep.ok ? "PASS" : "FAIL（安全地报出问题）");
    for (const std::string& e : rep.errors) {
        std::printf("  error: %s\n", e.c_str());
    }

    // 错误顺序：对同一张图直接 to_string() —— head() 解引用空指针。
    std::printf("现在不验证直接打印同一张图……\n");
    std::printf("%s\n", g.to_string().c_str());
    std::printf("到不了这一行：上面已经段错误了\n");
    (void)x;
    return 0;
}
