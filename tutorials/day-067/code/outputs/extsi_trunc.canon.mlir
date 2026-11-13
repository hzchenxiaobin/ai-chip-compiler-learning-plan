module {
  func.func @extsi_trunc(%arg0: i32) -> i32 {
    %0 = arith.trunci %arg0 : i32 to i8
    %1 = arith.extsi %0 : i8 to i32
    return %1 : i32
  }
}

