// 错误一现场：试图拷贝一个 Tensor。
// 不会产生运行期 bug——类型系统在编译期就把 double free 拦下了。
// 编译：g++ -std=c++17 -I ../src -c err_copy.cpp -o /dev/null
#include "Tensor.h"

int main() {
    Tensor a = Tensor::from_data(2, 3, {1, 2, 3, 4, 5, 6});
    Tensor b = a;   // ← 拷贝构造：unique_ptr 成员已把它删除
    (void)b;
    return 0;
}
