// cast_chain.mlir —— 第 67 天静态 IR：cast 家族交给 --canonicalize 的真实裁决。
// 六个函数全部合法（@extf_same 的「同型扩展」与 @bitcast_ui8 的 ui8 类型
// 会被 Verifier 直接拒绝，放在主实验 cast_elim_lab.py 里单独探针）。
//
// 预期（本机 LLVM 18.1.8 实测）：
//   @bitcast_same    f32→f32            消除为 return %arg0
//   @trunc_ext       f16→f32→f16        原样保留 2 op（stock 无浮点回环折叠）
//   @ext_trunc       f32→f16→f32        原样保留 2 op（有损，正确拒绝）
//   @truncsi_extsi   i8→i32→i8          消除为 return %arg0（整数回环有折叠）
//   @extsi_trunc     i32→i8→i32         原样保留 2 op（有损，正确拒绝）
//   @bitcast_chain   f32→i32→f32        消除为 return %arg0（双射重解释）

module {
  func.func @bitcast_same(%x: f32) -> f32 {
    %r = arith.bitcast %x : f32 to f32
    return %r : f32
  }
  func.func @trunc_ext(%x: f16) -> f16 {
    %e = arith.extf %x : f16 to f32
    %t = arith.truncf %e : f32 to f16
    return %t : f16
  }
  func.func @ext_trunc(%x: f32) -> f32 {
    %t = arith.truncf %x : f32 to f16
    %e = arith.extf %t : f16 to f32
    return %e : f32
  }
  func.func @truncsi_extsi(%x: i8) -> i8 {
    %e = arith.extsi %x : i8 to i32
    %t = arith.trunci %e : i32 to i8
    return %t : i8
  }
  func.func @extsi_trunc(%x: i32) -> i32 {
    %t = arith.trunci %x : i32 to i8
    %e = arith.extsi %t : i8 to i32
    return %e : i32
  }
  func.func @bitcast_chain(%x: f32) -> f32 {
    %b1 = arith.bitcast %x : f32 to i32
    %b2 = arith.bitcast %b1 : i32 to f32
    return %b2 : f32
  }
}
