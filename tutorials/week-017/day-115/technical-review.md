# 第 115 天技术校对报告

审阅范围：README.md、code/（func_lowering.py、loop_ir.mlir、run_all.sh、gen_images.py）、outputs/ 全部冻结产物、images/ 三张 SVG。核实方式：在临时目录完整复跑 `./run_all.sh`（复现 8/8 PASS＋9/9 PASS，仅时间戳与 ASLR 相关地址不同）；对 P1 探针、strides 单位、ctypes 按值传参等存疑点做了独立数值实验；对真实 MLIR 行为的论断查证了 llvm-project 当前 main 的源码与官方文档（TypeConverter.cpp、FuncToLLVM.cpp、LoweringOptions.cpp、BuiltinOps.td、DataLayout.md、上游测试 func-memref.mlir）；对 AAPCS64 规则用本机 gcc 9.4.0 实测。以下意见只写入本报告，不改动教程原文、代码或冻结输出。

## 【错误】

#### 1. "56 字节按值传参"被归因为"真实 MLIR 的结论"——真实 MLIR 默认 ABI 下 memref 参数是展开的标量，不是按值聚合
- **原文**：“D114 说"56 字节按值传参"时是引用真实 MLIR 的结论”
- **依据**：llvm-project main 的 mlir/lib/Conversion/LLVMCommon/TypeConverter.cpp 中默认（非 bare-ptr）参数转换器 `structFuncArgTypeConverter` 明确写着 "In signatures, Memref descriptors are expanded into lists of non-aggregate values"，它调用 `getMemRefDescriptorFields(memref, /*unpackAggregates=*/true)`——rank2 memref **参数**在 `llvm.func` 签名里展开为 7 个独立标量（2×ptr＋5×i64），不是一个 56B 聚合；上游测试 mlir/test/Conversion/FuncToLLVM/func-memref.mlir 的 CHECK 逐参数核对（`CHECK-COUNT-2: !llvm.ptr`＋`CHECK-COUNT-5: i64`），@memref_index 的 CHECK 也显示参数为 5 个标量、**返回值**才是 `!llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>`。也就是说"按值结构体"只出现在返回侧；合计 56 字节的是那 7 个标量，不是"一个聚合值"。D114 的 technical-review.md 第 2 条已把同一说法列为错误，D115 却再次确认该归因。受影响处：§1 伏笔引用（"默认 ABI 下每个 memref 参数是 56 字节的聚合值"）、§3.1"对应到技术上是：……变成 `llvm.func @gemm(%a: !llvm.struct<…>, …)`"、图 2 图注"GEMM 参数合计 112B（……机器上按"间接传"——调用方复制、寄存器放副本地址）"——mini 管道把自己的参数建模成单个 struct 是合法的教学简化（且其返回值打包与真实 MLIR 一致、JIT 边界用 ptr 也与 `_mlir_ciface` 思路一致），错的是把它说成"真实 MLIR 的结论/默认 ABI"。gcc 的 C ABI 证据链本身（按值＝间接传）没有问题。
- **置信度**：高——上游源码、上游测试、D114 既有审阅三重印证；仅"当前 main"与教程写作时点可能存在版本差，但该"签名内展开"行为多年稳定。

#### 2. "index 的位宽正是从目标指针宽度推出来的"——机制归因错误：MLIR 的 index 缺省位宽是 dlti 固定 64 位，与指针宽度无关
- **原文**：“`index` 的位宽正是从目标指针宽度推出来的——64 位目标上 `index` 兑换成 `i64`，这就是 D114 类型表第一条的"官方理由"”
- **依据**：MLIR 官方文档 DataLayout.md 明确写 "In absence of the corresponding entry, `index` is assumed to be a 64-bit integer"——缺省是固定 64 位；mlir/lib/Conversion/LLVMCommon/LoweringOptions.cpp 的构造函数是 `indexBitwidth = dl.getTypeSizeInBits(IndexType::get(ctx))`，来自 MLIR 的 DataLayout（dlti 规范，可用 `#dlti.dl_entry<index, 32>` 覆盖），而指针宽度只进入 `LLVMTypeConverter::getPointerBitwidth`（读 LLVM data layout）。因此"官方理由"不是指针宽度；64 位目标上结论碰巧相同（i64），但推导路径的表述不成立。教学版 `TeachingDataLayout` 里 `index_bits = pointer_bits` 作为简化模型没有问题，问题只在把它说成真实 MLIR 的机制。func_lowering.py 的注释"位宽随目标指针宽度（64 位目标 -> i64）"同错。
- **置信度**：高——依据当前 main 源码与官方文档；未考证更早版本 MLIR 是否曾有按指针宽度推导的行为，但教程以现在时陈述"真实 MLIR"。

#### 3. 发射的 `builtin.unrealized_conversion_cast` 用 `->` 分隔类型——真实 MLIR 语法是 `to`
- **原文**：“out.append(f"%{n}_m = builtin.unrealized_conversion_cast %{n} : {new} -> {old}")”
- **依据**：llvm-project main 的 mlir/include/mlir/IR/BuiltinOps.td 中 UnrealizedConversionCastOp 的 assemblyFormat 是 `($inputs^ \`:\` type($inputs))? \`to\` type($outputs)`；官方 DialectConversion.md 示例与上游测试（mlir/test/Conversion/FuncToLLVM/func-to-llvm.mlir 的 CHECK）均为 `builtin.unrealized_conversion_cast %arg0 : i64 to index` 形式。partial-ir.mlir 与 partial-ir-s232.mlir 里全部 8 条 cast、README §3.4/§4/§5.2 的引用、图 2 左下（"cast %a : !llvm.struct<...> -> memref<...>"、"i64 -> index"）都写成了 `->`，真实 mlir-opt 会拒绝解析。该文本本机不经解析器（无 MLIR），运行不受影响，但教程声称"四角色、兑换表、胶水……对照真实 MLIR 的行为建模"，且 op 前缀 `builtin.` 都写对了，唯独关键分隔符错——对要以"能对上真语法"为目标的读者是实打实的语法错误。
- **置信度**：高——ODS 源码、官方文档、上游测试三处一致。

#### 4. `llvm.mlir.constant 0 : i64` 缺少括号——真实语法是 `llvm.mlir.constant(0 : i64) : i64`，且与本系列 D113/D114 自身产物不一致
- **原文**：“A1 已把 `arith.constant 0 : index` 换成 `llvm.mlir.constant 0 : i64`”
- **依据**：LLVM Dialect 官方文档（Dialects/LLVM.md）示例为 `%3 = llvm.mlir.constant(42 : i32) : i32`——带类型的属性值放在括号内、结果类型跟在冒号后；本系列 D113 README 的词汇表写的就是 `llvm.mlir.constant(2 : i32) : i32`，D114 冻结产物 outputs/llvm-dialect-target.mlir 全部 12 条也是 `llvm.mlir.constant(48 : i64) : i64` 形式。D115 的 partial-ir.mlir（6 条常量）、partial-ir-s232.mlir、README §4 与图 2 的文本全部丢掉了括号，真实 MLIR 无法解析（也与前两天自己冻结的语法形态自相矛盾）。
- **置信度**：高——官方文档＋同仓库前后两天的冻结产物对照。

#### 5. P1 探针"对角线 3 点碰巧读对"——实际是 4 点，且与"20/24 点错"自相矛盾
- **原文**：“连续布局下只有对角线 3 点碰巧读对（i+6j=6i+j ⇔ i=j）”
- **依据**：P1 用 4×6 矩阵（A_big[:4]），i=j 时 i+6j=6i+j 成立的点为 (0,0)、(1,1)、(2,2)、(3,3) 共 **4** 个（i 范围 0..3、j 范围 0..5，对角点数=min(4,6)=4）；冻结报告"20/24 点错"本身蕴含 24−20=4 点对。我用与 tp8 相同的地址公式独立复算：恰 4 点值相等、20 点错。func_lowering.py 第 802 行注释"i==j 的 3 个对角点恰好读对"、图 3 面板④"对角线 3 点碰巧读对"、README §5.3 图 3 图注同错——"3"疑似从 D114 的 4×3 结果矩阵（min(4,3)=3）带过来的惯性数字。
- **置信度**：高——数值复算＋冻结报告内部矛盾双重确认。

#### 6. 引用 D114 的 P1 数字"120.13"——D114 冻结产物是 120.0132
- **原文**：“对照 D114 的仿真层 P1（2 个 NaN＋120.13）”
- **依据**：D114 冻结输出 outputs/conversion-report.txt 与 run-all-log.txt 均为"有限部分 max|diff|=120.0132，未写元素 2 个（NaN）"——120.0132 保留两位小数应写 120.01，"120.13"与原值不符（疑为转写时丢了一位 0）；图 3 面板④同样写"120.13"。NaN 数量（2 个）引用正确。
- **置信度**：高——直接对照 D114 冻结文件。

#### 7. 常见错误 1 的"定位"因果链不成立——"连续布局两种口径一致"是错误解释
- **原文**：“连续布局 [6,1] 恰好两种口径一致（6×4B=24B 行距 vs 6 元素），所以只有非连续布局暴露”
- **依据**：24B 与 6 元素是两个不同数值，谈不上"一致"；若真把 numpy 字节 strides (24,4) 当元素步长填进连续 4×6 描述符，地址 i*24+j*4 与正确索引 i*6+j 至多在 (0,0) 一点相等（其余 23 点全错，含越界读），连续布局同样会暴露 bug。而转置视图 (4,16)B↔(1,4) 元素同样满足"字节＝元素×itemsize"的换算关系，"口径一致"根本区分不了两种布局。真正的机制在代码里：tp6 中 A 的描述符 strides 是从类型文本硬编码的 `(6, 1)`（元素单位），只有转置视图 Bv 的描述符才从 numpy `.strides`（字节单位）推导——单位混用只发生在后者，所以"连续 24/24 全对、转置只对 1/12"。应按代码事实改写定位，否则初学者会以为连续布局对单位不敏感（实测恰恰相反）。
- **置信度**：高——数值推导＋复现两种填法的结果对比。

#### 8. §3.3 证据链②"真机 JIT 实测 x0 收到副本地址"在随附代码中不存在——echo 实验传的是整数地址，展示的是"直通"而非"副本"
- **原文**：“用 ctypes（libffi 实现）调 JIT 函数，x0 里收到的是副本地址而非原对象地址”
- **依据**：当天代码里唯一的 echo 调用在 tp6：`echo = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_void_p)(...)`，传入 `A.ctypes.data_as(...).value`（一个整数），echo 原样回传——冻结报告自己的措辞就是"echo：x0 直通指针（回传 0x… == 传入 0x…）OK"，展示的是指针直通。要实测"x0＝副本地址"必须把 56B 的 `Desc` **按值**传给 ptr 形参（`CFUNCTYPE(ctypes.c_int64, Desc)(echo)(d)` 后比对回传地址与原对象地址），func_lowering.py 里没有这个实验；§6 常见错误 3 的"定位"所描述的"写 echo 函数回传收到的指针……间接传能看到'副本地址 ≠ 原地址'"与随附代码不符。技术事实本身成立——我在本机按上述方式复验，按值传参时回传地址确实不同于原对象地址——错的是"今天拿三条独立证据钉死"中的②：它无法从当天产物复现，读者照着代码做不出这个观察。
- **置信度**：高——代码与冻结报告逐行核对，且独立复验了该 ABI 事实为真。

## 【存疑】

#### 1. "对超过 16 字节的聚合按'间接'传"作为 AAPCS64 一般规则过于绝对——HFA（同构浮点聚合）是例外
- **原文**：“对超过 16 字节的聚合按"**间接**"传”
- **依据**：AAPCS64 对 HFA 另有规则：成员数 ≤4 的 HFA 不论总大小都走 FP/SIMD 寄存器传递（返回方向同理，不经 x8）。本机 gcc 9.4.0 -O2 -S 实测：`struct {double a,b,c;}`（24B，HFA 3 成员）按值传参的函数体直接是 `fadd d0, d0, d1`（参数在 d0~d2），并非间接传；`struct {double a,b,c,d,e;}`（40B，HFA 5 成员>4）才从 `[x0]` 读。本教程的 desc 结构（指针＋整数混合，非 HFA）不受影响、结论仍成立；但同段"大于 16B 的返回值在 aarch64 上就是 sret 式的'调用方给地址、被调方往里写'"同样漏了 HFA 例外（≤4 成员 HFA 用 v/d 寄存器返回）。建议补一句"非 HFA 聚合"限定，或注明本例结构不含同构浮点成员、恰好落在">16B 非聚合寄存器类"的分支。
- **置信度**：高（本机实测反例；仅影响表述一般性，不影响当天结论）。

## 【建议】

#### 1. "真实输出节选"的行文格式与冻结文件不一致，宜标注"已重排"
- **原文**：“真实输出节选（`outputs/func-report.txt`，2026-11-13 一次冻结运行）”
- **依据**：冻结文件里不存在"[PASS] TP1 DataLayout 对账"这样的行——实际格式是"[TP1] DataLayout 对账：教学计算 vs 真机 LLVM TargetData"标题行＋末尾汇总"TP1: PASS"；README 节选把 PASS 前置、合并缩进。所有数值（56B/偏移/112B/20/24 等）逐项核对一致，仅呈现形式经编辑。建议注明"节选、格式有压缩"，或逐字引用原行，免得读者 diff 冻结文件时困惑。
- **置信度**：高。

#### 2. byval/直接聚合的错位数值与冻结报告不一致，且该值不在任何冻结产物中
- **原文**：“签名的函数读到 281474053336576 这种明显是指针的值”
- **依据**：func-report.txt 冻结值为 byval 281474228691920、直接聚合 281474228691856；281474053336576/281474053336512 只出现在 gen_images.py 与图 3 中（全目录 grep 验证），不在任何 outputs/ 冻结文件里。两处都注明"随环境变化"，技术上无碍，但图 3 标题写"全部本机冻结数字"就与事实不符。建议统一为冻结值，或在图 3/常见错误 3 处注明"另一次开发期运行的实测值"。
- **置信度**：高。

#### 3. §5.2 的 pack_results 片段以字面 `...` 结尾，单独复制不可运行
- **原文**：“return {"llvm": convs[0]["llvm"], "size": convs[0]["size"], ...}”
- **依据**：该行内嵌字面省略号，脱离上下文复制会得到语法错误；真实实现（func_lowering.py pack_results）返回含 align/packed 的完整字典。上下文有"省略说明"，但代码围栏里出现不可执行的 `...` 对初学者易误导；建议补全该行（只差两个字段）或改为注释式省略标记。
- **置信度**：高。

#### 4. 选做挑战"把收到的 x8 回传出来验证"缺少可行性提示——LLVM IR 层读不到 x8
- **原文**：“你可以再写一个 `echo` 版把收到的 x8 回传出来验证”
- **依据**：x8 是机器级 ABI 寄存器；LLVM IR 的按值返回大聚合在 IR 层不暴露隐式 sret 指针，IR 也没有读取指定物理寄存器的指令。要"回传收到的 x8"需要内联汇编（例如 C 侧 register 变量 `asm("x8")`），或把函数改写成显式 `ptr sret(%desc)` 形参再 ptrtoint——都比提示字面的"写一个 echo 版"多两步前置知识。建议在提示里点明"IR 层看不到 x8，需内联汇编或 sret 形参"，否则初学者会卡在"LLVM IR 怎么读 x8"上。
- **置信度**：中——结论基于 LLVM IR/AArch64 语义推断并经 D113 样例佐证，未逐条实验内联汇编方案。
