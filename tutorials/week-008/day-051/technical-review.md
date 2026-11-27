# 第 51 天技术校对报告

审阅对象：`tutorials/week-008/day-051/`（README、`code/` 全部源码与输入、4 张 SVG）。
审阅环境与 README 声明一致：Linux aarch64、g++ 9.4.0、Ubuntu LLVM/MLIR 18.1.8（`mlir-opt`、`mlir-tblgen` 实测可用）、Python 3.11.4、numpy 1.26.4。
核实手段：`mini_fuse.py`、`test_fusion.py` 实际运行；`code/mlir-mini` 在临时目录独立 cmake/ninja 构建（产物 6,828,960 字节 ≈ 6.8 MB，与 README 一致）并复跑 §5.2/§5.3/§5.4 全部命令；`--broken=no-guard` 在 gdb 下取崩溃回溯；`--broken=erase-order` 复跑确认 exit=0；linalg 对照命令复跑；TableGen `GET_OP_CLASSES` 踩坑用删掉 `#define` 的副本复现。以下引用均可逐字在 README 中定位。

## 【错误】
#### 1. 实验 C 的崩溃发生在贪心驱动的 fold 阶段，不是「最后打印模块时」
- **原文**：“等到最后打印模块时，读取 `return` 的操作数触发 `SIGSEGV`（信号 11，退出码 139）。**真正的错误在 Pattern 里，崩溃却在打印处**”
- **依据**：在本机完全一致的环境（MLIR 18.1.8、g++ 9.4.0、Release、同一份仓库源码、同一命令 `stdbuf -o0 ./build/mini-fuse inputs/multi_user_add.mlir --broken=no-guard`）下 5 次运行均稳定 exit=139，gdb 回溯为 `mlir::applyPatternsAndFoldGreedily` → `GreedyPatternRewriteDriver::processWorklist` → `mlir::Operation::fold` → `mlir::Value::getDefiningOp()`：即 Pattern 返回 success 之后、贪心驱动对工作队列剩余算子做折叠时读取悬空操作数，发生在 `verify()` 与「融合后」打印之前。「读悬空操作数触发 SIGSEGV、错误在 Pattern 崩溃在别处」的机制性描述本身成立，错的是发生阶段（打印处 → 驱动器 fold 处）。同一错误还出现在：§6 错误 2「崩溃点在打印/校验阶段（§5.4 实验 C）」、§9「打印时段错误」、图 3 右列文字「在打印融合后 IR 时读到悬空值」（图 3 未改动，仅在此记录）。
- **置信度**：高。gdb 直接回溯、逐次可复现；不确定点：其他 MLIR 版本或驱动配置下崩溃点可能落在不同阶段，但在本教程声明的环境内结论确定。

## 【存疑】
#### 1. 「打开断言的调试构建就可能当场崩溃」在发行版 MLIR 环境下无法按字面复现
- **原文**：“同一份代码换个输入、换个构建（比如打开断言的调试构建）就可能当场崩溃。”
- **依据**：`/usr/lib/llvm-18/include/mlir/IR/PatternMatch.h` 中 `eraseOp` 的声明注释为 “This method erases an operation that is known to have no uses”，「无使用者才可擦除」是文档化契约，从源码 Debug 构建的 MLIR 应有断言拦截；但本环境的 `libMLIRIR` 等库为 Release（NDEBUG）构建，`strings` 检索无断言文本，而学习者只把自己的工程切成 Debug（`-DCMAKE_BUILD_TYPE=Debug`）不会让预编译库内的断言生效，需从源码重新构建带断言的 MLIR 才可能触发。教程未说明这一差别，初学者按字面操作大概率复现不了「当场崩溃」，只能得到与 Release 相同的「表面正常」。
- **置信度**：中。契约存在有据（头文件注释）；「Debug 构建 MLIR 必然触发断言」未能直接验证（本机无 MLIR 源码构建条件）。

## 【建议】
#### 1. `add_relu_linalg.mlir` 的内容描述漏掉了 `%zero` 常量定义行
- **原文**：“输入文件 `inputs/add_relu_linalg.mlir` 的内容就是 `%t = arith.addf %a, %b` 与 `%r = arith.maximumf %t, %zero` 两行加上返回。”
- **依据**：该文件实际是三行算子加返回，还包含 `%zero = arith.constant dense<0.0> : tensor<2x2xf32>`（已 cat 核实）。读者按「两行加上返回」自行构造输入会因 `%zero` 未定义而解析失败，与「跟着操作」的教程定位冲突。
- **置信度**：高。

#### 2. linalg 对照的「真实输出」实为节选，且 `#map` 定义未随摘录给出
- **原文**：“真实输出（已保留原样）：”
- **依据**：所示片段逐字符比对确为真实输出的原样摘录，但省略了 `#map = affine_map<(d0, d1) -> (d0, d1)>` 定义、`module`/`func.func` 外壳、`%cst` 常量、`%0 = tensor.empty()` 与 `return` 等行；片段里的 `#map` 引用离开定义行无法独立解读，读者也容易误以为这就是完整输出。建议标注「节选」或至少补上 `#map` 定义行。
- **置信度**：高。

#### 3. 「180 行」与实际文件行数不符
- **原文**：“├── mini_fuse.py             ← 热身：迷你图 IR + Rewriter + 融合 Pattern（180 行）”
- **依据**：`wc -l` 实测 `mini_fuse.py` 共 207 行（非空行 159 行），`mini_fuse.py` 文件头的 docstring 也写「~180 行」。不影响正确性，但既然给出具体数字，建议改成 207 或「约 200 行」；§5 标题「从 180 行 Python 到真实 MLIR」同理。
- **置信度**：高。

#### 4. 图 4 图注把两种错误写法统称为「真实崩溃」，与正文对实验 D 的描述不一致
- **原文**：“§6 的两个真实崩溃，全都来自违反这张小抄。”
- **依据**：按正文与实测，只有实验 C（`--broken=no-guard`）真的崩溃（exit=139）；实验 D（`--broken=erase-order`）是「输出看起来正确、`exit=0`」的静默 UB（已复跑核实），并不崩溃。把它也称作「真实崩溃」与 §5.4 自己的表述矛盾，建议改为「两种错误写法」之类；从内容看实验 C 违反小抄第 3 条（未改接完 `%t` 的全部使用者就 `eraseOp`）、实验 D 违反第 4 条，「全都来自违反小抄」的归因本身可以成立。
- **置信度**：高。

## 复核记录（供后续修订参考）

- `python3 mini_fuse.py`、`python3 test_fusion.py` 输出与 README §5.1 逐字一致（含 RuntimeError 消息文本）。
- `./build/mini-fuse` 对 `add_relu.mlir`、`shared_result.mlir`、`multi_user_add.mlir` 的输出与 README §5.2/§5.3 逐字一致；`--broken=no-guard` exit=139、`--broken=erase-order` exit=0 均复现。
- `mlir-opt --convert-elementwise-to-linalg` 先产出 2 个独立 `linalg.generic`，加 `--linalg-fuse-elementwise-ops` 后合并为 1 个，README §5.4 的「两个合并成一个」属实；摘录片段与真实输出逐字一致。
- 交叉引用核对：第 10、17、36～42、43～44、45～48、50、52、57、71～72、136 天的主题与总计划及已发布教程相符；§3.1「第 45 天的 Pattern 以单个算子为根」与 day-045 的 `OpRewritePattern<mini::ReluOp>` 相符。
- `GET_OP_CLASSES` 踩坑复现：去掉 `#define` 后确实在 `mini-fuse.cpp:30` 报 `'ReluOp' is not a member of 'mini'`（同时 `MiniDialect.cpp` 报生成代码内部错误），README §6 错误 3 的现象描述属实；`build/gen/MiniOps.h.inc` 第 23 行可见 `#ifdef GET_OP_CLASSES`。
- 第 7 节练习用自构造 `chain.mlir` 实测：两处 `Add+Relu` 链均融合为两个 `mini.fused_add_relu`，与练习预期一致。
- 未能验证项：MLIR 18 `Operation::erase()` 断言在 Debug 构建下的具体行为（见【存疑】1）；`applyPatternsAndFoldGreedily` 折叠路径中被折叠的具体算子（回溯停在 `Operation::fold` 内，不影响「崩溃不在打印处」的结论）。
