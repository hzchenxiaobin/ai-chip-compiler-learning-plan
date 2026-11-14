#!/usr/bin/env python3
"""第 156 天：整理关键 Pass——四份 Pass 文档（五要素＋前后 IR）。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

DOCS = {
"shape-inference": """# Pass 文档：Shape 推导（S2 内嵌）

## 输入
  图 IR 的节点（const/arg/reshape）
## 输出
  每个 memref 的 (M, K, N) 尺寸
## 合法性
  三来源各管一段：const.shape 属性｜arg.tensor 类型正则｜reshape.new_shape
  推断不出 → E202 拒收（带节点 id）
## 收益
  shape 从图读出——不猜（D122 的设计决策）
## 限制
  只支持静态 shape；动态（?）走 D128 的描述符路径
## 前后 IR 示例
  前：const shape=[3,6] → 后：M=3, K=6（S2 签名用）
  出处：D122 loop_lower._infer_shape／D143 shape_of
""",
"fusion": """# Pass 文档：融合（S1 闸4）

## 输入
  matmul→add(const bias)→relu 的单链（单使用者）
## 输出
  fused_matmul_bias_relu 单节点
## 合法性
  结构门：单使用者✓＋bias 是 const✓（多使用者/非 const 拒绝）
## 收益
  图 7→5 节点（少两个中间结果的存取）
  教学规模收益归零（cache 命中）——结构结论保持
## 限制
  输出多使用者不融（D83 T10）；bias 非常量不融
## 前后 IR 示例
  前：%7=matmul %6,%12  %9=add %7,%8  %10=relu %9
  后：%10=fused_matmul_bias_relu %6,%12,%8
  出处：D121 闸4／D83 T09
""",
"layout": """# Pass 文档：布局简化（S1 闸2）

## 输入
  transpose(const) 模式
## 输出
  编译期转置后的 const（值重排、类型更新）
## 合法性
  输入必须是 const（动态张量的 transpose 保留——运行时才知道数据）
## 收益
  权重搬进编译期——运行时零数据移动
## 限制
  只折 transpose(const)；transpose(动态) 保留
## 前后 IR 示例
  前：%4=transpose %3 perm=[1,0]（%3 是 const）
  后：%12=const shape=[6,3] values=[转置后的值]
  出处：D121 闸2（D64/65 的语义）
""",
"tiling": """# Pass 文档：Tiling（S2 块循环生成）

## 输入
  朴素循环 IR＋tile (TM,TN,TK) 参数
## 输出
  块循环 IR（外层 tile 壳＋内层点循环）
## 合法性
  validate_tile：三元组＋整数＋≥1（5 负例拒收）
## 收益
  tile 参数真实生效（产物差异可 grep：phi 7 vs 4）
  性能：教学版 0.3×（重复计算抵消——负优化的诚实记录）
## 限制
  教学版点循环用全局边界（幂等正确但重复计算）；
  完整版（块内 min 钳制）是 future F-01 的后续
## 前后 IR 示例
  前：scf.for %i = 0 to 160 step 1 { ... }
  后：scf.for %i0 = 0 to 160 step 64 { scf.for %i = %i0 to 160 ... } }
  出处：D143~D146／D151（性能反例）
""",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for name, doc in DOCS.items():
        open(os.path.join(OUT, f"pass-{name}.md"), "w").write(doc)
        n += 1
        # 五要素检查
        for elem in ("## 输入", "## 输出", "## 合法性", "## 收益", "## 限制"):
            assert elem in doc, f"{name} 缺 {elem}"
    checks = [
        ("四份 Pass 文档", n == 4),
        ("五要素齐全", True),
        ("前后 IR 示例", all("示例" in d for d in DOCS.values())),
        ("出处可追溯", all("出处" in d for d in DOCS.values())),
    ]
    for nm, okk in checks:
        print(f"  [{'PASS' if okk else 'FAIL'}] {nm}")
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
