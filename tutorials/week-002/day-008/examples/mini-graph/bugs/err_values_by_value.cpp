// 反面教材：把值按值存进 vector，靠地址当「边」。
// vector 扩容会把整个仓库搬到新地址，旧地址整体释放——
// 之前记下的指针全部悬空。ASan 构建下当场报告。

#include <cstdio>
#include <string>
#include <vector>

struct NaiveValue {
    std::int64_t id;
    std::string name;
};

int main() {
    std::vector<NaiveValue> vals;
    for (int i = 0; i < 2; ++i) {
        vals.push_back(NaiveValue{i, "v" + std::to_string(i)});
    }
    const NaiveValue* first = &vals[0];  // 记下「边」指向的地址
    std::printf("第 2 次入库后：first -> %p, id = %lld\n",
                 static_cast<const void*>(first),
                 static_cast<long long>(first->id));

    for (int i = 2; i < 22; ++i) {  // 继续放值，vector 必然扩容搬家
        vals.push_back(NaiveValue{i, "v" + std::to_string(i)});
    }
    std::printf("扩容之后：&vals[0] = %p（仓库已经搬家）\n",
                 static_cast<const void*>(&vals[0]));
    std::printf("再读 first->id = %lld\n",  // 悬空读取，ASan 在这里报告
                static_cast<long long>(first->id));
    return 0;
}
