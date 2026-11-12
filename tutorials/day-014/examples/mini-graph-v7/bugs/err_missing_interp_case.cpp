// 反面教材：解释器漏接了 Mul——忽略 -Wswitch 警告的真实代价。
//
// 现象：图完全合法（verify PASS）、程序正常退出（exit 0），
//       但 Mul 节点的结果全是 0——静默错答案。
// 原因：switch 没有 case OpKind::Mul，落到 switch 之外，
//       result 保持初始的全 0 向量。-Wswitch 在编译时警告过一次，
//       警告被忽略后没有任何运行期防线。
//
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -Wall -Wextra -I ../src err_missing_interp_case.cpp
//       ../src/Graph.cpp ../src/Verifier.cpp -o err_missing_interp_case
//   ./err_missing_interp_case; echo "exit code: $?"
//
// 先看编译警告（-Wswitch 点名 Mul），再看输出：
//   buggy Y = 0 0 / 0 0（正确答案：58 0 / 0 308）。

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include <unordered_map>
#include <vector>

#include "Graph.h"
#include "Node.h"
#include "Value.h"
#include "Verifier.h"

namespace {

// 「漏了 Mul」的解释器：与 src/Interpreter.cpp 的唯一差别是
// switch 里没有 case OpKind::Mul。编译器会警告，但只警告一次。
void run_buggy(const Graph& g, std::unordered_map<const Value*, std::vector<double>>& storage) {
    for (const Node* n : g.topological_order()) {
        const TensorType& out = n->result()->type();
        std::vector<double> result(static_cast<std::size_t>(out.num_elements()), 0.0);

        auto at = [](const std::vector<double>& d, std::int64_t cols, std::int64_t r,
                     std::int64_t c) { return d[static_cast<std::size_t>(r * cols + c)]; };

        switch (n->kind()) {
            case OpKind::Constant:
                result = n->attrs().data;
                break;
            case OpKind::MatMul: {
                const std::vector<double>& a = storage.at(n->input(0));
                const std::vector<double>& b = storage.at(n->input(1));
                const std::int64_t m = out.shape[0];
                const std::int64_t k = a.size() / n->input(0)->type().shape[0];
                const std::int64_t n_dim = out.shape[1];
                for (std::int64_t i = 0; i < m; ++i) {
                    for (std::int64_t j = 0; j < n_dim; ++j) {
                        double sum = 0.0;
                        for (std::int64_t p = 0; p < k; ++p) {
                            sum += at(a, n->input(0)->type().shape[1], i, p) *
                                   at(b, n->input(1)->type().shape[1], p, j);
                        }
                        result[static_cast<std::size_t>(i * n_dim + j)] = sum;
                    }
                }
                break;
            }
            case OpKind::Relu: {
                const std::vector<double>& x = storage.at(n->input(0));
                for (std::size_t i = 0; i < x.size(); ++i) {
                    result[i] = std::max(0.0, x[i]);
                }
                break;
            }
            case OpKind::Add: {
                const std::vector<double>& x = storage.at(n->input(0));
                const std::vector<double>& y = storage.at(n->input(1));
                for (std::size_t i = 0; i < x.size(); ++i) {
                    result[i] = x[i] + y[i];
                }
                break;
            }
            // case OpKind::Mul: ……忘了写。-Wswitch 的警告就在这里响起。
        }
        storage[n->result()] = std::move(result);
    }
}

void print_y(const char* who, const std::vector<double>& y) {
    std::printf("%s Y =\n  %g %g\n  %g %g\n", who, y[0], y[1], y[2], y[3]);
}

}  // namespace

int main() {
    // Y = relu(A×B) ⊙ mask：A = 1..6，B = 7..12，mask = [1, 0, 0, 2]。
    // 手算：C = 58 64/139 154 → R = relu(C) 同 → Y = 58 0/0 308。
    Graph g("relu-then-mask");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* mask = g.add_constant("mask", {Dtype::F32, {2, 2}}, {1, 0, 0, 2});
    Node* mm = g.add_matmul(a, b, "C");
    Node* r = g.add_relu(mm->result(), "R");
    Node* mul = g.add_elementwise(OpKind::Mul, r->result(), mask->result(), "Y");
    g.mark_output(mul->result());

    const VerifyReport rep = verify_graph(g);
    std::printf("verify: %s（图本身完全合法——问题不在图上）\n", rep.ok ? "PASS" : "FAIL");

    std::unordered_map<const Value*, std::vector<double>> storage;
    storage[a] = {1, 2, 3, 4, 5, 6};
    storage[b] = {7, 8, 9, 10, 11, 12};
    run_buggy(g, storage);
    print_y("buggy ", storage.at(g.outputs()[0]));
    std::printf("正确答案 Y =\n  58 0\n  0 308\n");
    return 0;
}
