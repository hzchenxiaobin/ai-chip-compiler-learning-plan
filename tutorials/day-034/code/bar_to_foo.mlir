module {
  func.func @bar() {
    return
  }
  func.func @other(%arg0: i32) -> i32 {
    %0 = standalone.foo %arg0 : i32
    return %0 : i32
  }
}
