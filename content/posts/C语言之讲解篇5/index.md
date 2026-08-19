---
comments: true
title: "C语言之讲解篇5"
date: 2026-08-18
draft: false
ShowToc: false
---
{{< toc >}}

例题：


```
下列程序段的输出结果为（ ）

unsigned long pulArray[] = {6,7,8,9,10};
unsigned long *pulPtr;
pulPtr = pulArray;
*(pulPtr + 3) += 3;
printf("%d,%d\n",*pulPtr, *(pulPtr + 3));

```


解释：pulPtr已经是数组的首元素6，而*(pulPtr + 3)是指针向后移动3位所得到的结果，同时把该结果再加上3所得的值是12，接下来再把12赋值给*(pulPtr + 3)，然后由于指针是数组的首地址那么的话，*pulPtr就是6，而(pulPtr + 3)自然就是12，接下来我们就可以选择6 12了，本题11就这样结束了。
