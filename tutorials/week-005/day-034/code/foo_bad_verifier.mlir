// 探针：块参数本来就是 i64 —— 语法层完全自洽，能通过解析；
// 轮到 standalone.foo 自己的 Verifier 出场：operand #0 必须是 i32
func.func @main(%arg0: i64) -> i64 {
  %0 = standalone.foo %arg0 : i64
  return %0 : i64
}
