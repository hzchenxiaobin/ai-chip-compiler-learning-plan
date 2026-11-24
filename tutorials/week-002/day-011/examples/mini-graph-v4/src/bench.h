#pragma once

#include <cstdint>

class Graph;
class NodeVisitor;

// 两个 benchmark 循环故意放在独立翻译单元（bench.cpp）：
// 如果循环写在 main.cpp 里，编译器看得见 visitor 的具体类型，
// -O2 会把虚调用「去虚化」成直接调用——测出来的就不是虚函数了。
// 藏到别的 .cpp 里，编译器只能看到 NodeVisitor&，测的才是真·动态分发。
// 这也是今天的一个真实教训：测「动态分发代价」之前，先确认没被优化掉。
std::int64_t bench_switch(const Graph& g, int reps);

// v 只负责分发计数（结果通过派生类读取），bench 不返回值。
void bench_visitor(const Graph& g, NodeVisitor& v, int reps);
