# Pass 文档：Tiling（S2 块循环生成）

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
