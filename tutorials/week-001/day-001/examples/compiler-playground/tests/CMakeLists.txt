# 测试程序也是普通可执行文件——ctest 不认识任何测试框架，只会运行程序并检查退出码
add_executable(test_greet test_greet.cpp)
# 与主程序链接同一个 libgreet.a：测试跑的是真实实现而不是另一份拷贝（图 3 的“共用”）
target_link_libraries(test_greet PRIVATE greet)

# 向 ctest 注册一条测试：NAME 是 5.3 节报告里显示的名字，COMMAND 是要运行的程序；
# 程序以非 0 退出码结束即判失败——5.4 节实验二里 assert 失败正是靠这一点变红的
add_test(NAME greet_returns_greeting COMMAND test_greet)
