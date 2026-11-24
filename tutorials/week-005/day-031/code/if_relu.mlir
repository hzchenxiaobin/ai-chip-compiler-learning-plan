// 第 31 天主示例③：同一个 ReLU 的第三种写法——scf.if。
// 它是「一条 Operation 持有 2 个 Region」的最小例子：then 一个、else 一个，
// 每个 Region 各 1 个 Block、各 1 个终结符 scf.yield。
// 三种写法语义相同：maxsi（Day 30）/ cf.cond_br（branch_relu.mlir）/ scf.if（本文件）。
module {
  func.func @if_relu(%x: i32) -> i32 {
    %c0 = arith.constant 0 : i32
    %pos = arith.cmpi sgt, %x, %c0 : i32
    %r = scf.if %pos -> (i32) {
      scf.yield %x : i32
    } else {
      scf.yield %c0 : i32
    }
    return %r : i32
  }
}
