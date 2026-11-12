#include "TopoSort.h"

#include <algorithm>
#include <functional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>

#include "Graph.h"
#include "Node.h"
#include "OpKind.h"
#include "Value.h"

// 拓扑排序怎么工作，一句话版本：
//   反复找出「所有依赖都已就绪」的节点，剥下来排进结果；
//   剥掉一个节点，就通知它的使用者（use 账本！）把等待计数减一；
//   全部剥完 = 拓扑序；剥到一半剥不动了 = 图里有环。
//
// 这是 Kahn 算法（1962）。今天的变体是「一波剥一组」而不是
// 「一次剥一个」：同一波里的节点互不依赖，可以并行执行——
// 这一份波次表就是最朴素的并行调度表，第 102～103 天的
// 流水线要的「哪些计算能同时开跑」，答案从这里长出来。

namespace {

// 每个节点「还没就绪的依赖」计数：有生产者的输入槽计 1。
// 图输入（producer == nullptr）不是节点依赖，不计；
// 空槽不计（那是 Verifier 要拦的非法图，别在这里越权）。
// 重复槽位（如 add(%C, %C)）计 2——生产者剥下时账本里恰好有
// 两条记录、减两次，一一相抵。第 10 天的账本今天又付了一次利息。
std::int64_t pending_deps(const Node* n) {
    std::int64_t deps = 0;
    for (const Value* in : n->inputs()) {
        if (in != nullptr && in->producer() != nullptr) {
            ++deps;
        }
    }
    return deps;
}

// 三色 DFS 找环路径（只作诊断用，排序失败时才跑）。
// 白 = 没碰过；灰 = 在当前递归栈上；黑 = 已经安全走完。
// 走到「灰」节点 = 绕回了自己这条路径 = 找到环：
// 栈里从它第一次出现的位置到栈顶，加上它自己收尾，就是环路径。
//
// 递归深度 = 依赖链长度。教程规模的图没问题；工业编译器对
// 超长链会改写迭代版——道理相同，栈换成显式的 vector。
bool find_cycle_dfs(const Node* n, const std::unordered_set<const Node*>& node_set,
                    std::unordered_map<const Node*, int>& color, std::vector<const Node*>& stack,
                    std::vector<const Node*>& cycle) {
    color[n] = 1;  // 灰
    stack.push_back(n);
    for (const Value* in : n->inputs()) {
        if (in == nullptr) {
            continue;
        }
        const Node* p = in->producer();
        // 只走本图的边：图输入没有生产者；生产者不在本图的值
        // 是 Verifier 第 12 天「值归属」要拦的非法图——这里不越权，
        // 也不把别人的节点画进我们的环里。
        if (p == nullptr || node_set.find(p) == node_set.end()) {
            continue;
        }
        const auto it = color.find(p);
        if (it == color.end() || it->second == 0) {
            if (find_cycle_dfs(p, node_set, color, stack, cycle)) {
                return true;
            }
        } else if (it->second == 1) {
            // 命中灰节点：环找到了。
            const auto first = std::find(stack.begin(), stack.end(), p);
            cycle.assign(first, stack.end());
            cycle.push_back(p);  // 首尾同节点，把圈画闭合
            return true;
        }
    }
    color[n] = 2;  // 黑
    stack.pop_back();
    return false;
}

// 在整张图上找一条环路径；找不到（比如只是依赖了不属于本图的
// 节点）就返回空——诊断消息会走另一条分支，不冒充环检测。
std::vector<const Node*> find_cycle(const Graph& g,
                                    const std::unordered_set<const Node*>& node_set) {
    std::unordered_map<const Node*, int> color;
    std::vector<const Node*> stack;
    std::vector<const Node*> cycle;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        if (color[n.get()] == 0 && find_cycle_dfs(n.get(), node_set, color, stack, cycle)) {
            return cycle;
        }
    }
    return {};
}

}  // namespace

TopoSortResult topo_sort(const Graph& g) {
    TopoSortResult result;

    std::unordered_set<const Node*> node_set;
    std::unordered_map<const Node*, std::int64_t> pending;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        node_set.insert(n.get());
        pending.emplace(n.get(), pending_deps(n.get()));
    }

    // 第一波：等待计数为 0 的节点（吃图输入的算子、常量），按创建序。
    std::vector<const Node*> frontier;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        if (pending[n.get()] == 0) {
            frontier.push_back(n.get());
        }
    }

    // 逐波剥离。
    while (!frontier.empty()) {
        result.waves.push_back(frontier);
        std::vector<const Node*> next;
        for (const Node* n : frontier) {
            const Value* out = n->result();
            if (out == nullptr) {
                continue;  // 防御：结果值理论上永远非空（Verifier 查）
            }
            for (const Use& u : out->users()) {
                // 账本的每条 (user, slot) 记录让 user 恰好减一次。
                const auto it = pending.find(u.user);
                if (it == pending.end() || it->second <= 0) {
                    continue;  // 使用者不在本图，或账本有重复记录——Verifier 的活
                }
                if (--it->second == 0) {
                    next.push_back(u.user);
                }
            }
        }
        frontier = std::move(next);
    }

    // 拼出线性拓扑序，统计剥下/卡住。
    for (const std::vector<const Node*>& wave : result.waves) {
        result.order.insert(result.order.end(), wave.begin(), wave.end());
    }
    result.peeled = static_cast<std::int64_t>(result.order.size());
    result.stuck = g.num_nodes() - result.peeled;

    if (result.stuck > 0) {
        result.ok = false;
        result.cycle = find_cycle(g, node_set);
    }
    return result;
}

std::string cycle_to_string(const std::vector<const Node*>& cycle) {
    std::string s;
    for (std::size_t i = 0; i < cycle.size(); ++i) {
        if (i != 0) {
            s += " -> ";
        }
        s += op_name(cycle[i]->kind()) + "%n" + std::to_string(cycle[i]->id());
    }
    return s;
}

std::string topo_error_message(const Graph& g, const TopoSortResult& r) {
    std::string msg = "topo_sort: 图 \"" + g.name() + "\" ";
    if (!r.cycle.empty()) {
        msg += "含环，无拓扑序：" + cycle_to_string(r.cycle) + "（环上 " +
               std::to_string(r.cycle.size() - 1) + " 个节点；";
    } else {
        msg += "有 " + std::to_string(r.stuck) +
               " 个节点无法调度——依赖了不属于本图的值？先跑 Verifier（";
    }
    msg += "已剥 " + std::to_string(r.peeled) + " 个、卡住 " + std::to_string(r.stuck) + " 个）";
    return msg;
}
