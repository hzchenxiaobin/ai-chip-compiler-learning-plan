// config_bench.cpp —— 第 97 天：多配置正确性与性能实验
//
// 构建：g++ -std=c++17 -O3 -ffp-contract=off -o config_bench config_bench.cpp
//
// 用法：
//   ./config_bench suite                        # 5 个 shape × 6 配置的正确性套件（逐位比对）
//   ./config_bench bench M N K warm repeats     # 性能实验：先过正确性门，再 warmup+计时
//   ./config_bench cold idx M N K               # 新进程里冷启动跑 1 次指定配置（对照用）
//   ./config_bench env                          # 打印编译器/构建期环境信息
//
// 配置空间：2 种内层循环顺序 × 3 种 Tile 尺寸 = 6 个配置
//   i-j-k：内层 i→j→k，k 最内层（B 沿 k 跨步访存）
//   i-k-j：内层 i→k→j，j 最内层（B、C 沿 j 连续 → 可向量化，D96 的 reorder）
// 两种内核共享同一 tile 外壳（i0/j0/k0 + min 钳制，D95 的遗产），只交换最内两层。

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;

struct Config {
    const char* name;
    int order;  // 0: 内层 i-j-k；1: 内层 i-k-j
    int TM, TN, TK;
};

const Config kConfigs[] = {
    {"ijk-32",  0, 32, 32, 32},
    {"ijk-64",  0, 64, 64, 64},
    {"ijk-128", 0, 128, 128, 128},
    {"ikj-32",  1, 32, 32, 32},
    {"ikj-64",  1, 64, 64, 64},
    {"ikj-128", 1, 128, 128, 128},
};
constexpr int kNumConfigs = static_cast<int>(sizeof(kConfigs) / sizeof(kConfigs[0]));

// ---------- 参考实现：朴素三重循环，k 升序累加 ----------
void naive_ref(const float* A, const float* B, float* C, int M, int N, int K) {
    for (int i = 0; i < M; i++)
        for (int j = 0; j < N; j++) {
            float c = 0.0f;
            for (int k = 0; k < K; k++) c += A[i * (size_t)K + k] * B[k * (size_t)N + j];
            C[i * (size_t)N + j] = c;
        }
}

// ---------- 被测内核：tile 外壳 + min 钳制，内层顺序由模板参数决定 ----------
template <int ORDER>
__attribute__((noinline)) void tiled_matmul(const float* A, const float* B, float* C,
                                            int M, int N, int K, int TM, int TN, int TK) {
    for (int i0 = 0; i0 < M; i0 += TM)
        for (int j0 = 0; j0 < N; j0 += TN)
            for (int k0 = 0; k0 < K; k0 += TK) {
                const int ihi = std::min(i0 + TM, M);  // D95 的 min 钳制：任意 shape 不越界
                const int jhi = std::min(j0 + TN, N);
                const int khi = std::min(k0 + TK, K);
                if (ORDER == 0) {
                    // 内层 i→j→k：k 最内层；C 在 tile 内寄存器提升
                    for (int i = i0; i < ihi; i++)
                        for (int j = j0; j < jhi; j++) {
                            float c = C[i * (size_t)N + j];
                            for (int k = k0; k < khi; k++)
                                c += A[i * (size_t)K + k] * B[k * (size_t)N + j];
                            C[i * (size_t)N + j] = c;
                        }
                } else {
                    // 内层 i→k→j：j 最内层；B[k][j]、C[i][j] 都沿 j 连续
                    for (int i = i0; i < ihi; i++)
                        for (int k = k0; k < khi; k++) {
                            const float a = A[i * (size_t)K + k];
                            for (int j = j0; j < jhi; j++)
                                C[i * (size_t)N + j] += a * B[k * (size_t)N + j];
                        }
                }
            }
}

// 两个 order 各实例化一份，objdump 里能分开数向量指令
void run_config(int idx, const float* A, const float* B, float* C, int M, int N, int K) {
    const Config& cfg = kConfigs[idx];
    if (cfg.order == 0)
        tiled_matmul<0>(A, B, C, M, N, K, cfg.TM, cfg.TN, cfg.TK);
    else
        tiled_matmul<1>(A, B, C, M, N, K, cfg.TM, cfg.TN, cfg.TK);
}

// ---------- 数据与统计工具 ----------
void gen_data(std::vector<float>& A, std::vector<float>& B, int M, int N, int K, unsigned seed) {
    std::mt19937 rng(seed);  // 固定种子：所有配置吃同一份数据，这是控制变量的一部分
    std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
    A.resize((size_t)M * K);
    for (auto& x : A) x = dist(rng);
    B.resize((size_t)K * N);
    for (auto& x : B) x = dist(rng);
}

double median(std::vector<double> v) {  // 传值：nth_element 会打乱顺序
    size_t n = v.size();
    std::nth_element(v.begin(), v.begin() + n / 2, v.end());
    return v[n / 2];
}

double gflops_of(double seconds, long long flops) { return flops / seconds / 1e9; }

// ---------- 正确性门：任一配置与参考逐位相等才放行 ----------
// 返回 0=全过；否则打印失败清单并返回失败数。
int check_all(int M, int N, int K, bool verbose, const char* tag) {
    std::vector<float> A, B;
    gen_data(A, B, M, N, K, 42u);
    std::vector<float> Cref((size_t)M * N, 0.0f), C((size_t)M * N, 0.0f);
    naive_ref(A.data(), B.data(), Cref.data(), M, N, K);

    int fails = 0;
    for (int c = 0; c < kNumConfigs; c++) {
        std::fill(C.begin(), C.end(), 0.0f);
        run_config(c, A.data(), B.data(), C.data(), M, N, K);
        bool exact = (memcmp(C.data(), Cref.data(), C.size() * sizeof(float)) == 0);
        if (!exact) {
            double maxerr = 0;
            for (size_t t = 0; t < C.size(); t++) {
                double d = fabs(C[t] - Cref[t]);
                if (d > maxerr) maxerr = d;
            }
            if (verbose)
                std::printf("  [FAIL] %-8s M=%d N=%d K=%d max_abs_err=%.6f\n", kConfigs[c].name,
                            M, N, K, maxerr);
            fails++;
        } else if (verbose) {
            std::printf("  [PASS] %-8s M=%d N=%d K=%d 逐位相等\n", kConfigs[c].name, M, N, K);
        }
    }
    if (tag)
        std::printf("正确性门[%s]: %d/%d %s\n", tag, kNumConfigs - fails, kNumConfigs,
                    fails == 0 ? "全部与参考逐位相等，放行" : "存在失败，禁止计时");
    return fails;
}

// ---------- 性能实验 ----------
int run_bench(int M, int N, int K, int warm, int reps) {
    const long long flops = 2LL * M * N * K;  // 每 MAC 记 2 个 FLOP
    std::printf("shape: M=%d N=%d K=%d, GFLOPS = 2*M*N*K / t\n", M, N, K);
    std::printf("协议: warmup=%d(丢弃) + repeats=%d(计时), 计时器=steady_clock, "
                "编译=-O3 -ffp-contract=off, 数据种子=42\n", warm, reps);

    // 第 1 步：正确性门 —— 所有配置先验证，再谈性能
    if (check_all(M, N, K, /*verbose=*/false, "bench前") != 0) return 1;

    // 第 2 步：控制变量下的逐配置测量
    std::vector<float> A, B;
    gen_data(A, B, M, N, K, 42u);
    std::vector<float> C((size_t)M * N, 0.0f);

    std::vector<std::vector<double>> samples(kNumConfigs);
    std::vector<double> med(kNumConfigs), mad(kNumConfigs), mn(kNumConfigs),
        mx(kNumConfigs), first(kNumConfigs);

    for (int c = 0; c < kNumConfigs; c++) {
        for (int w = 0; w < warm; w++) run_config(c, A.data(), B.data(), C.data(), M, N, K);
        samples[c].reserve(reps);
        for (int r = 0; r < reps; r++) {
            std::fill(C.begin(), C.end(), 0.0f);  // 重置 C，每次样本同一初始状态
            auto t0 = Clock::now();
            run_config(c, A.data(), B.data(), C.data(), M, N, K);
            auto t1 = Clock::now();
            double sec = std::chrono::duration<double>(t1 - t0).count();
            samples[c].push_back(gflops_of(sec, flops));
            std::printf("CSV,%d,%s,%d,%.4f\n", c, kConfigs[c].name, r, samples[c].back());
        }
        med[c] = median(samples[c]);
        first[c] = samples[c][0];
        std::vector<double> dev;
        dev.reserve(samples[c].size());
        for (double s : samples[c]) dev.push_back(fabs(s - med[c]));
        mad[c] = median(dev);
        auto lo = std::min_element(samples[c].begin(), samples[c].end());
        auto hi = std::max_element(samples[c].begin(), samples[c].end());
        mn[c] = *lo;
        mx[c] = *hi;
        std::printf("MED,%s,%.4f\n", kConfigs[c].name, med[c]);
    }

    // 第 3 步：排序与统计表
    std::vector<int> by_med(kNumConfigs), by_first(kNumConfigs);
    for (int i = 0; i < kNumConfigs; i++) { by_med[i] = i; by_first[i] = i; }
    std::stable_sort(by_med.begin(), by_med.end(),
                     [&](int a, int b) { return med[a] > med[b]; });
    std::stable_sort(by_first.begin(), by_first.end(),
                     [&](int a, int b) { return first[a] > first[b]; });
    std::vector<int> rank_med(kNumConfigs), rank_first(kNumConfigs);
    for (int r = 0; r < kNumConfigs; r++) { rank_med[by_med[r]] = r + 1; rank_first[by_first[r]] = r + 1; }

    std::printf("\n%-9s %10s %10s %8s %8s %10s %6s %6s\n", "kernel", "median", "min", "MAD",
                "spread%", "first_smp", "rk_med", "rk_1st");
    for (int c = 0; c < kNumConfigs; c++) {
        double spread = (mx[c] - mn[c]) / med[c] * 100.0;
        std::printf("%-9s %10.3f %10.3f %8.3f %8.2f %10.3f %6d %6d\n", kConfigs[c].name,
                    med[c], mn[c], mad[c], spread, first[c], rank_med[c], rank_first[c]);
    }
    std::printf("BEST(中位数): %s = %.3f GFLOPS\n", kConfigs[by_med[0]].name, med[by_med[0]]);
    int flips = 0;
    for (int c = 0; c < kNumConfigs; c++)
        if (rank_med[c] != rank_first[c]) flips++;
    std::printf("rank_by_median 与 rank_by_first_sample 有分歧的配置数: %d/%d\n", flips, kNumConfigs);
    return 0;
}

// ---------- 冷启动对照：新进程只跑 1 次，不预热 ----------
int run_cold(int idx, int M, int N, int K) {
    if (idx < 0 || idx >= kNumConfigs) {
        std::fprintf(stderr, "cold: 配置序号必须在 [0,%d]\n", kNumConfigs - 1);
        return 2;
    }
    std::vector<float> A, B;
    gen_data(A, B, M, N, K, 42u);
    // calloc：C 的页在内核首次写入时才缺页 —— 冷启动成本全部计入这一次运行
    float* C = (float*)calloc((size_t)M * N, sizeof(float));
    if (!C) return 2;
    const long long flops = 2LL * M * N * K;
    auto t0 = Clock::now();
    run_config(idx, A.data(), B.data(), C, M, N, K);
    auto t1 = Clock::now();
    double g = gflops_of(std::chrono::duration<double>(t1 - t0).count(), flops);
    std::printf("COLD,%d,%s,%.4f\n", idx, kConfigs[idx].name, g);
    std::printf("冷启动(新进程第 1 次, 含 C 首次缺页): %-9s = %.3f GFLOPS "
                "(对照: 预热后的中位数见 perf-512.txt)\n", kConfigs[idx].name, g);
    free(C);
    return 0;
}

// ---------- 正确性套件：5 个 shape × 6 配置 ----------
int run_suite() {
    const int shapes[][3] = {{5, 7, 3}, {33, 31, 29}, {64, 64, 64}, {65, 63, 33}, {127, 129, 125}};
    const int nShapes = static_cast<int>(sizeof(shapes) / sizeof(shapes[0]));
    std::printf("正确性套件：%d 个 shape × %d 个配置（tile 超出维度时由 min 钳制兜底）\n",
                nShapes, kNumConfigs);
    int total = 0, pass = 0;
    for (int s = 0; s < nShapes; s++) {
        int M = shapes[s][0], N = shapes[s][1], K = shapes[s][2];
        std::vector<float> A, B;
        gen_data(A, B, M, N, K, 42u);
        std::vector<float> Cref((size_t)M * N, 0.0f), C((size_t)M * N, 0.0f);
        naive_ref(A.data(), B.data(), Cref.data(), M, N, K);
        std::printf("shape %3dx%3dx%3d:", M, N, K);
        for (int c = 0; c < kNumConfigs; c++) {
            std::fill(C.begin(), C.end(), 0.0f);
            run_config(c, A.data(), B.data(), C.data(), M, N, K);
            bool ok = (memcmp(C.data(), Cref.data(), C.size() * sizeof(float)) == 0);
            total++;
            if (ok) {
                pass++;
                std::printf(" %-8s:PASS", kConfigs[c].name);
            } else {
                std::printf(" %-8s:FAIL", kConfigs[c].name);
            }
        }
        std::printf("\n");
    }
    std::printf("== 正确性套件: %d/%d PASS（全部与参考逐位相等）==\n", pass, total);
    return pass == total ? 0 : 1;
}

int run_env() {
#if defined(__clang__)
    std::printf("compiler: clang %s\n", __VERSION__);
#elif defined(__GNUC__)
    std::printf("compiler: GCC %s\n", __VERSION__);
#endif
#if defined(__aarch64__)
    std::printf("arch: aarch64 (64-bit ARM)\n");
#elif defined(__x86_64__)
    std::printf("arch: x86-64\n");
#endif
#ifdef BUILD_FLAGS
    std::printf("build_flags: %s\n", BUILD_FLAGS);
#endif
    // 说明：-ffp-contract=off 禁止把 a*b+c 收缩成 fma，是“k 升序累加逐位相等”的编译期保证
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr,
                     "用法: %s suite | bench M N K warm repeats | cold idx M N K | env\n",
                     argv[0]);
        return 2;
    }
    std::string mode = argv[1];
    if (mode == "suite") return run_suite();
    if (mode == "env") return run_env();
    if (mode == "bench") {
        if (argc < 7) {
            std::fprintf(stderr, "bench 需要 M N K warm repeats\n");
            return 2;
        }
        return run_bench(std::atoi(argv[2]), std::atoi(argv[3]), std::atoi(argv[4]),
                         std::atoi(argv[5]), std::atoi(argv[6]));
    }
    if (mode == "cold") {
        if (argc < 6) {
            std::fprintf(stderr, "cold 需要 idx M N K\n");
            return 2;
        }
        return run_cold(std::atoi(argv[2]), std::atoi(argv[3]), std::atoi(argv[4]),
                        std::atoi(argv[5]));
    }
    std::fprintf(stderr, "未知模式: %s\n", mode.c_str());
    return 2;
}
