// 探针：mini 还没有算子，却写了一个 mini.foo。
// 拿它问两个工具：
//   mini-opt    → mini 方言已注册，报"op 未知"（户口本有，住户名单里没有 foo）
//   mlir-opt-18 → mini 方言根本没注册，报"Dialect not found"（连户口本都没有）
module {
  func.func @ghost() {
    %0 = mini.foo() : () -> ()
    return
  }
}
