# Pass 文档：融合（S1 闸4）

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
