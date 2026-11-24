// 第 46 天上游探针：同样的四条恒等式，交给 mlir-opt-18 内置的 arith
// 方言（标量版，f32/i32）跑 -canonicalize，看上游的取舍和 mini 是否一致。
// 命令：mlir-opt-18 -canonicalize arith_probe.mlir
//
// 期望观察（实测结果见 run_all.sh 第 5 步与教程 5.5 节）：
//   @addf_pos  ：arith.addf %x, +0.0 —— 与 mini 相同的符号零问题；
//   @addf_neg  ：arith.addf %x, -0.0 —— 严格恒等；
//   @mulf_one  ：arith.mulf %x, 1.0  —— 严格恒等；
//   @mulf_zero ：arith.mulf %x, 0.0  —— NaN/Inf 不可越；
//   @addi_zero ：arith.addi %x, 0    —— 整数没有符号零，恒等必然安全。
module {
  func.func @addf_pos(%x: f32) -> f32 {
    %c = arith.constant 0.0 : f32
    %a = arith.addf %x, %c : f32
    func.return %a : f32
  }
  func.func @addf_neg(%x: f32) -> f32 {
    %c = arith.constant -0.0 : f32
    %a = arith.addf %x, %c : f32
    func.return %a : f32
  }
  func.func @mulf_one(%x: f32) -> f32 {
    %c = arith.constant 1.0 : f32
    %m = arith.mulf %x, %c : f32
    func.return %m : f32
  }
  func.func @mulf_zero(%x: f32) -> f32 {
    %c = arith.constant 0.0 : f32
    %m = arith.mulf %x, %c : f32
    func.return %m : f32
  }
  func.func @addi_zero(%x: i32) -> i32 {
    %c = arith.constant 0 : i32
    %a = arith.addi %x, %c : i32
    func.return %a : i32
  }
}
