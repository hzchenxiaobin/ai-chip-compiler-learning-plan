# Pass 文档：Shape 推导（S2 内嵌）

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
