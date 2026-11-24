// 第 7 天·反面教材：一个"最简单"的 Tensor——裸指针 + 随意拷贝。
//
// 编译（对照组，裸指针）：
//   g++ -std=c++17 -g -Wall -Wextra naive-tensor.cpp -o naive && ./naive
// 编译（实验组，只把裸指针换成 unique_ptr，其余一行不改）：
//   g++ -std=c++17 -g -Wall -Wextra -DUSE_UNIQUE_PTR naive-tensor.cpp -o naive-up
// ASan 版（对照组）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan naive-tensor.cpp -o naive-asan && ./naive-asan
//
// 预测再运行：
//   1) NaiveTensor b = a; 之后改 b 的数据，a 会不会变？
//   2) main 结束时，两个对象的析构函数各自 delete[] 一次——会发生什么？

#include <cstdio>
#include <memory>
#include <string>
#include <vector>

#ifdef USE_UNIQUE_PTR
// ── 实验组：唯一的改动是 float* → unique_ptr<float[]>（第 5 天的手艺）──
class NaiveTensor {
public:
    explicit NaiveTensor(std::size_t n) : data_(new float[n]), n_(n) {}
    // 没写析构：unique_ptr 成员自动释放（第 2 天 RAII 的红利）。
    // 没写拷贝/移动：拷贝被自动删除、移动自动正确（第 5 天"纪律装进类型"）。
    float* data() { return data_.get(); }
    std::size_t size() const { return n_; }

private:
    std::unique_ptr<float[]> data_;
    std::size_t n_;
};
#else
// ── 对照组：裸指针 + 编译器生成的默认拷贝（"简单持有裸指针并随意拷贝"）──
class NaiveTensor {
public:
    explicit NaiveTensor(std::size_t n) : data_(new float[n]), n_(n) {}
    ~NaiveTensor() { delete[] data_; }
    // 注意：拷贝构造 / 拷贝赋值一个字都没写——
    // 编译器生成的版本只抄指针值（浅拷贝），不复制指向的内存。
    float* data() { return data_; }
    std::size_t size() const { return n_; }

private:
    float* data_;
    std::size_t n_;
};
#endif

std::string ptr_str(const void* p) {
    char buf[32];
    std::snprintf(buf, sizeof(buf), "%p", p);
    return buf;
}

int main() {
    // 无缓冲输出：对照组最后会 abort（double free），缓冲的 stdout 会被一起丢掉。
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    NaiveTensor a(6);  // shape 心里想着 (2,3)，元素 1..6
    for (std::size_t i = 0; i < a.size(); ++i) {
        a.data()[i] = static_cast<float>(i + 1);
    }
    std::printf("创建 a（%zu 个元素）：%g %g %g %g %g %g\n", a.size(),
                a.data()[0], a.data()[1], a.data()[2], a.data()[3], a.data()[4], a.data()[5]);
    std::printf("a.data() = %s\n", ptr_str(a.data()).c_str());

    // "随意拷贝"：一行看似人畜无害的代码。
    NaiveTensor b = a;
    std::printf("拷贝出 b：b.data() = %s\n", ptr_str(b.data()).c_str());
    std::printf("a、b 的指针是同一块内存吗？%s\n",
                ptr_str(a.data()) == ptr_str(b.data()) ? "是（同一块！）" : "否");

    // 改 b 的第 0 个元素，然后看 a。
    b.data()[0] = 100.0f;
    std::printf("执行 b.data()[0] = 100 之后：a.data()[0] = %g（改 b，a 跟着变了？）\n",
                a.data()[0]);

    std::printf("main 结束：b 先析构、a 后析构，各自 delete[] 一次……\n");
    return 0;
    // 对照组在这里触发 double free：同一块堆内存被释放两次。
    // 实验组（-DUSE_UNIQUE_PTR）根本编不过"NaiveTensor b = a;"——错误提前到编译期。
}
