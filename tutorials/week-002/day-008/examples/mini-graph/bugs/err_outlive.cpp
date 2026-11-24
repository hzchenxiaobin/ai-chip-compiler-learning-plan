// 反面教材：图析构之后还拿着它的节点指针用。
// Graph 是唯一所有人，主人没了，借用的指针就悬空——第 7 天的规则
// 「主人要活得比引用久」在图 IR 上原样成立。ASan 构建下当场报告。

#include <cstdio>

#include "Graph.h"
#include "Node.h"
#include "Value.h"

int main() {
    const Node* leaked = nullptr;
    {
        Graph g("tmp");
        Value* a = g.add_input("a");
        Node* relu = g.add_node("relu", {a}, "y");
        g.mark_output(relu->result());
        leaked = relu;  // 把「借用」带出了主人的作用域
    }  // g 析构：unique_ptr 释放了所有节点和值

    std::printf("图已析构，还想用它的节点：kind = %s\n",
                 leaked->kind().c_str());  // 悬空读取，ASan 在这里报告
    return 0;
}
