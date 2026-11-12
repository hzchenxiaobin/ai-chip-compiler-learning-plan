//===- CombinedPipeline.cpp - 第 48 天：组合优化管道的注册 ----*- C++ -*-===//
//
// 第 48 天的主角：mini-combined——把前面四天攒下的优化能力打包成
// 一条有名字的 Pass 管道（pipeline）。
//
// 到昨天为止，跑全量优化要在命令行手写一串：
//
//   mini-opt -mini-infer-shape -canonicalize input.mlir
//
// 今天把这串注册成一个名字：
//
//   mini-opt -mini-combined input.mlir        // 等价命令
//
// 为什么值得注册？三个理由：
//   1. 顺序是知识。Day 46 实测过：infer-shape 排在 canonicalize
//      后面，加零 bias 就永远消不掉（类型护栏先于形状细化把重写
//      拦下）。把正确顺序固化成管道名，使用者想排错都难。
//   2. 管道是一等公民。PassPipelineRegistration 与单个 Pass 的
//      PassRegistration 写进同一张全局注册表，命令行解析器
//      不区分"一个 Pass"和"一条管道"——上游 -O2 就是这么拼的。
//   3. 管道是复盘的锚点。Day 49 复盘要回答"两种 Pattern 为什么
//      要连续执行"，答案的实验载体就是这条管道。
//
// 机制上只有一个新面孔：PassPipelineRegistration<>。它注册的不是
// "构造一个 Pass 的函数"，而是"往 OpPassManager 里装若干 Pass 的
// 函数"。装进去的每个 Pass 仍按顺序各跑各的——管道不做任何调度
// 魔法，这一点对读代码的人是好消息：行为 = 名字展开后的命令行。
//
//===----------------------------------------------------------------------===//

#include "mini/Passes.h"

#include "mlir/Pass/PassManager.h"
#include "mlir/Pass/PassRegistry.h"
#include "mlir/Transforms/Passes.h"

using namespace mlir;

namespace mlir {
namespace mini {

void registerCombinedOptPipeline() {
  // 第三个模板参数是"管道构造器"：拿到 OpPassManager，按顺序装 Pass。
  // 这里装的每个 Pass 都已各自注册过（ShapeInferencePass 本地构造、
  // Canonicalizer 是上游 createCanonicalizerPass 的产物）——注册表
  // 允许管道引用不在命令行上单独出现的实现。
  //
  // 顺序就是 Day 46 实验证明的正确顺序：先推导，再规范化。
  // 为什么 canonicalize 只出现一次？因为它的驱动内部自带迭代
  // （贪婪工作表跑到不动点，见教程 §4）：fold 出的新常量、被拆掉的
  // 算子，都会在同一趟里被重新处理。需要跨 Pass 多轮的场景
  // （canonicalize 在前、infer-shape 在后）教程 §5.4 用命令行
  // 手动补第二轮做对照实验，不藏进管道里。
  PassPipelineRegistration<>(
      "mini-combined",
      "Run mini shape inference followed by canonicalization "
      "(the Day-46-verified order)",
      [](OpPassManager &pm) {
        pm.addPass(createShapeInferencePass());
        pm.addPass(createCanonicalizerPass());
      });
}

} // namespace mini
} // namespace mlir
