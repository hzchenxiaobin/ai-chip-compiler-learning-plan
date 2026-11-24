#pragma once

#include <string>
#include <unordered_map>
#include <vector>

#include "Graph.h"

// Interpreter：教程自带的验收工具，不是编译器的一部分
//（真正的执行要等到第 116 天之后的 Lowering / Runtime）。
// 它按拓扑序把图「算」一遍，验证我们记录的类型和属性足够还原语义。
// 只支持 f32 的 double 累加，只服务今天的四种算子。
class Interpreter {
public:
    // 为图输入绑定具体数据（元素个数必须与类型一致）。
    void bind(const Value* input, std::vector<double> data);

    // 按拓扑序求值，结果存在表里。
    void run(const Graph& g);

    // 取某个值的计算结果。
    const std::vector<double>& of(const Value* v) const;

private:
    std::unordered_map<const Value*, std::vector<double>> storage_;
};
