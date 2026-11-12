// k_blind.mlir —— 第 62 天：藏在 ? 后面的 K 失配（第 61 天「失明」现象的复刻）。
//
// 类型里明明白白写着 K=4（A 的第 1 维）和 K=3（B 的第 0 维），
// 但 M 是 ? —— 静态推断整体失效，Verifier 放行（本机实测 exit=0）。
//
// 今天的对照实验（5.4 节）：
//   python3 specialize.py k_blind.mlir --specialize-shape "a=2x4,b=3x2" --force ...
//   把 M=? 钉成 2 之后，同一处 K 失配被 Verifier 当场拦下
//   （exit=1：operand #1 ... dimension #0 to be 4, but found 3）——
//   特化不只为了性能：它把静态检查网重新点亮。
//
// 运行方式：
//   mlir-opt k_blind.mlir            # 动态版：放行（? 让检查失明）
//   特化后再跑 mlir-opt               # 静态版：拒绝（K 4 vs 3 被拦）

module {
  func.func @matmul_blind(%a: memref<?x4xf32>, %b: memref<3x2xf32>,
                          %o: memref<?x2xf32>) {
    linalg.matmul ins(%a, %b : memref<?x4xf32>, memref<3x2xf32>)
                  outs(%o : memref<?x2xf32>)
    return
  }
}
