// unroll_matmul.cpp —— 第 96 天：循环展开（K/内层）与向量化准备
//
// 构建：  g++ -O2 -std=c++17 -fno-tree-vectorize -o unroll_matmul unroll_matmul.cpp   # 标量版
//         g++ -O3 -std=c++17 -o unroll_matmul_vec unroll_matmul.cpp                   # 自动向量化版
// 用法：  ./unroll_matmul M N K TM TN TK U --all       四个内核对照表（主例 5 7 3 2 4 2 2）
//         ./unroll_matmul --suite                      40 项非整除/边界 Shape 正确性测试
//         ./unroll_matmul --bench N T U                性能测量（--bench 384 64 4）
//         ./unroll_matmul M N K TM TN TK U --mode no-tail|overlap
//
// 语义：C = A·B，A∈R^{M×K}，B∈R^{K×N}，行主序（与第 88~95 天一致）。
//       所有内核的 k 累加顺序都与参考实现一致（k 升序、串行累加链），
//       因此正确内核与参考逐位相等（e != 0.0 即失败）。
// 插桩（--all/--suite/--mode 路径）：所有访存经过 ldA/ldB/ldC/stC 包装，
//       越界一次记一次 oob；缓冲区按 tile 垫高并预填垃圾值 7.5，
//       错误模式不会段错误，而是可数、可观察的错误结果。
// 性能（--bench 路径）：直接下标访存、无插桩；预热 5 次 + 计时 15 次取中位数。

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

// ===================== 插桩路径（小 shape，计数器全开） =====================

struct Metrics {
    std::string name;
    bool correct = false;
    double max_abs_err = 0.0;
    long long inner_iters = 0;   // 有效 MAC 步数（有用计算）
    long long ctrl_iters = 0;    // 循环控制迭代数（cmp+自增+分支 ≈ 3 条/次）
    long long body_copies = 0;   // 静态循环体份数（源码里的 MAC 语句数）
    long long oob_touches = 0;   // 越界访存次数
    long long dup_writes = 0;    // 落到已写元素的重复 store（overlap 复现用）
};

struct Runner {
    int M, N, K, TM, TN, TK, U;
    int pm, pn, pk;             // 垫高后的缓冲维度
    std::vector<float> A, B, C;  // A: pm×pk, B: pk×pn, C: pm×pn
    std::vector<float> refC;     // M×N
    long long oob = 0;

    Runner(int M_, int N_, int K_, int TM_, int TN_, int TK_, int U_)
        : M(M_), N(N_), K(K_), TM(TM_), TN(TN_), TK(TK_), U(U_) {
        pm = (M + TM - 1) / TM * TM;
        pn = (N + TN - 1) / TN * TN;
        pk = (K + TK - 1) / TK * TK;
        A.resize((size_t)pm * pk);
        B.resize((size_t)pk * pn);
        C.resize((size_t)pm * pn);
        const float PAD = 7.5f;  // pad 区的垃圾值（与第 95 天一致）
        for (auto &v : A) v = PAD;
        for (auto &v : B) v = PAD;
        for (auto &v : C) v = PAD;
        for (int i = 0; i < M; i++)
            for (int k = 0; k < K; k++)
                A[(size_t)i * pk + k] = 0.25f * ((i * 7 + k * 3) % 11) - 1.0f;
        for (int k = 0; k < K; k++)
            for (int j = 0; j < N; j++)
                B[(size_t)k * pn + j] = 0.25f * ((k * 5 + j * 9) % 13) - 1.5f;
        refC.assign((size_t)M * N, 0.0f);
        for (int i = 0; i < M; i++)
            for (int j = 0; j < N; j++) {
                float acc = 0.0f;
                for (int k = 0; k < K; k++)
                    acc += A[(size_t)i * pk + k] * B[(size_t)k * pn + j];
                refC[(size_t)i * N + j] = acc;
            }
    }

    float ldA(int i, int k) {
        if (i < 0 || i >= M || k < 0 || k >= K) oob++;
        return A[(size_t)i * pk + k];
    }
    float ldB(int k, int j) {
        if (k < 0 || k >= K || j < 0 || j >= N) oob++;
        return B[(size_t)k * pn + j];
    }
    float ldC(int i, int j) {
        if (i < 0 || i >= M || j < 0 || j >= N) oob++;
        return C[(size_t)i * pn + j];
    }
    void stC(int i, int j, float v) {
        if (i < 0 || i >= M || j < 0 || j >= N) oob++;
        C[(size_t)i * pn + j] = v;
    }

    void resetC() { std::fill(C.begin(), C.end(), 0.0f); }

    void finalize(Metrics &m) {
        m.oob_touches = oob;
        m.max_abs_err = 0.0;
        m.correct = true;
        for (int i = 0; i < M; i++)
            for (int j = 0; j < N; j++) {
                double e = std::fabs((double)C[(size_t)i * pn + j] -
                                     (double)refC[(size_t)i * N + j]);
                if (e > m.max_abs_err) m.max_abs_err = e;
                if (e != 0.0) m.correct = false;
            }
    }

    // ---------- 内核 1：baseline，第 95 天的 minclamp 版（i/j/k 点循环） ----------
    Metrics run_baseline() {
        Metrics m;
        m.name = "baseline(i/j/k)";
        m.body_copies = 1;
        resetC();
        for (int i0 = 0; i0 < M; i0 += TM) {
            int ihi = std::min(i0 + TM, M);
            for (int j0 = 0; j0 < N; j0 += TN) {
                int jhi = std::min(j0 + TN, N);
                for (int k0 = 0; k0 < K; k0 += TK) {
                    int khi = std::min(k0 + TK, K);
                    for (int i = i0; i < ihi; i++) {
                        m.ctrl_iters++;
                        for (int j = j0; j < jhi; j++) {
                            m.ctrl_iters++;
                            for (int k = k0; k < khi; k++) {
                                m.ctrl_iters++;
                                m.inner_iters++;
                                stC(i, j, ldC(i, j) + ldA(i, k) * ldB(k, j));
                            }
                        }
                    }
                }
            }
        }
        finalize(m);
        return m;
    }

    // ---------- 内核 2：reorder，把连续的 j 换到最内层（不展开） ----------
    Metrics run_reorder() {
        Metrics m;
        m.name = "reorder(i/k/j)";
        m.body_copies = 1;
        resetC();
        for (int i0 = 0; i0 < M; i0 += TM) {
            int ihi = std::min(i0 + TM, M);
            for (int k0 = 0; k0 < K; k0 += TK) {
                int khi = std::min(k0 + TK, K);
                for (int j0 = 0; j0 < N; j0 += TN) {
                    int jhi = std::min(j0 + TN, N);
                    for (int i = i0; i < ihi; i++) {
                        m.ctrl_iters++;
                        for (int k = k0; k < khi; k++) {
                            m.ctrl_iters++;
                            for (int j = j0; j < jhi; j++) {
                                m.ctrl_iters++;
                                m.inner_iters++;
                                // 最内层沿 j：B 的行、C 的行都连续
                                stC(i, j, ldC(i, j) + ldA(i, k) * ldB(k, j));
                            }
                        }
                    }
                }
            }
        }
        finalize(m);
        return m;
    }

    // ---------- 内核 3：unroll-k，k 点循环展开 U 份 + 尾部循环 ----------
    // k 依然升序串行累加 → 与参考逐位相等
    Metrics run_unrollk() {
        Metrics m;
        m.name = "unroll-k U=" + std::to_string(U);
        m.body_copies = U + 1;  // 主循环 1 份体内 U 条 MAC + 尾部 1 条
        resetC();
        for (int i0 = 0; i0 < M; i0 += TM) {
            int ihi = std::min(i0 + TM, M);
            for (int j0 = 0; j0 < N; j0 += TN) {
                int jhi = std::min(j0 + TN, N);
                for (int k0 = 0; k0 < K; k0 += TK) {
                    int khi = std::min(k0 + TK, K);
                    for (int i = i0; i < ihi; i++) {
                        m.ctrl_iters++;
                        for (int j = j0; j < jhi; j++) {
                            m.ctrl_iters++;
                            float c = ldC(i, j);
                            int k = k0;
                            for (; k + U <= khi; k += U) {
                                m.ctrl_iters++;
                                for (int u = 0; u < U; u++) {  // U 条 MAC 写在一起
                                    m.inner_iters++;
                                    c += ldA(i, k + u) * ldB(k + u, j);
                                }
                            }
                            for (; k < khi; k++) {  // 尾部循环
                                m.ctrl_iters++;
                                m.inner_iters++;
                                c += ldA(i, k) * ldB(k, j);
                            }
                            stC(i, j, c);
                        }
                    }
                }
            }
        }
        finalize(m);
        return m;
    }

    // ---------- 内核 4：unroll-j，reorder 之后把 j 点循环展开 U 份 + 尾部 ----------
    Metrics run_unrollj() {
        Metrics m;
        m.name = "unroll-j U=" + std::to_string(U);
        m.body_copies = U + 1;
        resetC();
        for (int i0 = 0; i0 < M; i0 += TM) {
            int ihi = std::min(i0 + TM, M);
            for (int k0 = 0; k0 < K; k0 += TK) {
                int khi = std::min(k0 + TK, K);
                for (int j0 = 0; j0 < N; j0 += TN) {
                    int jhi = std::min(j0 + TN, N);
                    for (int i = i0; i < ihi; i++) {
                        m.ctrl_iters++;
                        for (int k = k0; k < khi; k++) {
                            m.ctrl_iters++;
                            int j = j0;
                            for (; j + U <= jhi; j += U) {
                                m.ctrl_iters++;
                                for (int u = 0; u < U; u++) {  // U 个 j 连续，独立累加
                                    m.inner_iters++;
                                    stC(i, j + u, ldC(i, j + u) +
                                                     ldA(i, k) * ldB(k, j + u));
                                }
                            }
                            for (; j < jhi; j++) {  // 尾部循环
                                m.ctrl_iters++;
                                m.inner_iters++;
                                stC(i, j, ldC(i, j) + ldA(i, k) * ldB(k, j));
                            }
                        }
                    }
                }
            }
        }
        finalize(m);
        return m;
    }

    // ---------- 错误复现 1：no-tail，展开后忘了尾部循环 ----------
    Metrics run_no_tail() {
        Metrics m;
        m.name = "no-tail(丢尾部)";
        m.body_copies = U;
        resetC();
        for (int i0 = 0; i0 < M; i0 += TM) {
            int ihi = std::min(i0 + TM, M);
            for (int j0 = 0; j0 < N; j0 += TN) {
                int jhi = std::min(j0 + TN, N);
                for (int k0 = 0; k0 < K; k0 += TK) {
                    int khi = std::min(k0 + TK, K);
                    for (int i = i0; i < ihi; i++) {
                        m.ctrl_iters++;
                        for (int j = j0; j < jhi; j++) {
                            m.ctrl_iters++;
                            float c = ldC(i, j);
                            for (int k = k0; k + U <= khi; k += U) {
                                m.ctrl_iters++;
                                for (int u = 0; u < U; u++) {
                                    m.inner_iters++;
                                    c += ldA(i, k + u) * ldB(k + u, j);
                                }
                            }
                            stC(i, j, c);
                        }
                    }
                }
            }
        }
        finalize(m);
        return m;
    }

    // ---------- 错误复现 2：overlap，主循环条件写成 k < khi ----------
    // 每步仍做 U 条 MAC，最后一步会“伸过” khi：
    // 伸进下一个 tile 的 k（在 K 内）→ 重复累加；伸出 K → 越界读。
    Metrics run_overlap() {
        Metrics m;
        m.name = "overlap(k<khi)";
        m.body_copies = U;
        resetC();
        for (int i0 = 0; i0 < M; i0 += TM) {
            int ihi = std::min(i0 + TM, M);
            for (int j0 = 0; j0 < N; j0 += TN) {
                int jhi = std::min(j0 + TN, N);
                for (int k0 = 0; k0 < K; k0 += TK) {
                    int khi = std::min(k0 + TK, K);
                    for (int i = i0; i < ihi; i++) {
                        m.ctrl_iters++;
                        for (int j = j0; j < jhi; j++) {
                            m.ctrl_iters++;
                            float c = ldC(i, j);
                            for (int k = k0; k < khi; k += U) {
                                m.ctrl_iters++;
                                for (int u = 0; u < U; u++) {  // 最后一步会伸过 khi
                                    m.inner_iters++;
                                    c += ldA(i, k + u) * ldB(k + u, j);
                                }
                            }
                            stC(i, j, c);
                        }
                    }
                }
            }
        }
        finalize(m);
        return m;
    }
};

static void print_header() {
    std::printf("%-22s %7s %11s %10s %12s %8s %9s\n", "kernel", "correct",
                "inner_iters", "ctrl_iters", "max_abs_err", "oob", "body_copies");
}
static void print_row(const Metrics &m) {
    std::printf("%-22s %7s %11lld %10lld %12.3f %8lld %9lld\n",
                m.name.c_str(), m.correct ? "yes" : "NO", m.inner_iters,
                m.ctrl_iters, m.max_abs_err, m.oob_touches, m.body_copies);
}

static int run_table(int M, int N, int K, int TM, int TN, int TK, int U) {
    Runner r(M, N, K, TM, TN, TK, U);
    std::printf("shape: M=%d N=%d K=%d, tile: TM=%d TN=%d TK=%d, U=%d, "
                "useful_flops(M*N*K)=%d, tiles=%d\n",
                M, N, K, TM, TN, TK, U, M * N * K,
                ((M + TM - 1) / TM) * ((N + TN - 1) / TN) *
                    ((K + TK - 1) / TK));
    print_header();
    Metrics a = r.run_baseline(), b = r.run_reorder(),
            c = r.run_unrollk(), d = r.run_unrollj();
    print_row(a); print_row(b); print_row(c); print_row(d);
    int bad = 0;
    for (Metrics *pm : {&a, &b, &c, &d}) if (!pm->correct) bad++;
    std::printf("== 正确性：%s（与参考逐位比较） ==\n",
                bad == 0 ? "4/4 全部逐位相等" : "存在失败！");
    return bad == 0 ? 0 : 1;
}

// ===================== 性能路径（大 shape，直下标，无插桩） =====================

struct P {
    int M, N, K, TM, TN, TK;
};

template <int... Is>
static inline void uk_body(std::integer_sequence<int, Is...>, const float *A,
                            const float *B, float *c, int i, int j, int k,
                            int N, int K) {
    ((*c += A[(size_t)i * K + k + Is] * B[(size_t)(k + Is) * N + j]), ...);
}

template <int... Is>
static inline void uj_body(std::integer_sequence<int, Is...>, const float *A,
                            const float *B, float *C, int i, int j, int k,
                            int N, int K) {
    ((C[(size_t)i * N + j + Is] +=
         A[(size_t)i * K + k] * B[(size_t)k * N + j + Is]),
     ...);
}

__attribute__((noinline)) void p_baseline(const float *A, const float *B,
                                          float *C, const P &p) {
    for (int i0 = 0; i0 < p.M; i0 += p.TM) {
        int ihi = std::min(i0 + p.TM, p.M);
        for (int j0 = 0; j0 < p.N; j0 += p.TN) {
            int jhi = std::min(j0 + p.TN, p.N);
            for (int k0 = 0; k0 < p.K; k0 += p.TK) {
                int khi = std::min(k0 + p.TK, p.K);
                for (int i = i0; i < ihi; i++)
                    for (int j = j0; j < jhi; j++)
                        for (int k = k0; k < khi; k++)
                            C[(size_t)i * p.N + j] +=
                                A[(size_t)i * p.K + k] * B[(size_t)k * p.N + j];
            }
        }
    }
}

__attribute__((noinline)) void p_reorder(const float *A, const float *B,
                                          float *C, const P &p) {
    for (int i0 = 0; i0 < p.M; i0 += p.TM) {
        int ihi = std::min(i0 + p.TM, p.M);
        for (int k0 = 0; k0 < p.K; k0 += p.TK) {
            int khi = std::min(k0 + p.TK, p.K);
            for (int j0 = 0; j0 < p.N; j0 += p.TN) {
                int jhi = std::min(j0 + p.TN, p.N);
                for (int i = i0; i < ihi; i++)
                    for (int k = k0; k < khi; k++)
                        for (int j = j0; j < jhi; j++)
                            C[(size_t)i * p.N + j] +=
                                A[(size_t)i * p.K + k] * B[(size_t)k * p.N + j];
            }
        }
    }
}

template <int U>
__attribute__((noinline)) void p_unrollk(const float *A, const float *B,
                                          float *C, const P &p) {
    for (int i0 = 0; i0 < p.M; i0 += p.TM) {
        int ihi = std::min(i0 + p.TM, p.M);
        for (int j0 = 0; j0 < p.N; j0 += p.TN) {
            int jhi = std::min(j0 + p.TN, p.N);
            for (int k0 = 0; k0 < p.K; k0 += p.TK) {
                int khi = std::min(k0 + p.TK, p.K);
                for (int i = i0; i < ihi; i++)
                    for (int j = j0; j < jhi; j++) {
                        float c = C[(size_t)i * p.N + j];
                        int k = k0;
                        for (; k + U <= khi; k += U)
                            uk_body(std::make_integer_sequence<int, U>{}, A,
                                    B, &c, i, j, k, p.N, p.K);
                        for (; k < khi; k++)
                            c += A[(size_t)i * p.K + k] * B[(size_t)k * p.N + j];
                        C[(size_t)i * p.N + j] = c;
                    }
            }
        }
    }
}

template <int U>
__attribute__((noinline)) void p_unrollj(const float *A, const float *B,
                                          float *C, const P &p) {
    for (int i0 = 0; i0 < p.M; i0 += p.TM) {
        int ihi = std::min(i0 + p.TM, p.M);
        for (int k0 = 0; k0 < p.K; k0 += p.TK) {
            int khi = std::min(k0 + p.TK, p.K);
            for (int j0 = 0; j0 < p.N; j0 += p.TN) {
                int jhi = std::min(j0 + p.TN, p.N);
                for (int i = i0; i < ihi; i++)
                    for (int k = k0; k < khi; k++) {
                        int j = j0;
                        for (; j + U <= jhi; j += U)
                            uj_body(std::make_integer_sequence<int, U>{}, A,
                                    B, C, i, j, k, p.N, p.K);
                        for (; j < jhi; j++)
                            C[(size_t)i * p.N + j] +=
                                A[(size_t)i * p.K + k] * B[(size_t)k * p.N + j];
                    }
            }
        }
    }
}

template <class F>
static double time_one(F &&kernel, int warm, int reps) {
    std::vector<double> ts;
    for (int r = 0; r < warm + reps; r++) {
        auto t0 = std::chrono::steady_clock::now();
        kernel();
        auto t1 = std::chrono::steady_clock::now();
        double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
        if (r >= warm) ts.push_back(ms);
    }
    std::sort(ts.begin(), ts.end());
    return ts[ts.size() / 2];
}

static int run_bench(int n, int t, int u) {
    P p{n, n, n, t, t, t};
    std::vector<float> A((size_t)n * n), B((size_t)n * n);
    for (auto &v : A) v = 0.25f * (rand() % 11) - 1.0f;
    for (auto &v : B) v = 0.25f * (rand() % 13) - 1.5f;
    std::vector<float> ref((size_t)n * n);
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) {
            float acc = 0.0f;
            for (int k = 0; k < n; k++)
                acc += A[(size_t)i * n + k] * B[(size_t)k * n + j];
            ref[(size_t)i * n + j] = acc;
        }
    const float *Ap = A.data(), *Bp = B.data();
    std::vector<float> C((size_t)n * n);
    float *Cp = C.data();
    double flop = 2.0 * n * n * n;
    int warm = 5, reps = 15;
    std::printf("bench: n=%d tile=%dx%dx%d, warmup=%d reps=%d "
                "(median), flop=%.1f MFLOP\n",
                n, t, t, t, warm, reps, flop / 1e6);
    (void)u;  // 展开因子固定枚举 2/4/8，u 仅用于 suite/表格

    auto check = [&]() {
        for (size_t x = 0; x < C.size(); x++)
            if (C[x] != ref[x]) return false;
        return true;
    };
    std::vector<bool> ok;
    auto run = [&](const char *name, auto kernel) {
        std::fill(C.begin(), C.end(), 0.0f);
        kernel();  // 先做一次校验调用，逐位比对参考结果
        bool exact = check();
        double ms = time_one(kernel, warm, reps);  // 计时调用不再看 C 的值
        ok.push_back(exact);
        std::printf("%-14s %9.3f ms   %8.3f GFLOPS   %s\n", name, ms,
                    flop / (ms * 1e6), exact ? "逐位相等" : "不相等!");
    };
    run("baseline", [&] { p_baseline(Ap, Bp, Cp, p); });
    run("reorder", [&] { p_reorder(Ap, Bp, Cp, p); });
    run("unroll-k 2", [&] { p_unrollk<2>(Ap, Bp, Cp, p); });
    run("unroll-k 4", [&] { p_unrollk<4>(Ap, Bp, Cp, p); });
    run("unroll-k 8", [&] { p_unrollk<8>(Ap, Bp, Cp, p); });
    run("unroll-j 2", [&] { p_unrollj<2>(Ap, Bp, Cp, p); });
    run("unroll-j 4", [&] { p_unrollj<4>(Ap, Bp, Cp, p); });
    run("unroll-j 8", [&] { p_unrollj<8>(Ap, Bp, Cp, p); });
    int bad = 0;
    for (bool b : ok) if (!b) bad++;
    std::printf("== 逐位正确性：%d/%d 通过 ==\n", (int)ok.size() - bad,
                (int)ok.size());
    return bad == 0 ? 0 : 1;
}

// ===================== suite 与 main =====================

static int run_suite(int u) {
    struct Case { int m, n, k, tm, tn, tk; const char *tag; };
    std::vector<Case> cases = {
        {5, 7, 3, 2, 4, 2, "主例：tile 内 k 长 2"},
        {1, 7, 3, 2, 4, 2, "M=1"},
        {5, 1, 3, 2, 4, 2, "N=1（j 展开只剩尾部）"},
        {5, 7, 1, 2, 4, 2, "K=1（k 展开只剩尾部）"},
        {9, 9, 9, 4, 4, 4, "每维余 1"},
        {7, 7, 7, 8, 8, 8, "Tile 比维度大"},
        {64, 64, 64, 16, 16, 16, "完全整除"},
        {65, 63, 33, 16, 16, 16, "大 shape 全带尾"},
        {3, 100, 2, 2, 32, 5, "瘦长 N"},
        {100, 3, 17, 16, 2, 3, "瘦长 M"},
    };
    int fails = 0, total = 0;
    std::printf("U=%d\n", u);
    std::printf("%-24s %-26s %-16s %-16s %-16s %-16s\n", "case(M N K | T)",
                "说明", "unroll-k", "unroll-j", "no-tail", "overlap");
    for (auto &c : cases) {
        Runner r(c.m, c.n, c.k, c.tm, c.tn, c.tk, u);
        char buf[64];
        std::snprintf(buf, sizeof buf, "%dx%dx%d | %dx%dx%d", c.m, c.n, c.k,
                      c.tm, c.tn, c.tk);
        Metrics a = r.run_unrollk(), b = r.run_unrollj(),
                d = r.run_no_tail(), e = r.run_overlap();
        std::printf("%-24s %-26s %-16s %-16s %-16s %-16s\n", buf, c.tag,
                    a.correct ? "PASS(逐位相等)" : "FAIL",
                    b.correct ? "PASS(逐位相等)" : "FAIL",
                    d.correct ? "PASS(碰巧)" : "FAIL(丢尾部)",
                    e.correct ? "PASS(碰巧)" : "FAIL(越界/重算)");
        for (Metrics *pm : {&a, &b}) {
            total++;
            if (!pm->correct) fails++;
        }
    }
    std::printf("\n== suite 结果：unroll-k/unroll-j 正确性 %d/%d 通过；"
                "no-tail/overlap 只在“有尾部”的用例上发作，"
                "完全整除时碰巧正确 ==\n",
                total - fails, total);
    return fails == 0 ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        std::fprintf(stderr,
                     "usage: %s M N K TM TN TK U --all\n"
                     "       %s --suite U\n"
                     "       %s --bench N T U\n"
                     "       %s M N K TM TN TK U --mode no-tail|overlap\n",
                     argv[0], argv[0], argv[0], argv[0]);
        return 2;
    }
    if (std::string(argv[1]) == "--suite") {
        int u = argc >= 3 ? atoi(argv[2]) : 4;
        int rc = run_suite(u);
        rc |= run_suite(u == 4 ? 5 : 4);
        return rc;
    }
    if (std::string(argv[1]) == "--bench") {
        int n = argc >= 3 ? atoi(argv[2]) : 384;
        int t = argc >= 4 ? atoi(argv[3]) : 64;
        int u = argc >= 5 ? atoi(argv[4]) : 4;
        return run_bench(n, t, u);
    }
    if (argc < 9) {
        std::fprintf(stderr, "需要 M N K TM TN TK U --all|--mode NAME\n");
        return 2;
    }
    int M = atoi(argv[1]), N = atoi(argv[2]), K = atoi(argv[3]);
    int TM = atoi(argv[4]), TN = atoi(argv[5]), TK = atoi(argv[6]);
    int U = atoi(argv[7]);
    std::string mode = argv[8];
    if (M <= 0 || N <= 0 || K <= 0 || TM <= 0 || TN <= 0 || TK <= 0 || U <= 0) {
        std::fprintf(stderr, "M,N,K,TM,TN,TK,U 必须均为正整数\n");
        return 2;
    }
    if (mode == "--all") return run_table(M, N, K, TM, TN, TK, U);
    if (mode == "--mode") {
        std::string which = argc >= 10 ? argv[9] : "";
        Runner r(M, N, K, TM, TN, TK, U);
        Metrics m;
        if (which == "no-tail") m = r.run_no_tail();
        else if (which == "overlap") m = r.run_overlap();
        else {
            std::fprintf(stderr,
                         "未知复现模式：%s（可选 no-tail|overlap）\n",
                         which.c_str());
            return 2;
        }
        std::printf("shape: M=%d N=%d K=%d, tile: TM=%d TN=%d TK=%d, U=%d, "
                    "mode=%s, useful_flops(M*N*K)=%d\n",
                    M, N, K, TM, TN, TK, U, which.c_str(), M * N * K);
        print_header();
        print_row(m);
        std::printf("inner_iters=%lld (useful=%d) ctrl_iters=%lld "
                    "oob=%lld max_abs_err=%.3f correct=%s\n",
                    m.inner_iters, M * N * K, m.ctrl_iters, m.oob_touches,
                    m.max_abs_err, m.correct ? "yes" : "NO");
        return 0;
    }
    std::fprintf(stderr, "未知模式：%s\n", mode.c_str());
    return 2;
}
