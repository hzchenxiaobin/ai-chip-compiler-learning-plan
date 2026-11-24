// 第 118 天路线 4：MCJIT 驱动——真实 JIT 引擎路径。
// 与 lli 的区别：lli 是"黑盒工具"，这里把 lli 内部做的事（parse -> opt -> MCJIT
// -> 查符号 -> 执行）用 LLVM C++ API 手写出来，每一步都可见、可插桩。
// 这正是 MLIR ExecutionEngine（mlir-runner 的心脏）在底层走的路。
#include <cstdio>
#include <cstring>
#include <memory>
#include <vector>

#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/Module.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/ExecutionEngine/ExecutionEngine.h"
#include "llvm/ExecutionEngine/MCJIT.h"
#include "llvm/ExecutionEngine/GenericValue.h"
#include "llvm/ExecutionEngine/SectionMemoryManager.h"
#include "llvm/IR/Verifier.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/TargetSelect.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Transforms/Utils.h"
#include "llvm/Passes/PassBuilder.h"

// 与 driver.c 相同的 56B 描述符
struct Desc {
    float *alloc;
    float *aligned;
    int64_t off;
    int64_t sh[2];
    int64_t st[2];
};

static const float kA[24] = {
    0.5f, -1.0f, 2.0f, 0.0f, 1.5f, -0.5f,
    1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f,
    -2.0f, 0.5f, 0.0f, 3.0f, -1.0f, 2.0f,
    0.0f, 0.0f, 0.5f, 0.5f, 0.5f, 0.5f};
static const float kB[18] = {
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18};
static const float kGolden[12] = {
    22.0f, 24.5f, 27.0f, 51.0f, 57.0f, 63.0f,
    49.0f, 51.5f, 54.0f, 23.0f, 25.0f, 27.0f};

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "用法: %s <input.ll>\n", argv[0]); return 2; }

    llvm::InitializeNativeTarget();
    llvm::InitializeNativeTargetAsmPrinter();

    // 1. parse .ll（等价 lli 的第一步）
    llvm::LLVMContext ctx;
    llvm::SMDiagnostic diag;
    auto mod = llvm::parseIRFile(argv[1], diag, ctx);
    if (!mod) { diag.print(argv[1], llvm::errs()); return 1; }
    if (llvm::verifyModule(*mod, &llvm::errs())) {
        fprintf(stderr, "verify 失败\n"); return 1;
    }

    // 2. 构建 MCJIT（默认 -O2 代码生成；IR 级优化留给上游，见 README 5.4 讨论）
    llvm::EngineBuilder eb(std::move(mod));
    std::string err;
    auto *ee = eb.setErrorStr(&err)
                 .setEngineKind(llvm::EngineKind::JIT)
                 .setMCJITMemoryManager(std::make_unique<llvm::SectionMemoryManager>())
                 .create();
    if (!ee) { fprintf(stderr, "创建 MCJIT 失败: %s\n", err.c_str()); return 1; }
    ee->finalizeObject();

    // 3. 查符号——JIT 的核心能力：按名字拿到内存中的函数地址
    uint64_t addr = ee->getFunctionAddress("_mlir_ciface_gemm");
    if (!addr) { fprintf(stderr, "符号 _mlir_ciface_gemm 未找到\n"); return 1; }

    // 4. 按 C 合同调用（与 driver.c / ctypes 完全同一份 ABI 约定）
    auto *ciface = reinterpret_cast<void (*)(Desc *, Desc *, Desc *)>(addr);
    Desc da = { const_cast<float *>(kA), const_cast<float *>(kA), 0, {4, 6}, {6, 1} };
    Desc db = { const_cast<float *>(kB), const_cast<float *>(kB), 0, {6, 3}, {3, 1} };
    Desc dc = {};
    ciface(&dc, &da, &db);

    // 5. 与 golden 逐点对照
    int bad = 0;
    for (int k = 0; k < 12; k++) {
        printf("C[%d]=%.2f\n", k, dc.alloc[k]);
        if (dc.alloc[k] != kGolden[k]) bad++;
    }
    printf("%s\n", bad == 0 ? "12/12 点与 golden 一致（MCJIT）" : "存在不一致点");
    delete ee;
    return bad == 0 ? 0 : 1;
}
