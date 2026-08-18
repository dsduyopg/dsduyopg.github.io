---
title: "C语言之讲解篇4"
date: 2026-08-18
draft: false
---
例题：


```
下面代码的结果是：（          ）

#include <stdio.h>
int main()
{
  int arr[] = {1,2,3,4,5};
  short *p = (short*)arr;
  int i = 0;
  for(i=0; i<4; i++)
  {
    *(p+i) = 0;
  }

  for(i=0; i<5; i++)
  {
    printf("%d ", arr[i]);
  }
  return 0;
}

```


由于short是短整型的，那么其，因此p每次只能得到两个字节，而由于原来是4次循环那么其实是相当于4/2=2个数，也就是说对原来的前两个数赋值为0，那么打印出来得话，自然是：0,0，3,4，5
