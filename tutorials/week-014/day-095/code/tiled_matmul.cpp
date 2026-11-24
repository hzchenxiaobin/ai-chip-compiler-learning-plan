// tiled_matmul.cpp —— 第 95 天：非整除尾部的三种策略对照 + 三个错误复现
//
// 构建：  g++ -O2 -std=c++17 -o tiled_matmul tiled_matmul.cpp
// 用法：  ./tiled_matmul M N K TM TN TK --all          三种策略对照表
//         ./tiled_matmul M N K TM TN TK --suite        一批非整除/边界 Shape 的正确性测试
//         ./tiled_matmul M N K TM TN TK --mode danger|clamp-store|off-by-one
//
// 语义：C = A·B，A∈R^{M×K}，B∈R^{K×N}。所有策略共享同一参考实现，
//       累加顺序完全一致（k 升序），因此正确策略应与参考逐位相等。
// 插桩：所有访存经过 ldA/ldB/ldC/stC 包装，越界一次记一次 oob_touches；
//       分配时给每个维度垫了“垃圾值”缓冲（pad），所以 danger 模式不会段错误，
//       而是把越界访问变成可数的、结果可观察的错误。

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

struct Metrics {
    std::string name;
    bool correct = false;
    double max_abs_err = 0.0;
    long long inner_iters = 0;    // 最内层循环执行次数
    long long guard_checks = 0;   // if (i<M && j<N && k<K) 判断执行次数
    long long idle_iters = 0;     // 判断为假、白跑的迭代
    long long boundary_ops = 0;   // min 钳制 / 区域判空等边界操作次数
    long long oob_touches = 0;    // 越界访存次数
    long long assign_stores = 0;  // 赋值式 store 次数（clamp-store 复现用）
    long long duplicate_writes = 0;   // 落到已被赋值过的元素的 store 数
    long long max_assign_per_elem = 0; // 单个元素最多被赋值式 store 的次数
    long long body_copies = 0;    // 静态循环体份数（epilogue 的 2^d 代价）
    long long regions_nonempty = 0;   // epilogue 非空区域数
};

static long long clamp_ll(long long v, long long lo, long long hi) {
    return std::max(lo, std::min(hi, v));
}

struct Runner {
    int M, N, K, TM, TN, TK;
    int pm, pn, pk;                 // 垫高后的缓冲维度：ceil(dim/T)*T
    std::vector<float> A, B, C;      // A: pm×pk, B: pk×pn, C: pm×pn
    std::vector<float> refC;         // M×N
    std::vector<int> wc;             // 每个真实元素的“赋值式 store”计数
    long long oob = 0;

    Runner(int M_, int N_, int K_, int TM_, int TN_, int TK_)
        : M(M_), N(N_), K(K_), TM(TM_), TN(TN_), TK(TK_) {
        pm = (M + TM - 1) / TM * TM;
        pn = (N + TN - 1) / TN * TN;
        pk = (K + TK - 1) / TK * TK;
        A.resize((size_t)pm * pk);
        B.resize((size_t)pk * pn);
        C.resize((size_t)pm * pn);
        wc.assign((size_t)M * N, 0);
        const float PAD = 7.5f;      // pad 区的垃圾值
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
    void stC(int i, int j, float v, bool assign = false) {
        if (i < 0 || i >= M || j < 0 || j >= N) oob++;
        C[(size_t)i * pn + j] = v;
        if (assign) {
            wc[(size_t)clamp_ll(i, 0, M - 1) * N + clamp_ll(j, 0, N - 1)]++;
        }
    }
    void resetC() { std::fill(C.begin(), C.end(), 0.0f); }
    void resetInstr() { oob = 0; std::fill(wc.begin(), wc.end(), 0); }

    void finalize(Metrics &m) {
        m.oob_touches = oob;
        long long maxw = 0, dup = 0;
        for (int c : wc) {
            maxw = std::max<long long>(maxw, c);
            if (c > 1) dup += c - 1;
        }
        m.max_assign_per_elem = maxw;
        m.duplicate_writes = dup;
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

    // ---------- 策略 1：guard，每元素判断（掩码思想的朴素形态） ----------
    Metrics run_guard() {
        Metrics m;
        m.name = "guard(每元素if)";
        resetInstr(); resetC();
        for (int i0 = 0; i0 < M; i0 += TM)
            for (int j0 = 0; j0 < N; j0 += TN)
                for (int k0 = 0; k0 < K; k0 += TK)
                    for (int i = i0; i < i0 + TM; i++)
                        for (int j = j0; j < j0 + TN; j++)
                            for (int k = k0; k < k0 + TK; k++) {
                                m.inner_iters++;
                                m.guard_checks++;
                                if (i < M && j < N && k < K) {
                                    stC(i, j, ldC(i, j) + ldA(i, k) * ldB(k, j));
                                } else {
                                    m.idle_iters++;
                                }
                            }
        finalize(m);
        return m;
    }

    // ---------- 策略 2：minclamp，Tile 边界钳制（MLIR/linalg 的做法） ----------
    Metrics run_minclamp() {
        Metrics m;
        m.name = "minclamp(min钳制)";
        resetInstr(); resetC();
        for (int i0 = 0; i0 < M; i0 += TM) {
            int ihi = std::min(i0 + TM, M);
            m.boundary_ops++;
            for (int j0 = 0; j0 < N; j0 += TN) {
                int jhi = std::min(j0 + TN, N);
                m.boundary_ops++;
                for (int k0 = 0; k0 < K; k0 += TK) {
                    int khi = std::min(k0 + TK, K);
                    m.boundary_ops++;
                    for (int i = i0; i < ihi; i++)
                        for (int j = j0; j < jhi; j++)
                            for (int k = k0; k < khi; k++) {
                                m.inner_iters++;
                                stC(i, j, ldC(i, j) + ldA(i, k) * ldB(k, j));
                            }
                }
            }
        }
        finalize(m);
        return m;
    }

    // ---------- 策略 3：epilogue，主循环 + 分离尾部（2^d 区域分解） ----------
    Metrics run_epilogue() {
        Metrics m;
        m.name = "epilogue(分离尾部)";
        resetInstr(); resetC();
        int Mm = M / TM * TM, Nn = N / TN * TN, Km = K / TK * TK;
        m.body_copies = 8;               // 2^3 份循环体
        for (int mi = 0; mi < 2; mi++)
            for (int nj = 0; nj < 2; nj++)
                for (int gk = 0; gk < 2; gk++) {
                    m.boundary_ops++;    // 每区域一次判空
                    int iLo = mi ? Mm : 0, iHi = mi ? M : Mm;
                    int jLo = nj ? Nn : 0, jHi = nj ? N : Nn;
                    int kLo = gk ? Km : 0, kHi = gk ? K : Km;
                    if (iLo >= iHi || jLo >= jHi || kLo >= kHi) continue;
                    m.regions_nonempty++;
                    for (int i = iLo; i < iHi; i++)
                        for (int j = jLo; j < jHi; j++)
                            for (int k = kLo; k < kHi; k++) {
                                m.inner_iters++;
                                stC(i, j, ldC(i, j) + ldA(i, k) * ldB(k, j));
                            }
                }
        finalize(m);
        return m;
    }

    // ---------- 错误复现 1：danger，忘加 min 也忘加 if ----------
    Metrics run_danger() {
        Metrics m;
        m.name = "danger(无任何保护)";
        resetInstr(); resetC();
        for (int i0 = 0; i0 < M; i0 += TM)
            for (int j0 = 0; j0 < N; j0 += TN)
                for (int k0 = 0; k0 < K; k0 += TK)
                    for (int i = i0; i < i0 + TM; i++)
                        for (int j = j0; j < j0 + TN; j++)
                            for (int k = k0; k < k0 + TK; k++) {
                                m.inner_iters++;
                                stC(i, j, ldC(i, j) + ldA(i, k) * ldB(k, j));
                            }
        finalize(m);
        return m;
    }

    // ---------- 错误复现 2：clamp-store，钳制“索引”而不是“边界” ----------
    // 为隔离单一变量：k 不分 tile（升序整段），i/j 走未钳制的完整网格，
    // 访存用 min(i, M-1) 等把索引拉回界内，store 是赋值式。
    Metrics run_clamp_store() {
        Metrics m;
        m.name = "clamp-store(钳索引)";
        resetInstr(); resetC();
        for (int i = 0; i < pm; i++)
            for (int j = 0; j < pn; j++) {
                float acc = 0.0f;
                int ci = std::min(i, M - 1), cj = std::min(j, N - 1);
                for (int k = 0; k < K; k++) {
                    m.inner_iters++;
                    acc += ldA(ci, k) * ldB(k, cj);
                }
                stC(ci, cj, acc, true);
                m.assign_stores++;
            }
        finalize(m);
        return m;
    }

    // ---------- 错误复现 3：off-by-one，min 上界写成 M-1 ----------
    Metrics run_off_by_one() {
        Metrics m;
        m.name = "off-by-one(min(..,M-1))";
        resetInstr(); resetC();
        for (int i0 = 0; i0 < M; i0 += TM) {
            int ihi = std::min(i0 + TM, M - 1);
            m.boundary_ops++;
            for (int j0 = 0; j0 < N; j0 += TN) {
                int jhi = std::min(j0 + TN, N - 1);
                m.boundary_ops++;
                for (int k0 = 0; k0 < K; k0 += TK) {
                    int khi = std::min(k0 + TK, K - 1);
                    m.boundary_ops++;
                    for (int i = i0; i < ihi; i++)
                        for (int j = j0; j < jhi; j++)
                            for (int k = k0; k < khi; k++) {
                                m.inner_iters++;
                                stC(i, j, ldC(i, j) + ldA(i, k) * ldB(k, j));
                            }
                }
            }
        }
        finalize(m);
        return m;
    }
};

static void print_header() {
    std::printf("%-26s %7s %12s %13s %10s %10s %10s %9s\n",
                "strategy", "correct", "inner_iters", "guard/idle",
                "boundary", "oob", "dup_write", "max/elem");
}
static void print_row(const Metrics &m) {
    std::printf("%-26s %7s %12lld %4lld/%-8lld %10lld %10lld %10lld %9lld\n",
                m.name.c_str(), m.correct ? "yes" : "NO",
                m.inner_iters, m.guard_checks, m.idle_iters,
                m.boundary_ops, m.oob_touches, m.duplicate_writes,
                m.max_assign_per_elem);
}

int main(int argc, char **argv) {
    if (argc < 7) {
        std::fprintf(stderr,
                     "usage: %s M N K TM TN TK [--all|--suite|--mode NAME]\n",
                     argv[0]);
        return 2;
    }
    int M = atoi(argv[1]), N = atoi(argv[2]), K = atoi(argv[3]);
    int TM = atoi(argv[4]), TN = atoi(argv[5]), TK = atoi(argv[6]);
    std::string mode = argc >= 8 ? argv[7] : "--all";
    if (M <= 0 || N <= 0 || K <= 0 || TM <= 0 || TN <= 0 || TK <= 0) {
        std::fprintf(stderr, "M,N,K,TM,TN,TK 必须均为正整数\n");
        return 2;
    }

    if (mode == "--suite") {
        struct Case { int m, n, k, tm, tn, tk; const char *tag; };
        std::vector<Case> cases = {
            {5, 7, 3, 2, 4, 2, "三个维度都有尾部"},
            {1, 7, 3, 2, 4, 2, "M=1"},
            {5, 1, 3, 2, 4, 2, "N=1"},
            {5, 7, 1, 2, 4, 2, "K=1"},
            {9, 9, 9, 4, 4, 4, "每个维度余 1"},
            {7, 7, 7, 8, 8, 8, "Tile 比维度还大"},
            {64, 64, 64, 16, 16, 16, "完全整除（回归 Day 94）"},
            {65, 63, 33, 16, 16, 16, "大 shape 全带尾"},
            {3, 100, 2, 2, 32, 5, "瘦长 N"},
            {100, 3, 17, 16, 2, 3, "瘦长 M"},
        };
        int fails = 0, total = 0;
        std::printf("%-30s %-26s %-20s %-20s %s\n", "case(M N K | T)",
                    "说明", "guard", "minclamp", "epilogue");
        for (auto &c : cases) {
            Runner r(c.m, c.n, c.k, c.tm, c.tn, c.tk);
            char buf[64];
            std::snprintf(buf, sizeof buf, "%dx%dx%d | %dx%dx%d", c.m, c.n,
                          c.k, c.tm, c.tn, c.tk);
            Metrics a = r.run_guard(), b = r.run_minclamp(),
                    d = r.run_epilogue();
            std::printf("%-30s %-26s %-20s %-20s %s\n", buf, c.tag,
                        a.correct ? "PASS(逐位相等)" : "FAIL",
                        b.correct ? "PASS(逐位相等)" : "FAIL",
                        d.correct ? "PASS(逐位相等)" : "FAIL");
            for (Metrics *pm : {&a, &b, &d}) {
                total++;
                if (!pm->correct) fails++;
            }
        }
        std::printf("\n== suite 结果：%d/%d 通过 ==\n", total - fails, total);
        return fails == 0 ? 0 : 1;
    }

    Runner r(M, N, K, TM, TN, TK);
    if (mode == "--all") {
        Metrics g = r.run_guard(), c = r.run_minclamp(), e = r.run_epilogue();
        std::printf("shape: M=%d N=%d K=%d, tile: TM=%d TN=%d TK=%d, "
                    "useful_flops(M*N*K)=%d, tiles=%d\n",
                    M, N, K, TM, TN, TK, M * N * K,
                    ((M + TM - 1) / TM) * ((N + TN - 1) / TN) *
                        ((K + TK - 1) / TK));
        print_header();
        print_row(g); print_row(c); print_row(e);
        int bad = 0;
        for (Metrics *pm : {&g, &c, &e}) if (!pm->correct) bad++;
        std::printf("== 正确性：%s（与参考逐位比较） ==\n",
                    bad == 0 ? "3/3 全部逐位相等" : "存在失败！");
        return bad == 0 ? 0 : 1;
    }
    if (mode == "--mode") {
        std::string which = argc >= 9 ? argv[8] : "";
        Metrics m;
        if (which == "danger") m = r.run_danger();
        else if (which == "clamp-store") m = r.run_clamp_store();
        else if (which == "off-by-one") m = r.run_off_by_one();
        else {
            std::fprintf(stderr,
                         "未知复现模式：%s（可选 danger|clamp-store|off-by-one）\n",
                         which.c_str());
            return 2;
        }
        std::printf("shape: M=%d N=%d K=%d, tile: TM=%d TN=%d TK=%d, mode=%s\n",
                    M, N, K, TM, TN, TK, which.c_str());
        print_header();
        print_row(m);
        std::printf("inner_iters=%lld oob_touches=%lld assign_stores=%lld "
                    "duplicate_writes=%lld max_assign_per_elem=%lld "
                    "max_abs_err=%.3f correct=%s\n",
                    m.inner_iters, m.oob_touches, m.assign_stores,
                    m.duplicate_writes, m.max_assign_per_elem,
                    m.max_abs_err, m.correct ? "yes" : "NO");
        return 0;
    }
    std::fprintf(stderr, "未知模式：%s（可选 --all|--suite|--mode NAME）\n",
                 mode.c_str());
    return 2;
}
