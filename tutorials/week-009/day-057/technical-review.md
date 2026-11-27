# 第 57 天技术校对报告

校对方法：在与仓库同构的环境（Python 3.11.4 / numpy 1.26.4 / Ubuntu LLVM 18.1.8 `mlir-opt` / Linux aarch64）中把 `code/` 复制到 /tmp 临时目录复跑全部产物——`layout_lab.py`（19/19）、`test_layout.py`（14/14）、`mlir-opt` 解析 / `--canonicalize` / `bad_load.mlir` 的输出与仓库冻结输出逐字节一致；`make_images.py` 在临时目录重生成 4 张 SVG 亦与冻结版逐字节一致。另做了 7 组对照实验：MLIR 侧验证 `strided<[...]>` 缺省 offset、`memref.transpose` / `memref.reinterpret_cast` 的 Verifier 校验行为、stride 0 与负 stride 的接受性、选做挑战 3×3 版本可行性；numpy 侧验证连续性判定的退化维度边界、`(6,)` 视图非零 offset 反例、必做练习视图的元信息；以及两次 run_all.sh 故障注入（故意失败的断言、无 mlir-opt 环境模拟）。git 历史确认 day-057 内容首次提交于 2026-11-12，与 README 声明的输出日期一致；总计划的六阶段划分与第 9–11 周主题均与正文及图 1 相符。以下结论均可复现。

## 【错误】

#### 1. run_all.sh 的「exit=$?」恒取 tee 的退出码：实验失败与 mlir-opt 缺失都被报告为成功，后者还会清空已保存的真实输出
- **原文**：“`run_all.sh` 会先打印环境（本机实测：Python 3.11.4、numpy 1.26.4、Ubuntu LLVM 18.1.8 的 `mlir-opt`、Linux aarch64），再依次跑 Python 实验、MLIR 解析与折叠、错误注入。没有 `mlir-opt` 也能跑前两步，Python 实验不依赖它。”
- **依据**：三个可复现的事实。(a) 步骤 1–4 均为 `python3 layout_lab.py | tee "$OUT/..."` 后跟 `echo "exit=$?"`，管道退出码取 `tee`（恒 0）而非实验本身；脚本只有 `set -u`，无 `set -e` / `pipefail`。在临时副本中把一条断言注入为失败（`layout_lab.py` 以 `SystemExit(1)` 退出、18/19）后复跑 run_all.sh：步骤 1 仍打印 `exit=0`，末尾打印 `run_all: 全部完成`，脚本退出码 0——脚本无法检测实验失败。(b) 按“没有 `mlir-opt` 也能跑前两步”的口径模拟无 mlir-opt 机器（临时副本中把回退路径 `/usr/lib/llvm-18/bin/mlir-opt` 改写为不存在的路径、保留 python3 的受限 PATH）：前两步确实正常（19/19 + 14/14 写入 outputs/），但步骤 3–4 打印 `mlir-opt: command not found` 的同时仍报 `exit=0`，且 `outputs/layout_views_roundtrip.mlir` 与 `outputs/layout_views_canon.mlir` 被 `tee` 截断为 0 字节——若读者在仓库内运行，README 所称“已保存的真实输出”会被清空；步骤 5 打印“Verifier 按预期拒绝（exit=127）”，127 实为 command not found 而非 Verifier 拒绝（真实 Verifier 诊断被 `bad_load.txt` 里的 shell 报错覆盖）；脚本仍以“全部完成”、退出码 0 收尾。(c) 该句声称脚本打印的环境包含 “Linux aarch64”，但 run_all.sh 第 19–22 行只打印 Python / mlir-opt / numpy 版本，从不打印体系结构。建议：加 `set -o pipefail`（并用 `PIPESTATUS` 或不接管道报告退出码）、在无 mlir-opt 时跳过步骤 3–5 而不是清空输出、步骤 5 区分 127 与 Verifier 的 1。
- **置信度**：高（(a)(b) 均为注入实验复现，(b) 通过改写回退路径模拟，仅影响 mlir-opt 可用性，与真实无 mlir-opt 机器行为一致；(c) 为脚本直读）。

## 【存疑】

- 无。

## 【建议】

#### 1. 图 4 替代文本把「非连续视图 ⇒ 搬新数组」写成规则，与正文判据不一致，且必做练习本身就是反例
- **原文**：“对照实验：reshape 在连续视图上是零拷贝，在非连续视图上静默搬出新数组”
- **依据**：正文 §6 错误 3 给出的正确判据是“`reshape` 只在**新形状能被元信息表达**时才是视图”，但该替代文本（与图 4 SVG 标题“同一句 reshape(6)，连续视图零拷贝，非连续视图静默拷贝”、图内“T 不连续 → 必须拷贝出新数组”同口径）把判据简化成“连续 vs 非连续”。实测反例（numpy 1.26.4）：`np.arange(12, dtype=np.float32)[0:12:2]` 形状 (6,)、元素 strides (2,)、C-contiguous=False，但 `.reshape(2, 3)` 仍是视图（`np.shares_memory` = True，元素 strides (6, 2)）——这正是 §7 必做练习让读者构造的那类视图，教程未点破“非连续输入的 reshape 未必拷贝”。读者容易从图 4 概括出错误规则；建议在 §5.4 或练习提示处补一句（Day 59 Reshape 合法性正好展开此判据）。
- **置信度**：高（反例实测；属图注表述框架风险，正文结论本身无误）。

#### 2. 「一个 (6,) 的连续一维视图只有一种合法元信息」缺少作用域限定，与教程自己的「偏移≠非连续」教学相抵
- **原文**：“一个 `(6,)` 的连续一维视图只有一种合法元信息：`strides=(1,)`、`offset=0`。”
- **依据**：作为一般命题不成立：`np.arange(10, dtype=np.float32)[2:8]` 是形状 (6,)、strides (4,) 字节、`C_CONTIGUOUS=True` 的一维视图，相对 10 元素底层存储的 storage offset 为 2——即 (6,) 的连续一维视图可以有非零 offset。本句只在“必须覆盖 store 全部 6 个元素”的语境下成立（`T.reshape(6)` 是 store 的完整视图，故 offset 只能为 0），但 §3.3 与 §6 错误 2 刚强调“offset 不为 0 仍可连续”，此处绝对化表述易让读者退回“offset=0 才连续”的误解。建议补上“对这块 6 元素 store 的完整视图而言”之类的限定。
- **置信度**：高（反例实测；结合上下文可读出正确含义，故列为建议而非错误）。

#### 3. C-contiguity 判定的两条绝对化表述在退化维度上有已验证反例
- **原文**：“负 stride、stride 0 都不算 C-contiguous。”
- **依据**：numpy 的判定对“大小为 1 的维度”整体豁免（本行前一句已声明该豁免），因此绝对化表述存在反例，实测（numpy 1.26.4）：`np.arange(6)[::-1][2:3]` 形状 (1,)、strides (-4,)，`flags['C_CONTIGUOUS']` 为 True；`np.lib.stride_tricks.as_strided(a, shape=(3,1), strides=(1,100))` 也判 True——说明同行的“最后一维 stride 必须是 1”只在最后一维大小 > 1 时成立。建议两处都限定为“大小大于 1 的维度”，与 test_layout.py 中 (1,4)/(3,1) 边界用例的口径保持一致，避免读者用形状 (1,) 的数组自测时得出矛盾结论。
- **置信度**：高（两个反例均实测；教程前一句的豁免规则已部分覆盖，属表述精度问题）。

#### 4. 选做挑战第二问预设 stride-0 视图成立，但 MLIR strided 布局实测禁止 0 步长
- **原文**：“为什么这种视图对"消除冗余拷贝"的 Pass 反而是好事？”
- **依据**：在 Ubuntu LLVM 18.1.8 上构造 `memref.reinterpret_cast ... strides: [0, 1] : ... to memref<3x3xf32, strided<[0, 1]>>` 被 MLIR 拒绝，报错原文 `strides must not be zero`——禁令在 strided 布局属性层面（与 reinterpret_cast 这个入口无关，直接写 `memref<3xf32, strided<[0, 1]>>` 类型同样被拒）。第一问“Verifier 会不会接受？”是好的发现式提问（答案：不接受），但第二问把“这种视图”当作可构造对象来讨论其对 Pass 的好处，学生在 MLIR 里无法落地验证；该讨论只在允许 stride-0 的系统（如 numpy `np.broadcast_to`）里成立。建议加一句明示“MLIR 的 strided 布局拒绝 0 步长，第二问请放到 numpy 语境或概念层思考”。
- **置信度**：高（实测报错原文；不排除其他 MLIR 版本放行，但教程声明并实测的环境即 18.1.8）。

#### 5. 「元素 strides (3, 1) 与 strided<[1, 3]>（转置后）逐数一致」的示例配对错位
- **原文**：“今天实验里 Python 侧打印的"元素 strides `(3, 1)`"与 MLIR 侧 `strided<[1, 3]>`（转置后）逐数一致，靠的就是这个换算。”
- **依据**：`(3, 1)` 是视图 A（未转置）的元素 strides；与 MLIR `strided<[1, 3]>` 数值一致的是视图 T 转置后的 `(1, 3)`。按字面读“(3, 1) 与 [1, 3] 逐数一致”不成立（两个向量不相等）；正确配对是 A 的 (3,1) ↔ 源 `memref<2x3xf32>` 的隐含行主序布局、T 的 (1,3) ↔ `strided<[1, 3]>`。建议改为直接引用 T 的 `(1, 3)`，或同时给出两侧的对应关系，以免读者拿着输出里的两行数字对不上。
- **置信度**：高（数值关系直读；本意——字节/元素两种口径换算后才可比——可恢复，属示例配对失误而非结论错误）。

#### 6. §5.1 文件树漏列 code/make_images.py（实测可确定性重生成全部 4 张图）
- **原文**：“├── run_all.sh             # 一键复跑全部实验并保存真实输出”
- **依据**：`code/` 目录实际还有 `make_images.py`（约 27 KB），且在临时目录运行后输出的 4 张 SVG 与仓库冻结版逐字节一致（01–04 全部相同）——即图片可确定性重生成，这对读者是有用信息；但 §5.1 的目录树未用省略号、呈完整列表状却缺这一项，照树操作的读者不会知道 `images/` 可由脚本重建。建议补一行 `make_images.py`（顺带注明“可确定性重生成 images/ 下 4 张图”）。
- **置信度**：高（目录直读 + 重生成 diff 实测）。
