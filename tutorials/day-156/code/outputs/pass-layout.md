# Pass 文档：布局简化（S1 闸2）

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
