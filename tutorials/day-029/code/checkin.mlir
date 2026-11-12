// checkin.mlir —— 第 29 天的"打卡"示例
//
// 一个最小 MLIR 函数：checkin(x) = (x + 0) * 1 + (2 * 3)
// 三个冗余正好是第一阶段手写过的两类 Pass：
//   x + 0  → 代数化简（Day 23 的 add(x,0)→x）
//   a * 1  → 代数化简（Day 23 的 mul(x,1)→x）
//   2 * 3  → 常量计算（Day 24 的编译期求值）
// 今天交给真正的 MLIR canonicalize 来做。
//
// 上面的 CHECK 注释是给 FileCheck 的"考卷"：
// 测试方式（lit 不可用时手动执行 lit 底层做的事）：
//   mlir-opt-18 checkin.mlir --canonicalize | FileCheck-18 checkin.mlir

// CHECK-LABEL: func.func @checkin(
// CHECK-SAME: %[[ARG:.*]]: i32
// CHECK-NOT: arith.muli
// CHECK: %[[C6:.*]] = arith.constant 6 : i32
// CHECK: %[[R:.*]] = arith.addi %[[ARG]], %[[C6]] : i32
// CHECK: return %[[R]] : i32

module {
  func.func @checkin(%x: i32) -> i32 {
    %c0 = arith.constant 0 : i32
    %c1 = arith.constant 1 : i32
    %c2 = arith.constant 2 : i32
    %c3 = arith.constant 3 : i32
    %a = arith.addi %x, %c0 : i32     // x + 0  → 冗余
    %b = arith.muli %a, %c1 : i32     // a * 1  → 冗余
    %d = arith.muli %c2, %c3 : i32    // 2 * 3  → 常量
    %r = arith.addi %b, %d : i32
    return %r : i32
  }
}
