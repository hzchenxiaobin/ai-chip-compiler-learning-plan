// 反面教材（第 12 天核心）：跳过 verify 直接跑解释器。
// 同一个错误——2x3 的 A 乘 2x2 的 B，内维 3 ≠ 2——这次既不走工厂
//（工厂会当场抛），也不 verify（Verifier 会一次列全），直接交给
// 解释器。解释器按错误的内维 k=3 去读只有 4 个元素的 B：
//   at(b, cols=2, p=2, j) → b[2*2+j] → b[4..5] —— 越界读。
// 现象（分构建）：
//   普通构建：不报错，悄悄读走 B 缓冲区后面的内存，结果看起来
//   「像模像样」——错误答案混过去了；
//   ASan 构建：heap-buffer-overflow READ of size 8，第一现场就指到
//   Interpreter.cpp 的 at()。
// 这就是「验证失败」和「运行失败」之间那条看不见的线：
// 不验证，非法 IR 的报错方式是未定义行为，轮不到你挑。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src ../src/Graph.cpp ../src/Interpreter.cpp err_oob_read.cpp -o err_oob_read && ./err_oob_read
#include <cstdio>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "Value.h"

int main() {
    // 崩溃演示专用：关掉 stdout 缓冲，保证 ASan 报告前的输出能落地。
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    Graph g("no-verify");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {2, 2}});
    // raw 后门：不查 Shape，内维 3 vs 2 的 matmul 照样造出来。
    Node* mm = g.add_raw_node(OpKind::MatMul, {a, b}, Attrs{}, {Dtype::F32, {2, 2}}, "C");
    g.mark_output(mm->result());
    std::printf("图造好了，跳过 verify，直接跑解释器……\n");

    Interpreter interp;
    interp.bind(a, {1, 2, 3, 4, 5, 6});
    interp.bind(b, {7, 8, 9, 10});
    interp.run(g);
    const std::vector<double>& r = interp.of(mm->result());
    std::printf("%%C =\n %g %g\n %g %g\n", r[0], r[1], r[2], r[3]);
    std::printf("(若没有 ASan，上面就是悄悄算错的答案；有 ASan，到不了这一行)\n");
    return 0;
}
