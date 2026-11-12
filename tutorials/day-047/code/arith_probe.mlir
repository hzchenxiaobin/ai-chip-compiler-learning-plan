// 第 47 天上游探针：常量折叠不是 mini 的发明——上游 arith 方言的
// addf/mulf 早就带着同款 fold 钩子。交给 mlir-opt-18 -canonicalize：
//
// 命令：mlir-opt-18 -canonicalize arith_probe.mlir
//
//   @both_const ：arith.addf(1.0, 2.0) → arith.constant 3.0（同款折叠）；
//   @uniquing   ：两条都折出 3.0 的 addf —— 上游 OperationFolder 同样
//                 只物化一个 arith.constant 3.0（同款去重）；
//   @from_arg   ：操作数来自入口参数 —— 同样不折（同款保守性）。
//
// 实测输出见 run_all.sh 第 5 步与教程 5.5 节：mini 的行为与上游逐项对齐。
module {
  func.func @both_const() -> f32 {
    %a = arith.constant 1.0 : f32
    %b = arith.constant 2.0 : f32
    %s = arith.addf %a, %b : f32
    func.return %s : f32
  }
  func.func @uniquing() -> (f32, f32) {
    %a1 = arith.constant 1.0 : f32
    %b1 = arith.constant 2.0 : f32
    %s1 = arith.addf %a1, %b1 : f32
    %a2 = arith.constant 0.5 : f32
    %b2 = arith.constant 2.5 : f32
    %s2 = arith.addf %a2, %b2 : f32
    func.return %s1, %s2 : f32, f32
  }
  func.func @from_arg(%x: f32, %y: f32) -> f32 {
    %s = arith.addf %x, %y : f32
    func.return %s : f32
  }
}
