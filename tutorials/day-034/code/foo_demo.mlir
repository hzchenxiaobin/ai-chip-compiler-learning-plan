// standalone.foo：I32 → I32 的无副作用算子
func.func @main(%arg0: i32) -> i32 {
  %0 = standalone.foo %arg0 : i32
  %1 = standalone.foo %0 : i32
  return %1 : i32
}
