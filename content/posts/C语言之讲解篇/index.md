---
comments: true
title: "C语言之讲解篇"
date: 2026-08-18
draft: false
---
例题：


```
下面代码的结果是：

#include <stdio.h>
int i;
int main()
{
    i--;
    if (i > sizeof(i))
    {
        printf(">\n");
    }
    else
    {
        printf("<\n");
    }
    return 0;
}

```


>


A.>

B.<

C.不输出

D.程序有问题

首先，我可以明确一点的是，这道题不选择D和C，在本函数中，由于int i 是一个全局变量，它存放的是静态区，

C标准是要求全局变量要被初始化为零值，因此即使你没有初始化该值那么依然会被系统初始化为0，然而，sizeof类型是属于unsigned int 类型，也就是说，-1需要进行一拨转换，然而-1转换为无符号整形数字是比较大的，那么的话，明显是>,那么就选则的是A
