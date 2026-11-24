// 反面教材（一）：还按第 8 天的字符串 API 造节点。
// v1 里拼错 kind 只是打印出一张怪图；v2 换成 OpKind 枚举后，
// 同样的拼写错误变成编译错误——一类运行期问题被挪到了编译期。
// 预期：编译失败，错误信息指向 "mutl"。

#include "Graph.h"
#include "Node.h"
#include "Value.h"

int main() {
    Graph g("typo");
    Value* a = g.add_input("a", {Dtype::F32, {2, 2}});
    Value* b = g.add_input("b", {Dtype::F32, {2, 2}});
    g.add_node("mutl", {a, b}, "c");  // v1 的老写法：字符串拼错
    return 0;
}
