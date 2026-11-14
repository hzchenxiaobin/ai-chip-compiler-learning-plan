/* 第 118 天路线 1：AOT 静态链接驱动。
 * 与 D115/D116 的 ctypes 驱动同构，但这次全部在 C 里：
 *   1. 栈上构造 A/B 数据与三份描述符（布局与 D115 的 56B 契约一致）
 *   2. 按 C 合同调 _mlir_ciface_gemm(out, a, b)   —— D117 导出时
 *      llvm.emit_c_interface 自动生成的包装（D116 手写包装的真工具版）
 *   3. 关键语义：@gemm 内部 memref.alloc() 会 malloc 新缓冲区，包装把
 *      返回的描述符 store 进 out 指向的 dc —— 结果在 dc.alloc 里，
 *      不在外部预备的 C 数组里（这是今天最重要的执行语义，README 6.1）
 */
#include <stdio.h>
#include <stdint.h>

typedef struct {
    float   *alloc;    /* 0  : 分配指针                    */
    float   *aligned;  /* 8  : 对齐指针（无显式对齐时 = alloc） */
    int64_t  off;      /* 16 : 元素偏移                    */
    int64_t  sh[2];    /* 24 : sizes                       */
    int64_t  st[2];    /* 40 : strides（元素个数，非字节）    */
} desc_t;              /* 合计 56B，与 D115 教学口径一致      */

extern void _mlir_ciface_gemm(desc_t *out, desc_t *a, desc_t *b);

static float A[24] = {
    0.5f, -1.0f, 2.0f, 0.0f, 1.5f, -0.5f,
    1.0f,  1.0f, 1.0f, 1.0f, 1.0f,  1.0f,
   -2.0f,  0.5f, 0.0f, 3.0f, -1.0f, 2.0f,
    0.0f,  0.0f, 0.5f, 0.5f, 0.5f,  0.5f
};
static float B[18] = {
    1.0f,  2.0f,  3.0f,  4.0f,  5.0f,  6.0f,
    7.0f,  8.0f,  9.0f, 10.0f, 11.0f, 12.0f,
   13.0f, 14.0f, 15.0f, 16.0f, 17.0f, 18.0f
};

int main(void)
{
    desc_t da = { A, A, 0, {4, 6}, {6, 1} };
    desc_t db = { B, B, 0, {6, 3}, {3, 1} };
    desc_t dc = { 0, 0, 0, {4, 3}, {3, 1} };   /* alloc 留空：等 kernel 填 */

    _mlir_ciface_gemm(&dc, &da, &db);

    /* 结果在 dc.alloc 指向的 malloc 缓冲区；栈上 C 数组从不存在 */
    if (dc.alloc == NULL) { fprintf(stderr, "kernel 未返回缓冲区\n"); return 1; }

    int bad = 0;
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 3; j++) {
            printf("C[%d]=%.2f\n", i * 3 + j, dc.alloc[i * 3 + j]);
        }
    }
    /* 与 golden 逐点对照（golden 值写死在源码里，来自 gen_golden.py） */
    static const float golden[12] = {
        22.0f, 24.5f, 27.0f,  51.0f, 57.0f, 63.0f,
        49.0f, 51.5f, 54.0f,  23.0f, 25.0f, 27.0f
    };
    for (int k = 0; k < 12; k++)
        if (dc.alloc[k] != golden[k]) bad++;
    printf("%s\n", bad == 0 ? "12/12 点与 golden 一致" : "存在不一致点");
    return bad == 0 ? 0 : 1;
}
