#pragma once

#include <string>
#include <vector>

#include "TensorType.h"

// Model：模型世界的描述——今天相当于一张极简 ONNX 的内存形态。
// 模型世界的三个特征，今天全部要拿来和 IR 世界对照：
//   1) 张量用「字符串名字」引用（ONNX 的 NodeProto.input 就是字符串表）；
//   2) 层与层之间的连接关系藏在名字里（"Add 的输入是 C"，C 是谁？查名字）；
//   3) 权重带着数据一起走（initializer：编译期就已知的数据）。
// 对应到 IR 世界：名字 → Value 对象身份，连接 → 输入槽里的指针，
// 权重数据 → Constant 节点的属性。翻译工作在 Frontend.cpp。

// 图输入：运行期才有的数据（激活值）。名字 + 类型。
struct ModelInput {
    std::string name;
    TensorType type;
};

// 权重（ONNX 叫 initializer）：编译期已知的数据。
// 今天作为 Constant 节点进图——它与图输入的分界是第 13 天的对照实验。
struct ModelWeight {
    std::string name;
    TensorType type;
    std::vector<double> data;
};

// 一层计算（ONNX 的 NodeProto）。op 用字符串：模型世界的算子名
// 是数据，不是类型——拼错要到映射时才发现，这正是今天要体会的边界。
struct ModelLayer {
    std::string op;                 // "MatMul" / "Add" / "Relu"
    std::vector<std::string> inputs;  // 引用名字（可能拼错、可能重复）
    std::string output;
    bool transpose_a = false;       // 仅 MatMul 使用；别的算子带上了会被拒绝
    bool transpose_b = false;
};

struct Model {
    std::string name;
    std::vector<ModelInput> inputs;
    std::vector<ModelWeight> weights;
    std::vector<ModelLayer> layers;      // 必须按拓扑序排列（ONNX 同款契约）
    std::vector<std::string> outputs;    // 图输出的名字
};

// 模型侧的打印视图：lower 之前它长什么样。教学/调试用，
// 不是 IR——IR 的文本形式是 Graph::to_string()。
inline std::string model_to_string(const Model& m) {
    std::string text = "model \"" + m.name + "\" {\n";
    for (const ModelInput& in : m.inputs) {
        text += "  input " + in.name + " : " + in.type.to_string() + "\n";
    }
    for (const ModelWeight& w : m.weights) {
        text += "  weight " + w.name + " : " + w.type.to_string() + " = [";
        for (std::size_t i = 0; i < w.data.size(); ++i) {
            if (i != 0) {
                text += ", ";
            }
            std::string v = std::to_string(w.data[i]);
            v.erase(v.find_last_not_of('0') + 1, std::string::npos);
            if (!v.empty() && v.back() == '.') {
                v.pop_back();
            }
            text += v;
        }
        text += "]\n";
    }
    for (std::size_t i = 0; i < m.layers.size(); ++i) {
        const ModelLayer& l = m.layers[i];
        text += "  layer " + std::to_string(i + 1) + ": " + l.op + "(";
        for (std::size_t j = 0; j < l.inputs.size(); ++j) {
            if (j != 0) {
                text += ", ";
            }
            text += l.inputs[j];
        }
        text += ") -> " + l.output;
        if (l.transpose_a || l.transpose_b) {
            text += std::string(" {") + (l.transpose_a ? "transpose_a" : "") +
                    (l.transpose_a && l.transpose_b ? ", " : "") +
                    (l.transpose_b ? "transpose_b" : "") + "}";
        }
        text += "\n";
    }
    for (const std::string& out : m.outputs) {
        text += "  output " + out + "\n";
    }
    return text + "}";
}
