#pragma once

#include "Graph.h"
#include "Model.h"

// 前端（Frontend）：模型世界 → 图 IR 的翻译官。
// MLIR 生态里对应「把 ONNX/TFLite 导入成 MLIR」的那一层；
// 今天的版本只有一个函数、一条规则：按拓扑序逐层翻译，
// 名字经符号表换成 Value 对象身份。
//
// 职责边界（今天刻意不做的）：
//   - 不解析文本——Model 是 C++ 结构体，第 41 天起才从文件来；
//   - 不做优化、不查层与层的语义等价——那是第 22 天以后 Pass 的事；
//   - 不跑 Verifier——工厂是带守卫的建造路径，验证在边界处由调用方
//     显式执行（第 12 天的分工：先 verify 再碰）。
//
// 错误语义：映射失败是「构造失败」（第 12 天三种失败的第一种），
// 全部抛 std::invalid_argument，消息一律带「第几层/哪个槽/哪个名字」。
Graph lower_model_to_graph(const Model& m);
