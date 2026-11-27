# 第 42 天技术校对报告

校对方法：在本机（Ubuntu 20.04 · LLVM/MLIR 18.1.8 · cmake 3.20.5 + Ninja，与教程环境一致）完整重建 `code/mini`，重放全部 11 个探针、`run_all.sh` 第 6/7 步的 trait 对照实验，并针对存疑论断补做了隔离实验（见各条依据）；生成代码、MLIR 18.1.8 头文件与静态库反汇编均逐一核对。除下述条目外，教程中的目标数值手算（`[[0,32],[276,0]]` 等）、11 个探针的退出码与报错原文、`diff -rq` 输出、生成代码 `MiniOps.cpp.inc` 第 889 行起的 `verifyInvariants` 引文、第 6 节四个错误场景的报错原文（`Found erroneous configuration for source file MulVerifier.cpp`、`undefined reference to 'mini::MulOp::verify()'`、`custom op 'mini.multiply' is unknown`、`no declaration matches 'mlir::LogicalResult mini::MulOp::verify()'`）、CSE 与 `-mini-count-ops` 输出均复现无误。

## 【错误】

#### 1. trait 版误拒报错的发出时机不是"建 op 时"（解析期），而是 IR 验证期
- **原文**："- **报错来源的细节**：trait 版误拒的报错不是来自 `verifyInvariants`，而是"建 op 时"的类型推断检查——`SameOperandsAndResultType` 还顺手提供了 `InferTypeOpInterface`（这就是需要补 include 的原因），解析器建 op 时先做了一轮推断比对。这印证了 3.2 节说的 trait 双重角色：它不只是检查，还是机器可读的接口声明。"
- **依据**：本机隔离实验证明该诊断在整份文件解析完成之后的 IR 验证阶段才发出。(1) 构造探针：第 2 行放一个只可能在验证期失败的 `mini.relu`（f64 操作数触发 ODS 类型约束错误），第 3 行放误拒同款 `mini.mul`（`?x3 * 2x3 -> 2x3`），喂给 trait 版 mini-opt。若推断比对发生在"解析器建 op 时"，解析会在第 3 行中止并只报 mul 的 `inferred type(s)...` 错误；实测输出只有 relu 的验证期错误（"'mini.mul' op operand #0 must be..." 同源的 `'mini.relu' op operand #0 must be ranked f32 tensor of 32-bit float values, but got 'tensor<2x2xf64>'`），mul 的推断错误根本没出现——说明解析成功、检查在验证阶段。(2) 生成代码证据：trait 版 `MiniOps.cpp.inc` 的 `MulOp::parse()` 解析出显式结果类型后直接 `result.addTypes(resTypes)`，不含任何 `inferReturnTypes`/`refineReturnTypes` 调用；推断比对只出现在省略结果类型的 `build()` 重载里，而教程全部 .mlir 文件都显式写了 `-> type`，解析路径不会走到。(3) 18.1.8 头文件证据：`mlir/Interfaces/InferTypeOpInterface.td` 中该 Trait 的检查挂为 `verifyWithRegions`（生成 `verifyRegionTrait` → `detail::verifyInferredResultTypes`），由 `mlir/IR/OpDefinition.h` 的 `VerifyRegionInvariantsFn` 钩子（`verifyRegionInvariants` → `verifyRegionTraits`）在验证期调用，与 `verifyInvariants` 是两个不同钩子——所以"不是来自 verifyInvariants"这半句是对的，但"建 op 时／解析器建 op 时先做了一轮推断比对"这半句错误。图 3 底部提问卡里同款表述（"解析建 op 时就比上了"）应一并更正为"验证期（region invariants 钩子）"。另有半句"还顺手提供了 InferTypeOpInterface"属实：生成类声明确含 `::mlir::InferTypeOpInterface::Trait` 且 tblgen 生成了 `MulOp::inferReturnTypes`（已核对 .h.inc/.cpp.inc）。
- **置信度**：高。钩子名 `verifyRegionInvariants` 来自安装版 18.1.8 头文件并经行为实验反推；未直接读 Verifier.cpp 源码（发行包不含），但错误顺序实验与生成 parse() 代码两项证据已足以排除"解析期检查"。

#### 2. "trait 只认三个类型字面相等"——SameOperandsAndResultType 自身的检查并非字面相等，字面相等来自其附带的 InferTypeOpInterface 的结果类型比对
- **原文**："- **误拒**：trait 只认三个类型**字面**相等，合法的细化 IR（`?x3 * 2x3 → 2x3`）被拒；verifier 版逐维保守判定，M 一边 `?` 一边 2 视为"无法反驳"，放行。"
- **依据**：实验直接证伪"三个类型字面相等"：把探针换成 `2x3 * ?x3 -> 2x3`（三个类型为 2x3、?x3、2x3，并不字面相等）喂给 trait 版 mini-opt，rc=0 通过。机制上，MLIR 18.1.8 的 `OpTrait::impl::verifySameOperandsAndResultType`（libMLIRIR.a 反汇编可见其调用 `mlir::verifyCompatibleShape(Type, Type)`）按维做"兼容"比较、动态维 `?` 与任何静态维视为兼容——即 trait 自身检查对 `?` 同样是"无法判定就放行"，并不比手写裁判更严格。`?x3 * 2x3 -> 2x3` 被拒的真正闸门是该 trait 附带的 `InferTypeOpInterface`：生成的 `MulOp::inferReturnTypes` 把 `operands[0]` 的类型当作推断结果，验证期用 `isCompatibleReturnTypes`（默认实现 `lhs == rhs`，见 InferTypeOpInterface.td 第 105～118 行的 defaultImplementation）与写出的结果类型做字面比对，`?x3` 对 `2x3` 不等才报 `inferred type(s)...incompatible`。准确说法是"结果类型必须与第一个操作数的类型字面相等"，而非"三个类型字面相等"；这也解释了一个正文未提的现象——动态维在第二个操作数上时 trait 版照样放行。3.2 节 ④ 的"（trait 只认字面相等 → Verifier 逐维保守判定）"（README 第 58 行）为同款表述，应一并修正。误拒现象本身与 5.4 引用的两条报错原文均属实（本机复现一致）。
- **置信度**：高。`verifyCompatibleShape` 的"动态维兼容"语义由反汇编调用关系与 `2x3 * ?x3 -> 2x3` 通过的实验共同支撑；该函数逐维实现的 .cpp 源码不在本机安装范围内，但行为结论有实验直接证明。

## 【存疑】

#### 1. "该放 Verifier 的写成 ODS 则根本表达不出来"——过于绝对，且与本教程 5.4 的实验存在张力
- **原文**："- 类比边界：安检类比解释不了**执行顺序的含义**——技术上两层不是平行关卡而是串联接力（生成代码里 `verifyInvariantsImpl() && verify()`），ODS 全过才轮到 `verify()`；这让 `verify()` 里可以放心 `cast<RankedTensorType>`，也意味着"该放 ODS 的约束写成 Verifier"只是浪费一层检查，反过来"该放 Verifier 的写成 ODS"则根本表达不出来。"
- **依据**："shape 一致"这类跨值约束恰恰可以用 ODS 表达——`SameOperandsAndResultType`、`SameOperandsAndResultShape`、`AllTypesMatch` 等 trait 正是为此存在的，且本教程 5.4 的对照实验本身就是"把 shape 规则写成 ODS trait"并成功编译、运行、给出诊断（本机复现一致）。ODS 真正表达不出来的是：分档诊断（区分"永久不匹配"与"差一个广播"）和逐维的动态维政策。若按"诊断质量与政策写不进 ODS"的狭义理解，该句成立；按字面"约束根本表达不出来"理解则错误，且与 5.4 自身的 trait 版实验冲突。建议收窄为"约束本身可以表达，但分级诊断和 `?` 的逐维政策表达不了"。
- **置信度**：中。两种读法在原文中都通顺，无法确定作者本意，故列存疑而非错误。

## 【建议】

#### 1. "+38 行／约 89 行"的行数口径与 diff 实测数不一致
- **原文**："今天交付后的真实改动半径（`diff -rq` 实测，见 5.3 节）：**改 2 个文件 + 新建 1 个文件**——`MiniOps.td`（+38 行）、`lib/MulVerifier.cpp`（新建 50 行）、`lib/CMakeLists.txt`（+1 行）。`MiniOpt.cpp`、`MiniDialect.cpp`、`Ops.h`、`Dialect.h`、`Passes.h`、`CountOpsPass.cpp` 全部原样。Day 41 在 `MiniOpt.cpp` 里留的那句注释——"第 42 天复盘新增 mini.mul 时也不会再碰这个文件"——今天兑现了。"
- **依据**：`diff day-041/.../MiniOps.td day-042/.../MiniOps.td` 实测新增 49 行、删除 0 行：其中 39 行是 mini.mul 段落（含 3 行 banner 注释与 1 行空行），另 9 行是文件头的"第 42 天"注释块。"+38"恰好只数了 mul 段落且不含空行；按 raw diff 口径 MiniOps.td 应为 +49，三个文件合计约 100 行，与"约 89 行"（第 6 行、第 343 行同口径）相差约一成。结论（改动半径极小）不受影响，但该句紧挨着"diff -rq 实测"，建议注明计数口径（如"mul 定义段 38 行，另有 9 行文件头注释"）或直接改用 diff 的实际计数。
- **置信度**：高（计数客观可复现）。

#### 2. "CSE 靠 Pure trait 判断能否合并"可再精确一步；"trait 既是一条检查"对 Pure 本身不成立
- **原文**："- 类比边界：餐厅类比解释不了**Pass 为什么也不用作改动**——技术上 Pass（如 CSE）判断"能不能合并"靠的是 op 的 `Pure` trait（无副作用标记），而不是维护一张算子白名单；trait 是挂在 Operation 上、随时可查询的**元数据**，这是 3.2 节的关键角色。"
- **依据**：18.1.8 中 `def Pure : TraitList<[AlwaysSpeculatable, NoMemoryEffect]>`（mlir/Interfaces/SideEffectInterfaces.td 第 146 行）——Pure 是 ODS 侧的打包名，落到生成代码是 `MemoryEffectOpInterface::Trait`（无内存副作用）加 `AlwaysSpeculatable`；libMLIRTransforms.a 中 CSE.cpp.o 实际调用的判据是 `mlir::isMemoryEffectFree(Operation*)` 等 MemoryEffectOpInterface 查询，并不存在对"Pure"这个名字的查询。3.2 节"trait 既是一条**检查**（生成代码会查）"对 Pure 也不成立——Pure 不生成任何验证代码，"检查"的一半只对 `SameOperandsAndResultType` 这类约束 trait 成立。教程的简化方向没错，教学场景可接受；若想让"trait 是给 Pass 看的元数据"经得起追问，可补一句"Pure 在 C++ 侧展开为 NoMemoryEffect 等接口实现，Pass 查询的是接口"。
- **置信度**：高。

#### 3. "不重编译就数出了 mini.mul=1"按字面读不通
- **原文**："三个细节：CSE 把重复的 `mini.mul` 合并后，两个 `mini.add` 因为输入变得相同也被顺带合并了（输出只剩一个 return 值被用了两遍）；`-mini-count-ops`（Day 41 写的 Pass）不重编译就数出了 `mini.mul=1`；两个 Pass 判断的依据分别是 **操作数/属性相同** 和 **遍历 Operation**——没有任何一方维护算子名单。`mini.mul=1` 里那个"1"，就是 `Pure` trait 和注册表架构合作的结果。"
- **依据**：`cmake --build` 会把 `CountOpsPass.cpp` 连同整个 MLIRMini 一起重新编译进新的 mini-opt（本机干净构建日志可证）；想表达的事实是"Pass 源码一行未改"。建议改为"没改一行 Pass 代码就数出了"，避免初学者误以为新增算子后无需重新构建。
- **置信度**：高。
