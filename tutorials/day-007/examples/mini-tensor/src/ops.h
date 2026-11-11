#pragma once

#include "Tensor.h"

// 第 7 天修复的本周遗留：第 6 天必做练习——逐元素加法（第 9 天 Add 算子的前身）。
//
// 签名的所有权语义（本周复盘的三种关系一次用全）：
//   参数 const Tensor&  借用——不拿走所有权，函数返回后 a、b 原封不动；
//   返回值 Tensor        按值——返回的是即将销毁的局部对象，移动接管，不触发拷贝；
//   结果的数据           新分配——Tensor::zeros 开新仓库，与 a、b 的存储零别名。
Tensor add(const Tensor& a, const Tensor& b);
