// probe_cast_roundtrip.mlir —— 探针 1（反例 R1：精度语义）
//
// f32 -> f16 -> f32 的 Cast 往返：类型一进一出「对消」，值上看似恒等。
// 但 f16 只有 10 位尾数（f32 有 23 位），roundtrip 会丢位——
// 这不是无操作 Cast，不能按「类型对消」折叠。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt probe_cast_roundtrip.mlir --canonicalize
//     → truncf + extf 原样保留（共 2 个 cast），stock 管道不折叠。

func.func @cast_roundtrip(%x: f32) -> f32 {
  %h = arith.truncf %x : f32 to f16
  %r = arith.extf %h : f16 to f32
  return %r : f32
}
