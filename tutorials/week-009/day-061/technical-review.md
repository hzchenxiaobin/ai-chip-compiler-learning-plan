# 第 61 天技术校对报告

校对环境：本机 Python 3.11.4 / numpy 1.26.4 / Ubuntu LLVM 18.1.8（`/usr/lib/llvm-18/bin/mlir-opt`、`mlir-cpu-runner`，Linux aarch64），与 README 声明一致。以下全部结论均在本机复跑核实：`dynamic_lab.py` 16/16、`test_dynamic.py` 41/41、fuzz 500 组 `ok=129 · shape_error=371`、`matmul_dynamic` cpu-runner 220/280/490/640、`k_hazard` 越界输出与 exit=0、`k_check` 220＋消息＋abort=134、`--canonicalize` 静态折叠/动态保留、`--convert-shape-constraints` 物化 `cf.assert`、bad_dynamic 三房间 exit 码、练习 4 与选做挑战的预测、B(5,2) 无声正确变体、`np.broadcast_shapes((2,3),(-1,))` 报错文案，全部与 README 及 `code/outputs/` 冻结产物一致。以下仅列出与事实不符或可改进之处。

## 【错误】

#### 1. 「类型里出现 `?` 后推断返回『全未知』、静态失配跟着跳过」不是 Verifier 的真实机制，属于过度推广
- **原文**：“Verifier 的形状推断是全有或全无——类型里出现 `?` 后推断返回「全未知」，静态可见的 4 vs 3 也跟着跳过。”
- **依据**：真实机制在 LLVM 18.1.8 `mlir/lib/Dialect/Linalg/IR/LinalgInterfaces.cpp` 的 `verifyStructuredOpInvariants`：先算 `getStaticLoopRanges()`，仅当所有循环上界都静态（`if (llvm::none_of(endLoopRangeValues, ShapedType::isDynamic))`）才进入逐维比较（源码注释："Verify only static cases since we can't get exact dimension sizes and loop ranges for dynamic cases in this stage"）；进入比较后每一维单独处理——`if (ShapedType::isDynamic(shape[dim]) || shape[dim] == 0) continue;` 只跳过为 `?` 的那一维，其余静态维（含输出侧）照常比对。同机 mlir-opt 反例（逐条实测）：① `memref<2x4xf32> × memref<3x2xf32> → outs memref<?x2xf32>` 类型里有 `?`（输出的 M），却 exit=1 报 `operand #1 has shape's dimension #0 to be 4, but found 3`——静态 4 vs 3 仍被查出；② `memref<2x3xf32> × memref<3x2xf32> → outs memref<?x4xf32>` exit=1 报 `operand #2 has shape's dimension #1 to be 2, but found 4`；③ `memref<?x4xf32> × memref<3x2xf32> → outs memref<2x2xf32>`（输出全静态）exit=0——A 的第 0 维 `?` 使 M 循环上界无法静态解出，整条检查才被跳过。即「失明」的条件是「循环上界无法全部静态解出」（对 matmul 即喂给循环上界的 A 第 0 维、A 第 1 维、B 第 1 维是 `?`），不是「类型里出现 `?`」。README 房间 2/房间 3 的实测本身可复现（A 的 M=`?` 恰好命中跳过条件），错在被当作通用因果规律教给读者的这句话。另请一并核对 §1「一个 `?` 让整张静态检查网失明」与图 2/图 3 中的同类概括。
- **置信度**：高——反例在同版本 mlir-opt 上逐条复现；错误消息出处已定位到源码文件（`libMLIRLinalgDialect.a` → `LinalgInterfaces.cpp`）。

#### 2. §5.3 结论 1 重申了同一过度推广，且「什么都推不出」的说法与源码行为不符
- **原文**：“静态检查是全有或全无的：类型里混进一个 `?`，整套推断就退化为「什么都推不出」，连本来能查的也不查了。”
- **依据**：同第 1 条的反例 ①②：类型里混进 `?` 后静态失配仍可能被查出（输出的 M 写成 `?` 时 K 失配、输出 N 失配都会被拦），「混进一个 `?` 就连本来能查的也不查」不成立。跳过整条检查的触发条件是循环上界含动态维，而非类型里出现 `?`；且源码行为是「跳过这段验证」，不存在「推断退化为什么都推不出」的过程。「全有或全无」若限定在「循环上界层面」（上界全静态才运行整段检查）则是准确的，建议按此口径改写。
- **置信度**：高——同第 1 条，反例与源码均核实。

#### 3. §9 开头把 bad_dynamic 房间 3（4 vs 3）与 k_hazard 的 cpu-runner 垃圾值拼接成了同一件事
- **原文**：“今天的问题始于「`memref<?x4xf32>` 乘 `memref<3x2xf32>`，4 和 3 都写在类型里却无人拦截，cpu-runner 静默吐出 `1.44752e+28`」。”
- **依据**：`memref<?x4xf32> × memref<3x2xf32>`（bad_dynamic 房间 3）只做过 mlir-opt 验证（`outputs/bad_dynamic_room_room3_static_m_dynamic.txt`，exit=0 放行），run_all.sh 第 8 步仅调 mlir-opt，从未用 cpu-runner 执行过该房型；`1.44752e+28` 出自 `outputs/k_hazard_exec.txt`，其输入是 k_hazard.mlir 的 A(2,3) 配 B(2,2)（K 3 vs 2、两侧都 cast 成 `memref<?x?xf32>`），失配数字与房型都不同。§1 的原始叙述（「再往下追（mlir-cpu-runner 真实执行，k_hazard.mlir）：给全动态的 MatMul 喂 A(2,3) × B(2,2)」）是对的，§9 的压缩把两个独立实验的对应关系写错了。
- **置信度**：高——依据为仓库冻结产物与 run_all.sh 流程本身，无需外部资料。

## 【存疑】

- 无。

## 【建议】

#### 4. §2 第 3 点把「折没」与「物化成 cf.assert」压进同一句，容易让读者以为都是 `--canonicalize` 干的
- **原文**：“MLIR 用 shape dialect 的 witness（`shape.cstr_require` + `shape.assuming`）表达同一件事，静态时整条链被 `--canonicalize` 折没，动态时物化成 `cf.assert`。”
- **依据**：`--canonicalize` 只做折叠化简、不会引入 `cf.assert`；把 `cstr_require` 变成 `cf.assert` 的是 `--convert-shape-constraints`（§5.4 与 `outputs/k_constraint_cstr.mlir` 的展示是准确的）。实测复核：`mlir-opt --canonicalize k_constraint.mlir` 的输出里没有任何 `cf.assert`。建议在 §2 这句给第二个分句补上 pass 名，与 5.4 节口径对齐。
- **置信度**：高。

#### 5. 「静态维（3、1）编译进代码当常数」只对循环上界成立，描述符 ABI 里静态 sizes/strides 仍是运行期字段
- **原文**：“静态维（3、1）编译进代码当常数；`?` 的值随参数传入，`memref.dim` 是唯一取值通道。”
- **依据**：`outputs/matmul_dynamic.lowered.mlir` 里 `@matmul_m_dynamic` 的 ABI 是 21 个标量（三个 memref 各 7 个：allocated ptr、aligned ptr、offset、sizes[2]、strides[2]），其中 `%arg3..%arg6` 正是 `memref<?x3xf32>` 的 sizes[0]/sizes[1]/strides[0]/strides[1]——静态的 sizes[1]=3 与 strides(3,1) 同样作为运行期参数传递。「编译进代码当常数」只对循环上界（`%c2`/`%c3`，见 `matmul_dynamic_loops.mlir`）成立；图 2 的「静态维（3、1）在类型里，编译进代码」也建议补上这层区分，避免读者以为描述符会省略静态维。
- **置信度**：高——直接来自降级 IR 实测。

#### 6. k_hazard 的具体垃圾值是堆布局相关的未定义行为结果，可加一句跨环境提示
- **原文**：“k_hazard 实测输出 `1.44752e+28 / 100 / 2.89504e+28 / 280`、exit=0”
- **依据**：越界读 B[2,j] 读到的是分配器残留（本机 B[2][0]≈4.82507e+27、B[2][1] 恰为 0，`100`/`280` 与 `e+28` 的算术能对上），换机器或换分配顺序数值会变；本机复跑数值稳定，但初学者在别的环境看到不同垃圾值时可能误以为自己做错了。建议加一句「具体数值因环境而异，稳定的信号是 exit=0＋非确定垃圾值」。
- **置信度**：高（UB 数值不保证跨环境一致是定性结论；本机两次运行数值相同，故仅建议加提示而非改动现有实测记录）。

#### 7. 「MLIR 只有在 M 也静态时才拦」是必要条件，可补一句精确前提
- **原文**：“而 MLIR 只有在 M 也静态时才拦（房间 3 的失明现场）。”
- **依据**：实测 `memref<2x?xf32> × memref<3x2xf32> → outs memref<2x2xf32>`（M 静态、A 的 K=`?`）同样 exit=0 放行——K 循环上界从 A 读，A 的 K=`?` 也令整段检查跳过。「M 静态」是拦截的必要条件而非充分条件（还需 A 的 K、B 的 N 等喂循环上界的维都静态）；与第 1、2 条一起改成「循环上界全部静态可解时才运行逐维检查」的口径更完整。
- **置信度**：高——探针用例在同机实测。
