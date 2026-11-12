# 第 034 天：跑通 Standalone 示例——一个 op 从 .td 声明走到命令行

> **今日目标**：完成本教程后，你能对 Standalone 工程里的任一文件说出它属于哪一层（`.td` 声明／`.inc` 生成／手写胶水／工具与测试）；能用 `cmake`＋`ninja` 独立构建出 `standalone-opt`，并解释构建日志**前 7 步为什么全是 `.inc`**；能用 `--show-dialects`、round-trip、两个报错探针验证"方言已注册、Verifier 在岗"；能用**两种写法**（直连旗标 `--standalone-switch-bar-foo` 与 `--pass-pipeline`）运行 Pass，并用官方 lit 测试确认 5 通过；能按"改代码 → 重编译 → 观察三处变化 → 测试先红后绿 → 还原"的闭环修改一个输出文本（`foo`→`qux`）并预测每一步结果。
> **预计时间**：学习 25 分钟 ＋ 实践 50 分钟
> **前置准备**：Day 29 的 MLIR 环境（`mlir-18-tools`、`libmlir-18-dev`、`llvm-18-dev`，版本 18.1.8，外加 `cmake`、`ninja`、`lit 18.1.8`）；Day 30 的 Operation 五件套（名字／操作数／结果／Region／属性）；Day 33 的 Dialect 概念（户口本：op 名、Type、Attribute 都登记在方言名下）。
> **今日产出**：`code/` 下一个可构建的 Standalone 示例工程（保持上游原状）＋ 4 个实验 `.mlir` 文件（round-trip 正例、主例子、两个报错探针）＋ `run_all.sh`（一键重放全部 8 组实验），以及它们在本机的真实运行记录；外加三张图：图 1 定位、图 2 讲透"op 诞生与上岗"机制、图 3 展示修改闭环全程。

## 1. 今天解决什么问题？

Day 33 结尾留了一句话："明天 Day 34 的工程会看到一个方言的全套家当。"今天还这个债。前三周我们一直在**用**别人定义的方言（`arith`、`func`、`linalg`），今天第一次从零拆一台**造方言的机器**——MLIR 官方的 out-of-tree（源码树外）示例工程 [Standalone](https://github.com/llvm/llvm-project/tree/main/mlir/examples/standalone)。计划今天要求三件事：**跟踪 Operation 定义、构建和 Pass 注册过程**；**运行示例，修改一个输出文本或简单属性并重新验证**；**产出可构建的示例工程和源码阅读笔记**。

具体拆成三个问题：

1. **定义一个 op 到底要写多少代码？** 答案少得惊人：3 份 `.td`（TableGen 声明）＋ 3 份手写 C++（胶水）。解析器、打印机、Verifier——Day 30～33 反复出现的这些机制，**没有一行需要手写**。
2. **工具是怎么"认识" `standalone.foo` 的？** 昨天说没户口的名字在解析层就被拒收；今天看户口是怎么登记进去的——而且有**两条路**：编进自己的工具，或者编译成插件塞给系统 `mlir-opt-18`。
3. **改一行代码，哪些东西会跟着变？** 把 Pass 里的 `"foo"` 改成 `"qux"`，IR 输出、`--help` 说明、lit 测试的 CHECK 行——三处连锁反应，这是"修改并重新验证"的最小完整闭环。

贯穿全文的例子只有一对：算子 **`standalone.foo`**（一个 `i32 → i32`、无副作用的"什么都不做"算子）和 Pass **`standalone-switch-bar-foo`**（把模块里名为 `@bar` 的函数改名为 `@foo`）。输入固定是 `code/bar_to_foo.mlir`：

```mlir
module {
  func.func @bar() {
    return
  }
  func.func @other(%arg0: i32) -> i32 {
    %0 = standalone.foo %arg0 : i32
    return %0 : i32
  }
}
```

跑一遍 Pass，`@bar` 变 `@foo`，`@other` 原样不动——今天所有实验都围绕这条三行的改动展开。

**术语先对齐**：**TableGen（.td）**是 LLVM 的描述语言，只声明"是什么"不写"怎么做"；**mlir-tblgen**是把 `.td` 编译成 C++ 的生成器；**.inc 文件**是生成产物（构建时出现在构建目录里）；**out-of-tree**指在 LLVM 源码树之外开发（你将来的 `mini` 就是）；**round-trip**指"解析 → 打印"原样往返；**Verifier**是 op 合法性的最后关卡；**lit**是 LLVM 的测试执行器，**FileCheck**是它的断言工具（`CHECK:` 行逐行核对输出）。

## 2. 先看全貌：今天的内容位于哪里？

![第 34 天全局定位图：顶部第 5 周路线条（Day 32 Type/Attribute、Day 33 Dialect 与渐进 Lowering、今天 Day 34 跑通 Standalone 示例高亮、Day 35 复盘、Day 36 创建 mini Dialect）；左侧五步主线列表（读源码、构建工程、运行验证、修改 Pass、重新验证）与今日产出卡；右下运行环境卡（Ubuntu 20.04 arm64、MLIR 18.1.8、run_all.sh 一键重放）；底部编译器链路条（源码 .td+.cpp → TableGen→C++→工具 → opt 工具 → 输入 .mlir → Pass Pipeline → 输出 .mlir），今天管中间"生成·构建·注册"一格](images/01-overview.svg)

**图 1**：先看顶部路线条——昨天给 Type／Attribute 上完户口，今天（高亮格）把整本户口本变成能敲的命令；Day 36 起你自己的 `mini` Dialect 走的就是今天这条流水线。再看左侧五步主线，它同时就是本篇目录：① 读源码（§3）→ ② 构建工程（§5.2）→ ③ 运行验证（§5.3）→ ④ 修改 Pass（§5.4）→ ⑤ 重新验证（§5.4）。底部链路条标出了今天管的格子：**从 `.td` 源码到能跑 Pass 的工具**，输入输出两端的 `.mlir` 反而是配角。

全局五步，每步都有可验证的产出：

1. **读**：3 份 `.td` ＋ 3 份手写 C++，分清"声明"和"胶水"（§3）；
2. **建**：`cmake`＋`ninja` 构建出 `standalone-opt`，构建日志前 7 步全是生成 `.inc`（§5.2）；
3. **跑**：`--show-dialects` 看注册表、round-trip 验算子、两个探针看两道报错关卡、两种写法跑 Pass、lit 跑官方测试、插件喂给系统工具（§5.3）；
4. **改**：Pass 里 `"foo"`→`"qux"`，重编译（§5.4）；
5. **验**：三处连锁变化 ＋ 测试先红后绿 ＋ 还原上游原状（§5.4）。

## 3. 核心概念：先用直觉，再给准确定义

### 3.1 TableGen 声明：只写"是什么"

一句通俗解释：`.td` 文件是一张**菜谱**——写清菜名、用料、忌口，但不写炒菜动作。

- **一个类比**：米其林中央厨房。菜谱（`.td`）只描述"这道菜有 `i32` 输入、`i32` 输出、不含麸质（无副作用）"；中央厨房（`mlir-tblgen`）照菜谱批量预制半成品（`.inc`）；门店厨师（手写 C++）只做菜谱覆盖不了的收尾——摆盘、开店、挂招牌。**对应到技术上是**：TableGen 是 LLVM 的领域特定语言，MLIR 用它**结构化地**描述 op 的名字、操作数／结果类型约束、trait（如 `Pure`）、通用语法格式；`mlir-tblgen` 在**构建期**把声明展开成上千行 C++。**类比的边界**：菜谱换一家厨房照样用，`.td` 却和 MLIR 版本强耦合——生成器一升级，`.inc` 的形态可能整个变样，所以 `.inc` 从不进版本库、每次构建现生成（它们长在构建目录里，上游工程 `.gitignore` 排除的正是 `build/`）。
- **一个最小例子**：整个方言只有三个 `.td`，职责各管一层：

```tablegen
// StandaloneDialect.td —— 方言户口本的封面：姓什么、住哪
def Standalone_Dialect : Dialect {
    let name = "standalone";                    // op 名字里的姓：standalone.foo
    let cppNamespace = "::mlir::standalone";    // 生成的 C++ 住哪个命名空间
    ...
}
class Standalone_Op<string mnemonic, list<Trait> traits = []> :
        Op<Standalone_Dialect, mnemonic, traits>;   // 全方言 op 的共同基类
```

```tablegen
// StandaloneOps.td —— 今天的主角 foo，声明只有这几行
include "mlir/Interfaces/InferTypeOpInterface.td"
include "mlir/Interfaces/SideEffectInterfaces.td"

def Standalone_FooOp : Standalone_Op<"foo", [Pure,
                                             SameOperandsAndResultType]> {
    let summary = "Illustrates how to define an operation.";
    let arguments = (ins I32:$input);          // 操作数：signless 32 位整数（不区分符号，区别于 si32/ui32）
    let results = (outs I32:$res);              // 结果：同样是 i32
    let assemblyFormat = [{                     // 书写格式：谁教解析器认识这行字
        $input attr-dict `:` type($input)
    }];
}
```

```tablegen
// StandalonePasses.td —— Pass 的声明：名字＋作用对象＋说明
def StandaloneSwitchBarFoo: Pass<"standalone-switch-bar-foo", "::mlir::ModuleOp"> {
  let summary = "Switches the name of a FuncOp named `bar` to `foo` and folds.";
}
```

`assemblyFormat` 那三行值得盯住：它声明了 `%0 = standalone.foo %arg0 : i32` 这行字怎么读——先操作数 `$input`，再可选属性字典 `attr-dict`，冒号后是 `type($input)`。**Day 30 你手写过 generic form；今天这一行声明让普通写法（pretty form）也能被解析和打印**。注意 `Pure`（无副作用）和 `SameOperandsAndResultType`（结果类型＝操作数类型）都是 trait——声明挂上去，后面全是免费的。

- **一个常见误解**："定义一个 op 主要是写 C++。"恰恰相反——手写部分里**没有一行**涉及 op 的语法、类型检查或打印；改动`.td` 里的 `I32` 为 `I64`，解析器、打印器、Verifier 会整体跟着变（§5.4 的 `foo→qux` 就是同款连锁，只是改的是 Pass 侧文本）。

### 3.2 生成：声明如何长成上千行 C++

一句通俗解释：`mlir-tblgen` 是**构建期的翻译官**，把上面三张菜谱译成 7 份 `.inc` 半成品——`StandaloneOps.cpp.inc`、`StandaloneOps.h.inc`、`StandaloneOpsDialect.cpp.inc`、`StandaloneOpsDialect.h.inc`、`StandaloneOpsTypes.cpp.inc`、`StandaloneOpsTypes.h.inc`、`StandalonePasses.h.inc`。

最值得亲眼看的是**从 `I32:$input` 这一个字长出来的 Verifier**（`StandaloneOps.cpp.inc` 真实片段）：

```cpp
static ::mlir::LogicalResult __mlir_ods_local_type_constraint_StandaloneOps0(
    ::mlir::Operation *op, ::mlir::Type type, ::llvm::StringRef valueKind,
    unsigned valueIndex) {
  if (!((type.isSignlessInteger(32)))) {
    return op->emitOpError(valueKind) << " #" << valueIndex
        << " must be 32-bit signless integer, but got " << type;
  }
  return ::mlir::success();
}
```

对照真实报错（§5.3 探针 4b，本机运行）：`'standalone.foo' op operand #0 must be 32-bit signless integer, but got 'i64'`——`operand #0` 是 `valueKind`＋`valueIndex`，后半句一字不差。**Verifier 的报错文案写在 `.td` 约束里，不在任何手写文件里**。

同一份 `.inc` 里还长着两件东西。**打印器**（`print`）：`_odsPrinter << getInput(); … << ' ' << ":"`——把 `$input attr-dict `:` type($input)` 反向吐出来，这就是 round-trip 的另一半。**类型推断**（`inferReturnTypes`）：

```cpp
::mlir::LogicalResult FooOp::inferReturnTypes(...) {
  inferredReturnTypes.resize(1);
  ::mlir::Type odsInferredType0 = operands[0].getType();  // 结果类型＝照抄操作数
  inferredReturnTypes[0] = odsInferredType0;
  return ::mlir::success();
}
```

这解释了一个 Day 30 遗留的小谜题：`%0 = standalone.foo %arg0 : i32` 结尾的 `: i32` 明明标注的是**操作数**，结果 `%0` 的类型从哪来？——`SameOperandsAndResultType` 让生成器自动实现"结果类型照抄操作数"，所以书写格式里结果不需要写类型。

### 3.3 手写胶水：把半成品挂上墙

一句通俗解释：生成器管"这个 op 本身"，手写 C++ 管"它和世界的关系"——方言初始化、Pass 逻辑、工具入口。

- **一个类比**：`.inc` 是预制的门窗，手写 cpp 是毛坯房里打洞装框。**对应到技术上是**：TableGen 无法知道你的工程叫什么、想注册哪些方言、Pass 的**行为**是什么——这些和上下文相关的东西必须手写，一共三份：

```cpp
// lib/Standalone/StandaloneDialect.cpp —— 方言初始化：把生成的 op 清单装进方言
void StandaloneDialect::initialize() {
  addOperations<
#define GET_OP_LIST
#include "Standalone/StandaloneOps.cpp.inc"      // ← 生成的 op 清单在这里展开
      >();
  registerTypes();
}
```

```cpp
// lib/Standalone/StandaloneOps.cpp —— 全文两行：实例化生成的 op 类
#define GET_OP_CLASSES
#include "Standalone/StandaloneOps.cpp.inc"
```

```cpp
// lib/Standalone/StandalonePasses.cpp —— Pass 的行为（生成器只生成了壳）
namespace mlir::standalone {
#define GEN_PASS_DEF_STANDALONESWITCHBARFOO
#include "Standalone/StandalonePasses.h.inc"     // 壳：基类＋注册宏

namespace {
class StandaloneSwitchBarFooRewriter : public OpRewritePattern<func::FuncOp> {
public:
  LogicalResult matchAndRewrite(func::FuncOp op,
                                PatternRewriter &rewriter) const final {
    if (op.getSymName() == "bar") {
      rewriter.modifyOpInPlace(op, [&op]() { op.setSymName("foo"); });  // 今天要改的一行
      return success();
    }
    return failure();
  }
};

class StandaloneSwitchBarFoo
    : public impl::StandaloneSwitchBarFooBase<StandaloneSwitchBarFoo> {
public:
  void runOnOperation() final {
    RewritePatternSet patterns(&getContext());
    patterns.add<StandaloneSwitchBarFooRewriter>(&getContext());
    FrozenRewritePatternSet patternSet(std::move(patterns));
    if (failed(applyPatternsAndFoldGreedily(getOperation(), patternSet)))
      signalPassFailure();
  }
};
} // namespace
} // namespace mlir::standalone
```

第 22 天学过的三件套全在：`OpRewritePattern`（Pattern）＋ `matchAndRewrite`（匹配后重写）＋ `applyPatternsAndFoldGreedily`（贪婪驱动器）。Pass 的"壳"（命令行旗标、`--help` 文案、基类字段）由 `StandalonePasses.h.inc` 生成，"心"（改什么）永远是手写的——**这就是为什么 §5.4 改 `setSymName` 后 `--help` 文案要从 `.td` 的 summary 里同步改**。

工具入口 `standalone-opt/standalone-opt.cpp` 的 `main()` 干三件事：注册全部上游 Pass ＋ 本方言 Pass；建 `DialectRegistry` 并 `insert` 本方言与 `arith`、`func`；交给 `MlirOptMain`——**昨天说的"户口登记处 `MLIRContext`"，登记动作就发生在这几行**：

```cpp
int main(int argc, char **argv) {
  mlir::registerAllPasses();
  mlir::standalone::registerPasses();           // 本方言的 Pass 进注册表

  mlir::DialectRegistry registry;
  registry.insert<mlir::standalone::StandaloneDialect,   // ← 户口在这里登记
                  mlir::arith::ArithDialect, mlir::func::FuncDialect>();

  return mlir::asMainReturnCode(
      mlir::MlirOptMain(argc, argv, "Standalone optimizer driver\n", registry));
}
```

- **一个常见误解**："注册方言＝写解析器。"不是——解析器认识 `standalone.foo` 靠的是 `.td` 的 `assemblyFormat` 生成的 `parse()`；注册只是把**方言对象**放进 registry，让解析器遇到 `standalone.` 前缀时知道去哪找户口。`standalone-opt` 只登记了 4 个方言，`--show-dialects` 输出就是证据：`Available Dialects: arith,builtin,func,standalone`（本机真实输出）。

### 3.4 注册的两条路：自带工具 vs 动态插件

一句通俗解释：同一个方言，**编进自己的工具**（路 A）或**编译成 `.so` 插件喂给系统工具**（路 B）。

- **为什么两条路都要会**：自己的工程随便重编（路 A，秒级增量编译）；但给别人的工具加能力——比如让没重编过的 `mlir-opt-18` 认识 `standalone.foo`——只能走插件。**对应到技术上是**：路 B 的 `standalone-plugin.cpp` 只暴露一个 `extern "C"` 入口，把和路 A **同一份**注册代码装进函数指针：

```cpp
extern "C" LLVM_ATTRIBUTE_WEAK DialectPluginLibraryInfo
mlirGetDialectPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "Standalone", LLVM_VERSION_STRING,
          [](DialectRegistry *registry) {
            registry->insert<mlir::standalone::StandaloneDialect>();
            mlir::standalone::registerPasses();
          }};
}
```

`mlir-opt-18 --load-dialect-plugin=StandalonePlugin.so` 加载后，系统工具与本工程工具行为完全一致（§5.3 实验 7，本机双跑对照过，输出逐字节相同）。将来 CANN 生态里给 `aicpu`／`ascend` 方言扩工具，走的正是这套机制。**类比的边界**：插件不是万能外挂——插件版本必须和宿主工具的 MLIR 版本匹配（API 版本号 `MLIR_PLUGIN_API_VERSION` 就是合同号），版本错位加载即崩。

## 4. 图解核心机制

把 §3 的四块拼成一条流水线：**一份声明怎么变成命令行上能敲的行为**。

![核心机制图：standalone.foo 的诞生与上岗。左侧①定义区三份 .td 卡片（Dialect.td 姓名与命名空间、Ops.td 的 foo 算子声明含 I32 约束与 assemblyFormat、Passes.td 的 Pass 声明）；中上②生成区：mlir-tblgen 生成 7 份 .inc（标出关键 4 份：Ops.h.inc 类声明＋Adaptor、Ops.cpp.inc 解析器/打印器/Verifier、OpsDialect.cpp.inc 方言构造、Passes.h.inc Pass 基类），附生成的 Verifier 代码片段与真实 ninja 日志前 4 步；中下③手写胶水区：Dialect.cpp 的 initialize 装配、Passes.cpp 的 OpRewritePattern 与 setSymName、standalone-opt.cpp 的 main 注册；右侧④上岗两条路：路 A 链接成 standalone-opt 自带工具、路 B 编译成 .so 由 mlir-opt-18 动态加载，两条路共用同一份注册代码；底部 Verifier 闭环条：i64 输入被生成的 Verifier 拦下的真实报错](images/02-mechanism.svg)

**图 2**：从左往右读。①**定义**——三份 `.td` 只声明"是什么"（注意 `Ops.td` 卡片上的 `(ins I32:$input)`，它是右边 Verifier 报错的源头）；②**生成**——`mlir-tblgen` 产出 7 份 `.inc`，其中 `Ops.cpp.inc` 里长着 parse／print／Verifier 三件套和 `inferReturnTypes`（§3.2 逐段讲过）；③**胶水**——`initialize()` 把生成的 op 清单装进方言、`Passes.cpp` 写 Pass 的行为、`main()` 把户口塞进 registry；④**上岗**——同一个方言走两条路：路 A 链接成 `standalone-opt`，路 B 打成 `.so` 塞给系统 `mlir-opt-18`。

图里两个"真凭实据"都来自本机：ninja 日志的前几步（`[1/20] Building StandalonePasses.h.inc...`）和底部 Verifier 拦截 `i64` 的真实报错。**看图记住一件事就够**：`.td` 里的一行声明（`I32:$input`），会在流水线末端变成一条具体的行为（一条报错、一段解析、一个 `--help` 说明）——声明和行为的对应关系，就是今天"源码阅读笔记"的全部内容。

## 5. 动手实践：构建、运行、修改、重新验证

### 5.1 准备文件

本篇交付的 `code/` 目录结构（`standalone/` 为上游原状，另加 4 个实验 `.mlir` 和重放脚本）：

```text
tutorials/day-034/code/
├── run_all.sh                 # 一键重放全部 8 组实验（本篇所有命令都在里面）
├── bar_to_foo.mlir            # 主例子：Pass 的输入（@bar 待改名）
├── foo_demo.mlir              # 实验③：round-trip 正例
├── foo_bad_type.mlir          # 实验 4a：解析器拦截探针
├── foo_bad_verifier.mlir      # 实验 4b：op Verifier 报错探针
└── standalone/                # 上游 out-of-tree 工程（保持原状交付）
    ├── CMakeLists.txt
    ├── include/Standalone/    # 3 份 .td ＋ 3 份 .h（§3.1 的声明都在这）
    ├── lib/Standalone/        # 3 份手写 .cpp（§3.3 的胶水都在这）
    ├── standalone-opt/        # 工具入口 main()（路 A）
    ├── standalone-plugin/     # 插件入口（路 B）
    ├── standalone-translate/  # 翻译工具入口
    └── test/Standalone/       # lit ＋ FileCheck 官方测试（§5.4 的红绿就在这）
```

环境（本机实测记录：Ubuntu 20.04 arm64）：`mlir-18-tools`、`libmlir-18-dev`、`llvm-18-dev`（`dpkg` 显示版本 `1:18.1.8-11~20.04.2`）、`cmake ≥ 3.20`、`ninja`、`lit 18.1.8`（`pip` 安装）。若尚未安装：`apt install cmake ninja-build mlir-18-tools libmlir-18-dev llvm-18-dev && pip install lit==18.1.8`。本机环境已预装好，以下输出全部来自真实执行。

### 5.2 构建工程

```bash
cd tutorials/day-034/code
cmake -G Ninja -S standalone -B /tmp/day034-build \
  -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir \
  -DLLVM_EXTERNAL_LIT="$(command -v lit)"
ninja -C /tmp/day034-build
```

`MLIR_DIR` 指向系统 MLIR 的 `MLIRConfig.cmake`——**out-of-tree 的关键一步**：工程从这里借走 `mlir-tblgen`、TableGen 模板和链接库，不必自己编一遍 LLVM。真实构建日志（节选）：

```text
ninja: Entering directory `/tmp/day034-build'
[1/20] Building StandalonePasses.h.inc...
[2/20] Building StandaloneOps.cpp.inc...
[3/20] Building StandaloneOpsDialect.cpp.inc...
[4/20] Building StandaloneOpsDialect.h.inc...
[5/17] Building StandaloneOpsTypes.h.inc...
[6/17] Building StandaloneOps.h.inc...
[7/13] Building StandaloneOpsTypes.cpp.inc...
构建产物：standalone-opt
standalone-translate
```

**看懂这份日志就懂了 out-of-tree 的本质**：前 7 步没有任何一行 C++ 被编译——全是 `mlir-tblgen` 在把 `.td` 译成 `.inc`（图 2 的②）。之后的编译单元 `#include` 这些 `.inc`（§3.3 的 `GET_OP_LIST`／`GET_OP_CLASSES`），半成品才被装进成品。最终产出两个工具（`ls /tmp/day034-build/bin`：`standalone-opt`、`standalone-translate`）和 `lib/` 下的 `libMLIRStandalone.a`、`StandalonePlugin.so` 等库。

### 5.3 运行与观察：六个观察点

以下命令均可单独执行，也可用 `bash run_all.sh` 一键重放。

**观察点 1——方言注册表**：

```bash
/tmp/day034-build/bin/standalone-opt --show-dialects
```

```text
Available Dialects: arith,builtin,func,standalone
```

`main()` 里 `registry.insert` 了几个，这里就列几个——昨天"户口登记处"的可视化。

**观察点 2——round-trip**：`standalone-opt foo_demo.mlir` 原样吐回（生成的 parse 读进来、生成的 print 写出去，一来一回没走样，输出见 `foo_demo.mlir` 内容本身）。注意 `: i32` 只标注操作数，结果类型由 `inferReturnTypes` 照抄（§3.2）。

**观察点 3——两道报错关卡**（改自 Day 30 的"错误探针"方法，两个文件只差参数类型；以下报错为本机真实输出，绝对路径前缀截短为文件名）：

```bash
standalone-opt foo_bad_type.mlir        # 块参数声明 i32，使用处却写 i64
```

```text
foo_bad_type.mlir:3:23: error: use of value '%arg0' expects different type than
prior uses: 'i64' vs 'i32'
```

```bash
standalone-opt foo_bad_verifier.mlir     # 块参数本来就是 i64，语法自洽
```

```text
foo_bad_verifier.mlir:4:8: error: 'standalone.foo' op operand #0 must be
32-bit signless integer, but got 'i64'
```

对比这两条是今天最重要的观察：**前者是解析器（generic 语法层）拦的——类型对不上就根本组不出 Value；后者语法完全合法，IR 组装完后由 op 自己的 Verifier 检查**，报错文案正来自 §3.2 那段生成的 `isSignlessInteger(32)`。`.td` 声明 → 生成 Verifier → 真实报错，三点一线。

**观察点 4——运行 Pass 的两种写法**：

```bash
standalone-opt bar_to_foo.mlir --standalone-switch-bar-foo          # 写法一：直连旗标
standalone-opt bar_to_foo.mlir \
  --pass-pipeline="builtin.module(standalone-switch-bar-foo)"        # 写法二：显式管线
```

两种写法输出逐字节相同（本机对照过，退出码均为 0）：

```text
module {
  func.func @foo() {          ← @bar 被改名，Pass 生效
    return
  }
  func.func @other(%arg0: i32) -> i32 {   ← @other 不匹配 "bar"，原样穿过
    %0 = standalone.foo %arg0 : i32
    return %0 : i32
  }
}
```

写法一更短，写法二把 Pass 嵌进显式管线结构（Day 22 的 PassManager 写法）——工程里两种都要认得。

**观察点 5——官方 lit 测试**：`ninja -C /tmp/day034-build check-standalone` 跑工程自带的 6 个测试：

```text
Total Discovered Tests: 6
  Unsupported: 1 (16.67%)
  Passed     : 5 (83.33%)
```

`Unsupported` 的那 1 个是 Python 绑定冒烟测试——本构建未开启 `MLIR_ENABLE_BINDINGS_PYTHON`，lit 把它标为"不支持"而非失败，属正常现象。

**观察点 6——插件喂给系统工具**（§3.4 路 B）：

```bash
mlir-opt-18 bar_to_foo.mlir \
  --load-dialect-plugin=/tmp/day034-build/lib/StandalonePlugin.so \
  --pass-pipeline="builtin.module(standalone-switch-bar-foo)"
```

输出与观察点 4 完全一致——**没重编过一行系统工具，它已经认识 `standalone.foo` 并能跑我们的 Pass**。若去掉 `--load-dialect-plugin` 直接跑，会被方言注册表当场拦下：`Dialect `standalone' not found for custom op 'standalone.foo'`（§6 错误 A 的真实报错，附已注册方言清单）。

### 5.4 修改一个输出文本再观察：`foo`→`qux` 闭环

计划要求"修改一个输出文本或简单属性并重新验证"。我们改 Pass 的输出文本：`setSymName("foo")` → `setSymName("qux")`。改之前先预测——第 1 章的问题 3 在这里兑现：`@foo` 同时活在**三个地方**（IR 输出、`--help` 文案、lit 的 CHECK 行），一个改动、三处连锁。完整闭环 `run_all.sh` 实验 8 已封装（结束自动还原源码），手动版如下：

```bash
cd tutorials/day-034/code
# (8a) 备份后改两处：Pass 行为＋.td 说明（生成器要靠 summary 印 --help 文案）
sed -i 's/op.setSymName("foo")/op.setSymName("qux")/' \
  standalone/lib/Standalone/StandalonePasses.cpp
sed -i 's/named `bar` to `foo`/named `bar` to `qux`/g' \
  standalone/include/Standalone/StandalonePasses.td
ninja -C /tmp/day034-build          # (8b) 增量重编译，几秒完成
standalone-opt bar_to_foo.mlir --pass-pipeline="builtin.module(standalone-switch-bar-foo)"
```

(8b) 真实输出——行为已变：

```text
  func.func @qux() {                          ← 新名字
  func.func @other(%arg0: i32) -> i32 {      ← 不匹配的照旧穿过
```

(8c) `--help` 文案跟着变（因为它是从 `.td` 的 `summary` 生成的）：

```text
      --standalone-switch-bar-foo  -  Switches the name of a FuncOp named `bar` to `qux` and folds.
```

(8d) **测试抓住改动**——lit 真实输出，两个测试从绿变红：

```text
FAIL: STANDALONE :: Standalone/standalone-plugin.mlir (4 of 6)
FAIL: STANDALONE :: Standalone/standalone-pass-plugin.mlir (5 of 6)
Failed Tests (2):
  Passed     : 3 (50.00%)
  Failed     : 2 (33.33%)
```

红的原因：测试文件里的期望 `// CHECK-LABEL: func @foo()` 还在等旧名字，而 IR 已输出 `@qux`——**FileCheck 的本质就是"期望 vs 实际"逐行对账**。(8e) 把两个测试文件的 `@foo()` 更新为 `@qux()`，重跑恢复全绿（`Passed: 5 (83.33%)`）。(8f) 还原 `.orig` 备份、重编译确认基线（`@foo` 回来、测试 5 通过），交付的源码树保持上游原状。

![修改闭环图：foo→qux 的一圈。左上输入卡 bar_to_foo.mlir 与原版 Pass 输出（@bar 改名 @foo、@other 不动）；右上"@foo 活在三处"卡（IR 输出、--help 说明、lit CHECK 行）；中部六步环：8a 改两行（Passes.cpp 的 setSymName 与 .td summary）→ 8b 重编译 → 8c 输出变 @qux 且 --help 同步 → 8d lit 两个 FAIL（CHECK 还在等 @foo）→ 8e CHECK 改为 @qux 恢复全绿 → 8f 还原上游原状；右侧 lit 真实计数条：基线 Passed 5 Unsupported 1、改后 Failed 2、修后 Passed 5；附 Unsupported 1 的原因说明（Python 绑定未开启）](images/03-example.svg)

**图 3**：对照着刚才的 (8a)～(8f) 读一圈。重点不是"改了名字"，而是**改动的可见范围**：改一行 `setSymName`，IR 输出立刻变（8b→8c）；`--help` 文案跟着变，前提是 `.td` 的 summary 同步改（8a 的第二处 `sed`）；测试变红是**好事**——它证明"期望"被显式写在了 CHECK 行里，改动逃不过对账（8d）；把期望更新为新的行为，测试恢复绿（8e）；最后还原，基线复测（8f）。右上角"三处卡"就是第 1 章问题 3 的答案：**一个输出文本，同时活在代码、文档生成、测试期望三个文件里**。

顺带验证了 `--help` 文案的来源：它不是手写字符串，而是 `StandalonePasses.h.inc` 从 `.td` 的 `summary` 生成的——**改声明，文档自动跟**，这就是"声明式"定义 op 的第二重红利（第一重是 Verifier，见 §5.3 观察点 3）。

## 6. 常见错误与排查

**错误 A：系统工具说不认识我的方言**
- **现象**：`mlir-opt-18 foo_demo.mlir` 直接报错退出（`exit=1`）：

```text
foo_demo.mlir:3:8: error: Dialect `standalone' not found for custom op 'standalone.foo'
note: Registered dialects: acc, affine, amdgpu, ... func, ...（长列表，无 standalone）
```

- **原因**：`mlir-opt-18` 的 `main()` 只预装上游方言；`standalone` 只在我们自己的工具和插件里注册。
- **定位**：看 note——它就是宿主工具的注册表（与 `--show-dialects` 同源），清单里没有 `standalone` 即确认。
- **修复**：三选一——用 `standalone-opt`（路 A）；加 `--load-dialect-plugin=.../StandalonePlugin.so`（路 B）；或加 `-allow-unregistered-dialect`（Day 33 说过的调试后门，Pass 不生效，仅救急）。

**错误 B：把解析器报错当成 Verifier 报错（或反过来）**
- **现象**：同样是"喂 `standalone.foo` 一个 i64"，两个探针报错完全不同：`use of value '%arg0' expects different type than prior uses: 'i64' vs 'i32'`（`foo_bad_type.mlir:3:23`）vs `'standalone.foo' op operand #0 must be 32-bit signless integer, but got 'i64'`（`foo_bad_verifier.mlir:4:8`）。
- **原因**：前者发生在**组装 IR 时**（块参数类型对不上，Value 都组不出来）；后者 IR 已合法组装，是 op 的 Verifier 在检查 `.td` 约束。
- **定位**：报错格式可区分——解析器报错不带 op 名、指向"值的类型"；Verifier 报错以 `'op全名' op` 开头、指向"第几个操作数"（`operand #0`）。
- **修复**：按关卡对症：改块参数声明或使用处的类型写法（前者）；改 `.td` 的约束或换正确类型（后者）。判断关卡再动手，别拿 Verifier 文案去猜语法问题。

**错误 C：改了 Pass，测试从绿变红**
- **现象**：§5.4 的 (8d)：`check-standalone` 两个测试 `FAIL`，`Failed: 2 (33.33%)`。
- **原因**：行为改了，期望没改——CHECK 行还在等 `@foo()`，实际输出已是 `@qux()`。
- **定位**：lit 的 FAIL 行指出具体测试文件；打开看 `// CHECK-LABEL: func @foo()` 与实际输出对照。
- **修复**：这不是坏事——把期望更新为新的正确行为（`@foo()`→`@qux()`）即恢复全绿。若测试变红是因为改动本身错了，CHECK 就替你挡住了回归：**这正是"修改并重新验证"要交付的证据**。

**错误 D：shell 脚本里 `grep -m1` 配 `pipefail` 的假阴性**
- **现象**：本篇 `run_all.sh` 早期版本在实验 4 打印了误导性的"(预期 error 未出现)"，可 error 明明就在上一行。
- **原因**：`set -o pipefail` 下，`cmd | grep -m1 "error:"` 的 `grep` 找到首 match 即退出，上游 `standalone-opt` 写管道时收到 SIGPIPE（退出码 141），整条管线被判失败。
- **定位**：`echo "${PIPESTATUS[@]}"` 能看到 `141 0`——错误不在 grep，在管线。
- **修复**：先收再筛——`err=$(cmd 2>&1 || true)` 存下全部输出，再 `grep`；交付版 `run_all.sh` 已改用此写法（工程里排查"脚本和工具谁在说谎"的通用套路）。

## 7. 今日练习

### 必做练习

把 Pass 的**匹配名**从 `"bar"` 改成 `"other"`：`StandalonePasses.cpp` 里 `op.getSymName() == "bar"` 改为 `== "other"`，`.td` 的 summary 同步改，重编译。**先书面预测再动手**：(1) IR 输出里谁改名、改名成什么？`@bar` 和 `@other` 各自的命运？(2) `--help` 文案变成什么？(3) lit 测试红几个、为什么？验证后对照 `run_all.sh` 实验 8 的手法更新 CHECK、再还原源码。预期产出：一份"预测 vs 实测"对照笔记（四条各一句话）。

### 选做挑战

- 用 `standalone-opt --mlir-print-op-generic foo_demo.mlir` 看 `standalone.foo` 的 generic form，找到以完整字符串出现的 `"standalone.foo"`——数一数它带几个操作数、几个结果，和 `.td` 的 `ins/outs` 对上。
- 给 `foo_bad_verifier.mlir` 换成 `i1`／`f32` 重跑，观察报错文案只有类型名在变——体会"约束文案是同一份生成代码"（都标注 `must be 32-bit signless integer`）。
- 在 `.td` 里把 `I32:$input` 改成 `I64:$input`，重编译后直接重跑 `foo_demo.mlir`（不改它），观察角色互换——现在轮到 `i32` 版本报 `must be 64-bit`。做完记得还原。

## 8. 今日验收

- [ ] 我能不看资料说出 3 份 `.td`（Dialect／Ops／Passes）各自声明什么、7 份 `.inc` 里哪 4 份最关键、3 份手写 C++ 各负责什么"上下文胶水"；
- [ ] 我能独立完成构建，并向别人解释 ninja 日志前 7 步为什么全是 `.inc`、为什么 `.inc` 不进版本库；
- [ ] 我能用两个探针区分解析器报错和 Verifier 报错，并指出 Verifier 文案在生成代码里的那一行；
- [ ] 我能用两种写法运行 `standalone-switch-bar-foo`，并用插件让系统 `mlir-opt-18` 认识 `standalone.foo`；
- [ ] 我完成了 `foo→qux`（或必做练习的 `bar→other`）闭环：能预测三处连锁变化，让测试先红后绿，最后把源码树还原为上游原状，并保存了重放脚本与运行记录。

## 9. 一句话总结与明天预告

今天把 Day 33 的"户口本"变成了可运行的命令：**声明（`.td`）→ 生成（`mlir-tblgen` 出 `.inc`）→ 胶水（手写注册与 Pass 行为）→ 上岗（自带工具或插件）**；构建日志的 `.inc` 前置、`--show-dialects` 的注册表、两道报错关卡、`foo→qux` 的三处连锁与测试红绿，全部在本机跑通并留档。最重要的收获是**声明与行为的对应**：`.td` 里的一行约束，最终变成一条报错、一段 `--help` 文案、一组 CHECK 期望——改声明，三者自动跟着变。明天是第 5 周复盘：不查资料解释一段 MLIR，把 Operation、Value、Region、Block、Type、Attribute、Dialect 串成一张概念图——今天亲手装配过的"注册→解析→验证→重写"链条，正是那张图上每个概念的现实落点。




