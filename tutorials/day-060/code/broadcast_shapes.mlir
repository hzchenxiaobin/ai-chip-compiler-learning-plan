// broadcast_shapes.mlir —— 第 60 天：MLIR shape dialect 里的 Broadcast 形状推导。
//
// 与 broadcast_lab.py 用同一组例子：
//   (2,3) 与 (3,)      → (2,3)          （贯穿例子）
//   (8,1000,256) 与 (256,) → (8,1000,256)（bias 例子）
//   (2,3) 与 (4,)      → 失配           （经典翻车）
//
// 三种「运行」方式：
//   1) 解析 + 验证 + 打印：
//        mlir-opt broadcast_shapes.mlir
//   2) 编译期形状推导（const_shape 折叠）：
//        mlir-opt --canonicalize broadcast_shapes.mlir
//      兼容的常量形状会被折成结果 const_shape——这就是 Shape 推导 Pass 的样子；
//      失配的 (2,3)+(4,) 却原样留着、不报静态错误（Verifier 缺口，见教程 5.4 节）。

module {
  // ---- ① 兼容：右对齐补 1，逐维取最大 —— canonicalize 折成 [2, 3] ----
  func.func @bc_row() -> !shape.shape {
    %a = shape.const_shape [2, 3] : !shape.shape
    %b = shape.const_shape [3] : !shape.shape
    %r = shape.broadcast %a, %b : !shape.shape, !shape.shape -> !shape.shape
    return %r : !shape.shape
  }

  // ---- ② 兼容：bias 相加，(8,1000,256) + (256,) —— canonicalize 折成 [8, 1000, 256] ----
  func.func @bc_bias() -> !shape.shape {
    %a = shape.const_shape [8, 1000, 256] : !shape.shape
    %b = shape.const_shape [256] : !shape.shape
    %r = shape.broadcast %a, %b : !shape.shape, !shape.shape -> !shape.shape
    return %r : !shape.shape
  }

  // ---- ③ 失配：(2,3) + (4,) —— canonicalize 不折叠也不报错（原样保留）----
  // numpy 在这一步直接抛 ValueError；mini.broadcast 也静态报错；
  // shape.broadcast 的错误要等运行期才暴露——静态可见的失配该静态拦（教程 5.4 节）。
  func.func @bc_conflict() -> !shape.shape {
    %a = shape.const_shape [2, 3] : !shape.shape
    %b = shape.const_shape [4] : !shape.shape
    %r = shape.broadcast %a, %b : !shape.shape, !shape.shape -> !shape.shape
    return %r : !shape.shape
  }
}
