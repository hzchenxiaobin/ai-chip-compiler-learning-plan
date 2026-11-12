// 反面教材：一个「不在枚举表里」的 kind，一路绿灯走到底。
// 现象（三连）：
//   1) to_string() 里这个节点整个消失——apply_visitor 的 switch
//      没有匹配的 case，visit 一个都没调用；
//   2) use 表里它以 "?%n0" 的面目出现——op_name() 落到 return "?"；
//   3) 解释器对它什么都不算，结果是初始化的全 0。
// 全程没有编译错误、没有运行期异常，只有悄悄错掉的输出——
// 这就是把 kind 分发散落在各处、又没有穷尽性检查时的真实代价。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src ../src/Graph.cpp ../src/Interpreter.cpp err_unhandled_kind.cpp -o err_unhandled_kind && ./err_unhandled_kind
#include <cstdio>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "Value.h"

int main() {
    Graph g("bad-kind");
    Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
    Value* y = g.add_input("y", {Dtype::F32, {2, 2}});
    // add_elementwise 不检查 kind 是否在枚举表内（第 9 天留下的口子，
    // 第 12 天 Verifier 来堵）。static_cast<OpKind>(99) 是合法的 uint8_t
    // 值，只是没有对应的名字——模拟「新增算子后有人漏改一处」的后果。
    Node* ghost = g.add_elementwise(static_cast<OpKind>(99), x, y, "G");
    g.mark_output(ghost->result());

    std::printf("== to_string()：注意 %%G 的节点行整个不见了 ==\n%s\n",
                g.to_string().c_str());
    std::printf("== use 表：它以 \"?%%n0\" 的面目出现 ==\n%s\n",
                g.uses_to_string().c_str());

    Interpreter interp;
    interp.bind(x, {1, 2, 3, 4});
    interp.bind(y, {5, 6, 7, 8});
    interp.run(g);
    const std::vector<double>& r = interp.of(ghost->result());
    std::printf("== 解释器：应为逐元素乘 5 12 21 32，实际是 ==\n %g %g\n %g %g\n",
                r[0], r[1], r[2], r[3]);
    std::printf("\n全程零报错。静默的错误，是最难抓的那一种。\n");
    return 0;
}
