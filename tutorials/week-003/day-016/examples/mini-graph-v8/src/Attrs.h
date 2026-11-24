#pragma once

#include <vector>

// Attrs：节点的属性——构造图时就已经确定的编译期数据。
// 与输入（Value，数据流里运行期才知道内容的值）相对。
//
// 今天的属性集只装现在就有用的东西：
// - Constant 用 data 存常量值（元素个数由结果的 TensorType 决定）；
// - MatMul 用 transpose_a / transpose_b 记录「小差异」，而不是派生子类。
//
// 等算子多起来，这里会换成通用的「名字 -> 值」字典（MLIR 的做法）；
// 四种算子就用具名字段，够用且类型安全（YAGNI）。
// 第 14 天复盘：v6 里写过一个 operator==，「留着以后比较属性用」——
// 一周过去没有任何调用方，按 YAGNI 删除；第 26 天 CSE 真正需要比较
// 属性时再回来写（那时才知道 CSE 关心哪些字段，现在写必然猜错）。
struct Attrs {
    bool transpose_a = false;
    bool transpose_b = false;
    std::vector<double> data;  // Constant 的常量值
};
