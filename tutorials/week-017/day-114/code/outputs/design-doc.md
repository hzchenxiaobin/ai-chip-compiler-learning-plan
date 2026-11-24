# 第 114 天：最终 Lowering 设计文档

## 1. 任务与输入

把 `loop_ir.mlir`（GEMM A(4×6)@B(6×3) 的循环 IR）降成只含 `llvm.*` 的目标形态。源 IR 18 op；目标形态 69 op、10 个基本块。信息显式化的代价在这里量化：每条 memref.load 展开 10 条目标 op，每个描述符要 7 次 insertvalue 填充。

## 2. 角色分工（与 D85 同一套框架）

- **ConversionTarget（终态）**：只允许 `llvm.*`；mini/scf/memref/arith/func 全非法。真实管道分 Pass：convert-scf-to-cf → convert-arith-to-llvm → convert-memref-to-llvm → convert-cf-to-llvm → convert-func-to-llvm → reconcile-unrealized-casts；每个 Pass 有自己的合法集，终态只有一份。
- **TypeConverter（兑换表）**：index→i64；f32/i32 原样；memref→五字段描述符（与真实 MLIR MemRefDescriptor 字段与顺序一致）；tensor／动态 memref 拒收。
- **ConversionPattern（翻译手册）**：F1/R1/A1~A3/C1/M1~M3 共 10 条，见 `legality-checklist.md` 第一节。
- **驱动器**：full＝残留即整体失败（D117 导出前的门）；partial＝残留记账（D115~D116 渐进施工的账本）。两种模式共用同一份残留报告格式。

## 3. 关键设计决策

1. **alloc → malloc 运行库调用**（模式 M3）：真实 MLIR 的 MemRefToLLVM 默认把 memref.alloc 降成对 malloc 的调用；描述符字段随后用 insertvalue 填满。
2. **iter_args → 块参数 → phi**（模式 C1）：scf.yield 的值沿回边传回头块，导出后是 phi（D113 规则 R3）；出口块的块参数接住循环终值。
3. **load/store 的地址公式**（M1/M2）：addr_elems = offset + Σ idx_d×stride_d，getelementptr 负责元素→字节。字段编号 [1]=aligned、[2]=offset、[4,d]=strides——这是 P1 探针盯防的位置。
4. **描述符按值传参**：默认 ABI 下每个 memref 参数是 56 字节的聚合值；教学真机验证用'指针+聚合 load/sret'等价形式，字段运算一致，D115 实现时对齐真实 ABI。
5. **常量内联发生在导出**：目标形态里常量是 op（llvm.mlir.constant）；LLVM IR 文本里按 D113 规则 R2 内联成字面量、不占槽位。

## 4. 实现排期（本周）

- D115：F1/R1/A1（函数签名与类型）——对照实验 B 的两道闸就是它的验收。
- D116：M1/M2/M3/A2/A3（内存与算术）——Relu/Add 先行，参考结果验证。
- D117：C1（循环）+ 完整管道 → 导出 LLVM IR；full 驱动必须全绿。
- D118：执行（JIT/AOT）——真机验证脚本今天是它的预演。

## 5. 残留报告格式（partial 模式的账本）

每条残留两行：`op 简述` + `原因`，原因取值：'模式未注册（排期见清单）'、'类型转换失败：…'、'非法方言 mini.*…'、'明确暂不支持：…'。D117 导出前，账本必须清零或逐项写明归属。
