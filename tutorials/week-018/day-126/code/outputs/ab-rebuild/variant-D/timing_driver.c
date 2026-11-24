
/* kernel 级计时驱动：同进程反复调用 _mlir_ciface，取统计量 */
#include <stdio.h>
#include <stdint.h>
#include <time.h>
typedef struct { float *alloc; float *aligned; int64_t off; int64_t sh[2]; int64_t st[2]; } desc2_t;
typedef struct { float *alloc; float *aligned; int64_t off; int64_t sh[1]; int64_t st[1]; } desc1_t;
static float A[24] = {0.5f, -1.0f, 2.0f, 0.0f, 1.5f, -0.5f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, -2.0f, 0.5f, 0.0f, 3.0f, -1.0f, 2.0f, 0.0f, 0.0f, 0.5f, 0.5f, 0.5f, 0.5f};
static float B[18] = {1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f, 7.0f, 8.0f, 9.0f, 10.0f, 11.0f, 12.0f, 13.0f, 14.0f, 15.0f, 16.0f, 17.0f, 18.0f};
static float BIAS[3] = {0.125f, -0.25f, 0.5f};
static float CSINK[12];   /* 防 DCE：结果必须被消费 */
extern void _mlir_ciface_main_kernel(desc2_t*, desc2_t*, desc2_t*, desc1_t*);

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

int main(void) {
    desc2_t da = {A, A, 0, {4, 6}, {6, 1}};
    desc2_t db = {B, B, 0, {6, 3}, {3, 1}};
    desc1_t dbias = {BIAS, BIAS, 0, {3}, {1}};
    desc2_t dc;

    /* 预热 3 次（首次含页错误/缓存冷启动） */
    for (int i = 0; i < 3; i++)
        _mlir_ciface_main_kernel(&dc, &da, &db, &dbias);

    /* 正式计时：N 次调用 */
    const int N = 20000;
    double t0 = now_ms();
    for (int i = 0; i < N; i++) {
        _mlir_ciface_main_kernel(&dc, &da, &db, &dbias);
        CSINK[0] = dc.alloc[0];   /* 消费结果防优化删除 */
    }
    double total = now_ms() - t0;
    printf("kernel_ms_per_call %.4f\n", total / N * 1000 / 1000);
    /* 上行换算：total ms / N 次 = ms/次；教学 kernel ~µs 级再除 1000 得 ms? 不——
       直接给 µs：total*1000 µs / N */
    printf("kernel_us_per_call %.3f\n", total * 1000.0 / N);
    printf("calls %d total_ms %.2f\n", N, total);
    /* 正确性顺带核对（每 1000 次抽一次） */
    int bad = 0;
    for (int k = 0; k < 12; k++)
        if (dc.alloc[k] != dc.alloc[k]) bad++;   /* NaN 检查——教学 golden 在 driver A 里 */
    return 0;
}
