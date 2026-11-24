// flip_lab.cpp —— 第 98 天：为什么大 Tile 在 512 上更快、在 516 上更慢
//
// 构建：g++ -std=c++17 -O3 -ffp-contract=off -o flip_lab flip_lab.cpp
//
// 用法：
//   ./flip_lab ledger            # ① 结构账本：tile 网格的纯计数（不计时）
//   ./flip_lab isolate           # ② 维度隔离：2 配置 × 10 shape，逐维拆解 516 的尾巴
//   ./flip_lab pitch             # ③ 行距探针：固定计算内容，只改行距（冲突缺失假说）
//   ./flip_lab tailcost          # ④ 尾层单价：只扫 M，给尾层每 MAC 单价定价
//   ./flip_lab confirm           # ⑤ 复跑 512/516 关键对照，看翻转跨进程是否可复现
//   ./flip_lab env               # 环境记录
//
// 与第 97 天的契约：内核与 config_bench.cpp 的 tiled_matmul<1>（i-k-j，j 最内层）
// 完全同构，外加 ldA/ldB/ldC 行距参数（BLAS 的 leading dimension 思想）；
// 数据种子 42、-ffp-contract=off、逐位正确性门、中位数口径全部继承。

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

// ---------- 被测内核：tile 外壳 + min 钳制（D95 遗产），i-k-j 内层序（D96 reorder） ----------
// ldA/ldB/ldC 是行距（leading dimension）：第 r 行首地址 = base + r*ld。
// 隔离/确认模式里 ld = K 或 N（与 D97 完全一致）；行距探针里 ld 可以大于有效列数。
__attribute__((noinline)) void ikj_tiled(const float* A, const float* B, float* C,
                                         int M, int N, int K, int TM, int TN, int TK,
                                         size_t ldA, size_t ldB, size_t ldC) {
    for (int i0 = 0; i0 < M; i0 += TM)
        for (int j0 = 0; j0 < N; j0 += TN)
            for (int k0 = 0; k0 < K; k0 += TK) {
                const int ihi = std::min(i0 + TM, M);  // D95 的 min 钳制：任意 shape 不越界
                const int jhi = std::min(j0 + TN, N);
                const int khi = std::min(k0 + TK, K);
                for (int i = i0; i < ihi; i++)
                    for (int k = k0; k < khi; k++) {
                        const float a = A[(size_t)i * ldA + k];
                        for (int j = j0; j < jhi; j++)          // j 最内层：B、C 沿 j 连续 → 可向量化
                            C[(size_t)i * ldC + j] += a * B[(size_t)k * ldB + j];
                    }
            }
}

// ---------- 参考实现：朴素三重循环，k 升序累加（与 D97 的逐位口径一致） ----------
void naive_ref(const float* A, const float* B, float* C,
               int M, int N, int K, size_t ldA, size_t ldB, size_t ldC) {
    for (int i = 0; i < M; i++)
        for (int j = 0; j < N; j++) {
            float c = 0.0f;
            for (int k = 0; k < K; k++) c += A[(size_t)i * ldA + k] * B[(size_t)k * ldB + j];
            C[(size_t)i * ldC + j] = c;
        }
}

// ---------- 数据与统计工具（口径继承 D97） ----------
struct Mats {
    std::vector<float> A, B, C, Cref;
    int M, N, K;
    size_t ldA, ldB, ldC;
};

void gen_mats(Mats& m, int M, int N, int K, size_t ldA, size_t ldB, size_t ldC, unsigned seed) {
    m.M = M; m.N = N; m.K = K; m.ldA = ldA; m.ldB = ldB; m.ldC = ldC;
    std::mt19937 rng(seed);  // 固定种子 42：所有配置吃同一份数据（控制变量）
    std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
    m.A.assign((size_t)M * ldA, -7.0f);
    m.B.assign((size_t)K * ldB, -7.0f);
    for (int i = 0; i < M; i++)
        for (int k = 0; k < K; k++) m.A[(size_t)i * ldA + k] = dist(rng);
    for (int k = 0; k < K; k++)
        for (int j = 0; j < N; j++) m.B[(size_t)k * ldB + j] = dist(rng);
    m.C.assign((size_t)M * ldC, 0.0f);
    m.Cref.assign((size_t)M * ldC, 0.0f);
}

double median(std::vector<double> v) {  // 传值：nth_element 会打乱顺序
    size_t n = v.size();
    std::nth_element(v.begin(), v.begin() + n / 2, v.end());
    return v[n / 2];
}

double mad_of(const std::vector<double>& v, double med) {
    std::vector<double> dev;
    dev.reserve(v.size());
    for (double x : v) dev.push_back(std::fabs(x - med));
    return median(dev);
}

// ---------- 一次受控计时：预热(丢弃) + repeats 次计时，返回样本 ----------
std::vector<double> time_kernel(const Mats& m, int TM, int TN, int TK, int warm, int reps) {
    const long long flops = 2LL * m.M * m.N * m.K;
    std::vector<double> samples;
    std::vector<float> C = m.C;
    for (int w = 0; w < warm; w++) {
        std::fill(C.begin(), C.end(), 0.0f);
        ikj_tiled(m.A.data(), m.B.data(), C.data(), m.M, m.N, m.K, TM, TN, TK,
                  m.ldA, m.ldB, m.ldC);
    }
    for (int r = 0; r < reps; r++) {
        std::fill(C.begin(), C.end(), 0.0f);  // 每个样本同一初始状态（控制变量）
        auto t0 = Clock::now();
        ikj_tiled(m.A.data(), m.B.data(), C.data(), m.M, m.N, m.K, TM, TN, TK,
                  m.ldA, m.ldB, m.ldC);
        auto t1 = Clock::now();
        double sec = std::chrono::duration<double>(t1 - t0).count();
        samples.push_back((double)flops / sec / 1e9);
    }
    return samples;
}

// ---------- 正确性门：逐位相等才放行（口径继承 D97） ----------
bool check_gate(const Mats& m, int TM, int TN, int TK, const char* tag) {
    std::vector<float> C = m.C;
    ikj_tiled(m.A.data(), m.B.data(), C.data(), m.M, m.N, m.K, TM, TN, TK,
              m.ldA, m.ldB, m.ldC);
    return memcmp(C.data(), m.Cref.data(), C.size() * sizeof(float)) == 0;
}

struct TileCfg { const char* name; int TM, TN, TK; };
const TileCfg kCfgs[] = {
    {"ikj-64", 64, 64, 64},
    {"ikj-128", 128, 128, 128},
};

// ============================================================
// ① 结构账本：纯公式计数 tile 网格，不跑内核
// ============================================================
struct DimPlan {
    int tiles;   // ceil(D/T)
    int full;    // 满块数
    int tail;    // 尾巴元素数（0 表示无尾巴）
};

DimPlan plan_dim(int D, int T) {
    int tiles = (D + T - 1) / T;
    int tail = D % T;
    return {tiles, tail ? tiles - 1 : tiles, tail};
}

int cmd_ledger() {
    struct LShape { int M, N, K; const char* tag; };
    const LShape shapes[] = {
        {512, 512, 512, "512^3"},
        {516, 516, 516, "516^3"},
        {640, 640, 640, "640^3"},
    };
    const int tiles[] = {32, 64, 128};

    std::printf("结构账本：tile 网格的纯计数（内核结构 = min 钳制 + i-k-j 内层序）\n");
    std::printf("每 MAC 记 2 FLOP；流量按 float 元素计；vec 宽度 = 4（NEON 128-bit）\n\n");
    for (auto& s : shapes) {
        for (int T : tiles) {
            DimPlan pm = plan_dim(s.M, T), pn = plan_dim(s.N, T), pk = plan_dim(s.K, T);
            long long macs = (long long)s.M * s.N * s.K;
            long long shells = (long long)pm.tiles * pn.tiles * pk.tiles;
            long long full3 = (long long)pm.full * pn.full * pk.full;
            // C 流量：每个 k-tile 都要读+写整块 C 区域 → M*N*ceil(K/T) 次读 + 同样次写
            long long c_pass = pn.tiles * 0 + (long long)pk.tiles;  // ceil(K/T)
            long long c_traffic = 2LL * s.M * s.N * pk.tiles;
            // A/B 重读次数（tile 化的固有代价）
            long long a_reread = pn.tiles, b_reread = pm.tiles;
            // 向量指令数与通道利用率：内层 j 循环按 4 打包
            long long vec_ops = 0, ik_pairs_short = 0, ik_pairs_all = 0;
            for (int i0 = 0; i0 < s.M; i0 += T)
                for (int j0 = 0; j0 < s.N; j0 += T)
                    for (int k0 = 0; k0 < s.K; k0 += T) {
                        int iw = std::min(i0 + T, s.M) - i0;
                        int jw = std::min(j0 + T, s.N) - j0;
                        int kw = std::min(k0 + T, s.K) - k0;
                        vec_ops += (long long)iw * kw * ((jw + 3) / 4);
                        ik_pairs_all += (long long)iw * kw;
                        if (jw <= 4) ik_pairs_short += (long long)iw * kw;  // 内层只剩 1 条向量指令
                    }
            long long lanes = 4 * vec_ops;
            double lane_util = 100.0 * (double)macs / (double)lanes;
            double shell_pct = 100.0 * (double)full3 / (double)shells;
            std::printf("%-7s tile %3d^3 | 维分解 M:%d+%d尾 N:%d+%d尾 K:%d+%d尾\n",
                        s.tag, T, pm.full, pm.tail, pn.full, pn.tail, pk.full, pk.tail);
            std::printf("        shells=%lld(满块 %.1f%%) C过趟=%lld(C流量 %.2fM elem) "
                        "A重读=%lldx B重读=%lldx\n",
                        shells, shell_pct, c_pass, c_traffic / 1e6, a_reread, b_reread);
            std::printf("        vec_ops=%.2fM 通道利用率=%.2f%% 短内层(i,k)对=%.0f%%\n\n",
                        vec_ops / 1e6, lane_util, 100.0 * (double)ik_pairs_short / (double)ik_pairs_all);
        }
    }
    // 工作集速查（ikj 内核在 tile 内要同时驻留 B tile 和 C tile）
    std::printf("工作集速查（float 元素 × 4B）：\n");
    for (int T : tiles)
        std::printf("  tile %3d^3: B tile = %3dx%3d = %2dKB, C tile = %2dKB, 合计 %3dKB  (L1d=64KB/4路, L2=512KB/8路)\n",
                    T, T, T, T * T * 4 / 1024, T * T * 4 / 1024, 2 * T * T * 4 / 1024);
    return 0;
}

// ============================================================
// ② 维度隔离：哪一维的尾巴在咬人？哪一维在帮忙？
// ============================================================
int cmd_isolate() {
    struct IShape { int M, N, K; const char* tag; };
    const IShape shapes[] = {
        {512, 512, 512, "base  512^3"},
        {640, 512, 512, "M=640(5满块)"},
        {516, 512, 512, "M=516(4+尾4) "},
        {512, 640, 512, "N=640(5满块)"},
        {512, 516, 512, "N=516(4+尾4) "},
        {512, 512, 640, "K=640(5满块)"},
        {512, 512, 516, "K=516(4+尾4) "},
        {576, 576, 576, "all  576^3"},
        {640, 640, 640, "all  640^3"},
        {516, 516, 516, "all  516^3"},
    };
    const int warm = 2, reps = 15;
    std::printf("维度隔离实验：ikj-64 与 ikj-128，单变量改动 shape 的一个维度\n");
    std::printf("协议: warmup=%d(丢弃) + repeats=%d(计时), 中位数/MAD, 编译=-O3 -ffp-contract=off, 种子=42\n",
                warm, reps);
    std::printf("GFLOPS = 2*M*N*K / t；正确性门：逐位与朴素参考相等才计时\n\n");
    std::printf("%-16s | %10s %6s %6s | %10s %6s %6s | %-8s\n",
                "shape", "ikj-64 中位", "MAD", "min", "ikj-128 中位", "MAD", "min", "gate");
    for (auto& s : shapes) {
        Mats m;
        gen_mats(m, s.M, s.N, s.K, (size_t)s.K, (size_t)s.N, (size_t)s.N, 42u);
        naive_ref(m.A.data(), m.B.data(), m.Cref.data(), s.M, s.N, s.K, m.ldA, m.ldB, m.ldC);
        std::printf("%-16s |", s.tag);
        for (auto& cfg : kCfgs) {
            bool ok = check_gate(m, cfg.TM, cfg.TN, cfg.TK, cfg.name);
            std::vector<double> smp = ok ? time_kernel(m, cfg.TM, cfg.TN, cfg.TK, warm, reps)
                                         : std::vector<double>{0.0};
            double med = median(smp), mad = mad_of(smp, med);
            double mn = *std::min_element(smp.begin(), smp.end());
            std::printf(" %10.3f %6.3f %6.3f |", med, mad, mn);
            if (&cfg == &kCfgs[1] && !ok) std::printf(" [FAIL]");
        }
        std::printf("\n");
    }
    return 0;
}

// ============================================================
// ③ 行距探针：计算内容一字不变，只改行距 → 分离「冲突缺失」与「尾巴」
// ============================================================
int cmd_pitch() {
    struct PVar { int n, pitch; const char* tag; };
    const PVar vars[] = {
        {512, 512, "N=512 pitch=512(行距2048B=32行, 每8行撞同一组)"},
        {512, 513, "N=512 pitch=513(行距2052B=32.06行, 组冲突被打散)"},
        {512, 528, "N=512 pitch=528(行距2112B=33行, 对齐64B且打散)"},
        {516, 516, "N=516 pitch=516(带尾4 + 行距2064B=32.25行, 打散)"},
        {516, 528, "N=516 pitch=528(带尾4 + 行距2112B=33行, 对齐且打散)"},
    };
    const int warm = 2, reps = 15;
    std::printf("行距探针：M=N=K 固定，只改 ld（行距）。行距是唯一变量——计算、尾巴、向量内层全部不变\n");
    std::printf("协议: warmup=%d(丢弃) + repeats=%d(计时), 中位数/MAD, 编译=-O3 -ffp-contract=off, 种子=42\n\n", warm, reps);
    std::printf("%-52s | %10s %6s | %10s %6s\n", "变体", "ikj-64", "MAD", "ikj-128", "MAD");
    for (auto& v : vars) {
        Mats m;
        gen_mats(m, v.n, v.n, v.n, (size_t)v.pitch, (size_t)v.pitch, (size_t)v.pitch, 42u);
        naive_ref(m.A.data(), m.B.data(), m.Cref.data(), m.M, m.N, m.K, m.ldA, m.ldB, m.ldC);
        std::printf("%-52s |", v.tag);
        for (auto& cfg : kCfgs) {
            if (!check_gate(m, cfg.TM, cfg.TN, cfg.TK, cfg.name)) {
                std::printf(" %10s %6s |", "[FAIL]", "-");
                continue;
            }
            std::vector<double> smp = time_kernel(m, cfg.TM, cfg.TN, cfg.TK, warm, reps);
            double med = median(smp), mad = mad_of(smp, med);
            std::printf(" %10.3f %6.3f |", med, mad);
        }
        std::printf("\n");
    }
    return 0;
}

// ============================================================
// ④ 尾层单价：M 从 4 到 640 扫一遍，直接给「尾层每 MAC 单价」定价
// ============================================================
int cmd_tailcost() {
    const int Ms[] = {4, 8, 16, 32, 64, 68, 96, 128, 132, 256, 260, 512, 516, 640};
    const int warm = 2, reps = 15;
    std::printf("尾层单价实验：N=K=512 固定，只扫 M。M=4 就是纯尾层（1 个 4 行 i-tile）\n");
    std::printf("ns/MAC = (时间/2) / (M*N*K)，把 FLOP 口径换算成每 MAC 纳秒\n");
    std::printf("协议: warmup=%d(丢弃) + repeats=%d(计时), 中位数, 编译=-O3 -ffp-contract=off, 种子=42\n\n", warm, reps);
    std::printf("%6s | %10s %6s %8s | %10s %6s %8s\n", "M", "ikj-64", "MAD", "ns/MAC", "ikj-128", "MAD", "ns/MAC");
    for (int M : Ms) {
        const int N = 512, K = 512;
        Mats m;
        gen_mats(m, M, N, K, (size_t)K, (size_t)N, (size_t)N, 42u);
        naive_ref(m.A.data(), m.B.data(), m.Cref.data(), M, N, K, m.ldA, m.ldB, m.ldC);
        std::printf("%6d |", M);
        for (auto& cfg : kCfgs) {
            if (!check_gate(m, cfg.TM, cfg.TN, cfg.TK, cfg.name)) {
                std::printf(" %10s %6s %8s |", "[FAIL]", "-", "-");
                continue;
            }
            std::vector<double> smp = time_kernel(m, cfg.TM, cfg.TN, cfg.TK, warm, reps);
            double gf = median(smp);
            double mad = mad_of(smp, gf);
            double nsmac = 2.0 / gf;  // GFLOPS → 每 MAC 纳秒：1e9/(gf×1e9/2) = 2/gf
            std::printf(" %10.3f %6.3f %8.3f |", gf, mad, nsmac);
        }
        std::printf("\n");
    }
    return 0;
}

// ============================================================
// ⑤ 确认模式：关键对照原样复跑一遍（跨运行稳定性，口径继承 D97 repeatability）
// ============================================================
int cmd_confirm() {
    struct CShape { int n; const char* tag; };
    const CShape shapes[] = {{512, "512^3"}, {516, "516^3"}};
    const int warm = 2, reps = 15;
    std::printf("确认实验：512 与 516 的关键对照原样复跑（新进程、同协议）\n");
    std::printf("协议: warmup=%d(丢弃) + repeats=%d(计时), 中位数/MAD, 编译=-O3 -ffp-contract=off, 种子=42\n\n", warm, reps);
    std::printf("%-8s | %10s %6s | %10s %6s\n", "shape", "ikj-64", "MAD", "ikj-128", "MAD");
    for (auto& s : shapes) {
        Mats m;
        gen_mats(m, s.n, s.n, s.n, (size_t)s.n, (size_t)s.n, (size_t)s.n, 42u);
        naive_ref(m.A.data(), m.B.data(), m.Cref.data(), m.M, m.N, m.K, m.ldA, m.ldB, m.ldC);
        std::printf("%-8s |", s.tag);
        for (auto& cfg : kCfgs) {
            if (!check_gate(m, cfg.TM, cfg.TN, cfg.TK, cfg.name)) {
                std::printf(" %10s %6s |", "[FAIL]", "-");
                continue;
            }
            std::vector<double> smp = time_kernel(m, cfg.TM, cfg.TN, cfg.TK, warm, reps);
            std::printf(" %10.3f %6.3f |", median(smp), mad_of(smp, median(smp)));
        }
        std::printf("\n");
    }
    return 0;
}

// ============================================================
// 环境记录
// ============================================================
int cmd_env() {
    std::printf("记录日期: %s\n", __DATE__);
#if defined(__GNUC__) && defined(__GNUC_MINOR__)
    std::printf("编译器: GCC %d.%d\n", __GNUC__, __GNUC_MINOR__);
#endif
#ifdef __aarch64__
    std::printf("架构: aarch64 (NEON 128-bit = 4 float)\n");
#endif
    std::printf("构建命令: g++ -std=c++17 -O3 -ffp-contract=off\n");
    std::printf("内核: min 钳制 tile 外壳 + i-k-j 内层序（与 D97 tiled_matmul<1> 同构）+ ldA/ldB/ldC 行距\n");
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "用法: %s ledger|isolate|tailcost|pitch|confirm|env\n", argv[0]);
        return 2;
    }
    std::string mode = argv[1];
    if (mode == "ledger") return cmd_ledger();
    if (mode == "isolate") return cmd_isolate();
    if (mode == "pitch") return cmd_pitch();
    if (mode == "tailcost") return cmd_tailcost();
    if (mode == "confirm") return cmd_confirm();
    if (mode == "env") return cmd_env();
    std::fprintf(stderr, "未知模式: %s\n", mode.c_str());
    return 2;
}
