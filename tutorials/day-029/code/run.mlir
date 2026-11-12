// run.mlir —— 用 mlir-cpu-runner 真正"跑起来"的最小程序
//
// checkin 保持原样（不先优化），另加一个 main 调用它：
//   main = checkin(10) = (10 + 0) * 1 + (2 * 3) = 16
//
// 两步执行（本机 Ubuntu 的 mlir-cpu-runner 不注册 func 方言，需要先 lower）：
//   mlir-opt-18 run.mlir --convert-func-to-llvm --convert-arith-to-llvm -o run.llvm.mlir
//   mlir-cpu-runner-18 run.llvm.mlir --entry-point-result=i32

module {
  func.func @checkin(%x: i32) -> i32 {
    %c0 = arith.constant 0 : i32
    %c1 = arith.constant 1 : i32
    %c2 = arith.constant 2 : i32
    %c3 = arith.constant 3 : i32
    %a = arith.addi %x, %c0 : i32
    %b = arith.muli %a, %c1 : i32
    %d = arith.muli %c2, %c3 : i32
    %r = arith.addi %b, %d : i32
    return %r : i32
  }

  func.func @main() -> i32 {
    %x = arith.constant 10 : i32
    %r = func.call @checkin(%x) : (i32) -> i32
    return %r : i32
  }
}
