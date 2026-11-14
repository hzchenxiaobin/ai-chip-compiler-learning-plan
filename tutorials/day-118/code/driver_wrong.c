/* 第 118 天 TP5 错误示范：把"外部预备 C 数组"当输出缓冲区——经典误区。
 * 误区：以为 kernel 会把结果写进调用方给的缓冲区（很多运行库的 out 参数确实如此）。
 * 事实：@gemm 的输出是 memref.alloc() 的**新**缓冲区，包装只是把描述符
 *       （含 malloc 指针）store 回 out。调用方若给一个 alloc=NULL/未初始化的
 *       desc_t 且从不读回 dc.alloc，就会访问空指针。
 * 本程序故意解引用 dc.alloc（未经 kernel 填充的原始值），预期崩溃。
 */
#include <stdio.h>
#include <stdint.h>

typedef struct {
    float   *alloc;
    float   *aligned;
    int64_t  off;
    int64_t  sh[2];
    int64_t  st[2];
} desc_t;

extern void _mlir_ciface_gemm(desc_t *out, desc_t *a, desc_t *b);

int main(void)
{
    static float A[24], B[18];          /* 数据无关紧要：错误在读回 */
    static float C[12];                 /* 误区核心：以为 kernel 会写这里 */
    desc_t da = { A, A, 0, {4, 6}, {6, 1} };
    desc_t db = { B, B, 0, {6, 3}, {3, 1} };
    desc_t dc = { C, C, 0, {4, 3}, {3, 1} };  /* 把 C 数组填进 desc 传出去 */

    _mlir_ciface_gemm(&dc, &da, &db);

    /* 错误：kernel 的结果在它自己 malloc 的缓冲区（已随包装覆盖 dc.alloc），
     * 这里打印的是"根本没被写过"的 C 数组 —— 全 0（静态区）。
     * 若调用方没把 dc 当输出读回，就永远拿不到结果。 */
    printf("C 数组 = %.2f %.2f %.2f ...（全 0：kernel 从未写这里）\n", C[0], C[1], C[2]);
    printf("dc.alloc=%p（kernel malloc 的新缓冲区，不是 C）\n", (void *)dc.alloc);
    return 0;
}
