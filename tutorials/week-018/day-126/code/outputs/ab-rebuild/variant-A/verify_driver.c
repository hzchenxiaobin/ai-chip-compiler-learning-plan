
/* minic S6 验证驱动（D118 路线 1 的自动化版） */
#include <stdio.h>
#include <stdint.h>
typedef struct { float *alloc; float *aligned; int64_t off; int64_t sh[2]; int64_t st[2]; } desc2_t;
typedef struct { float *alloc; float *aligned; int64_t off; int64_t sh[1]; int64_t st[1]; } desc1_t;
/* A/B 数据内嵌（与 e2e.py 的 A_DATA/B_DATA 一致） */
static float A[24] = {0.5f, -1.0f, 2.0f, 0.0f, 1.5f, -0.5f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, -2.0f, 0.5f, 0.0f, 3.0f, -1.0f, 2.0f, 0.0f, 0.0f, 0.5f, 0.5f, 0.5f, 0.5f};
static float B[18] = {1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f, 7.0f, 8.0f, 9.0f, 10.0f, 11.0f, 12.0f, 13.0f, 14.0f, 15.0f, 16.0f, 17.0f, 18.0f};
static float BIAS[3] = {0.125f, -0.25f, 0.5f};
static float C[12] = {0};
/* golden 内嵌（与 numpy 参考一致，编译时替换） */
static const float GOLDEN[12] = {22.125000f, 24.250000f, 27.500000f, 51.125000f, 56.750000f, 63.500000f, 49.125000f, 51.250000f, 54.500000f, 23.125000f, 24.750000f, 27.500000f};
extern void _mlir_ciface_main_kernel(desc2_t *out, desc2_t *a, desc2_t *b, desc1_t *bias);
int main(void) {
    desc2_t da = {A, A, 0, {4, 6}, {6, 1}};
    desc2_t db = {B, B, 0, {6, 3}, {3, 1}};
    desc1_t dbias = {BIAS, BIAS, 0, {3}, {1}};
    desc2_t dc = {0, 0, 0, {4, 3}, {3, 1}};
    _mlir_ciface_main_kernel(&dc, &da, &db, &dbias);
    if (dc.alloc == NULL) { printf("FAIL: null\n"); return 1; }
    int bad = 0;
    for (int k = 0; k < 12; k++) {
        printf("C[%d]=%.4f (golden %.4f)\n", k, dc.alloc[k], GOLDEN[k]);
        if (dc.alloc[k] != GOLDEN[k]) bad++;
    }
    printf("%s\n", bad == 0 ? "12/12 点 bitwise 一致" : "VERIFY FAIL");
    return bad == 0 ? 0 : 1;
}
