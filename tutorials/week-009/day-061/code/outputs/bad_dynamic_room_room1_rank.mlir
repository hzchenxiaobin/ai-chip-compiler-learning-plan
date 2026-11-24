// bad_dynamic.mlir —— 第 61 天错误博物馆：同一处静态失配，三种待遇。
//
// 房间 1：秩错误 —— 一维操作数喂给 matmul，Verifier 静态拦截
// 房间 2：静态 K 失配 + M 也静态 —— Verifier 静态拦截
// 房间 3：静态 K 失配 + M 动态   —— Verifier 放行（exit=0）！
//         4 vs 3 明明都写在类型里，但一个 ? 让整张静态检查网失明。
//         错误要么等运行期检查（k_check.mlir 的路线），
//         要么静默产出错误结果（k_hazard.mlir 的路线）。
//
// 运行：整个文件被拒（第一条错误就退出）；逐房间的单独验证见 run_all.sh，
//       三个房间的单独结果保存在 outputs/bad_dynamic_room*.txt。
//
// 实测（LLVM 18.1.8）：房间 1、2 exit=1；房间 3 exit=0。
// tensor 版同样验证过：房间 3 的 tensor 双写法（outs 静态/动态）同样 exit=0。

// ---- room1_rank（秩错误，Verifier 拦截）----
func.func @room1_rank(%a: memref<?xf32>, %b: memref<3x2xf32>,
                      %o: memref<?x2xf32>) {
  linalg.matmul ins(%a, %b : memref<?xf32>, memref<3x2xf32>)
                outs(%o : memref<?x2xf32>)
  return
}

