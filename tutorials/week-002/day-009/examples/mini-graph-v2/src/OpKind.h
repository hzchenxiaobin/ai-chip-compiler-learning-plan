#pragma once

#include <cstdint>
#include <string>

// OpKind：算子类型。第 8 天的 kind 只是字符串，今天换成封闭的枚举——
// 拼错名字从「打印出怪图」变成「编译失败」。
// 枚举是「一个类 + kind + 属性」路线的一部分：不为每种算子派生子类。
enum class OpKind : std::uint8_t {
    Constant,  // 常量：值放在属性里，没有输入
    MatMul,    // 矩阵乘：两个二维输入
    Add,       // 逐元素加：两个同形输入
    Relu,      // 逐元素取正：一个输入
};

// 叫 op_name 而不是 to_string：Graph::to_string() 成员会遮蔽同名自由函数，
// 第 8 天踩过的名字隐藏坑，这里直接绕开。
inline std::string op_name(OpKind k) {
    switch (k) {
        case OpKind::Constant: return "constant";
        case OpKind::MatMul:   return "matmul";
        case OpKind::Add:      return "add";
        case OpKind::Relu:     return "relu";
    }
    return "?";
}
