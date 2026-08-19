---
comments: true
title: "C语言之指针篇第五"
date: 2026-08-18
draft: false
ShowToc: false
---
{{< toc >}}

在本讲中，我们将会详细的学习sizeof以及strlen的区别，同时呢我也会为大家讲一些经典面试题，相信大家在看过我的本讲之后，一定会对指针有更加深刻的认识与了解，下面就开启我们的指针之旅吧。


#### C语言之指针篇第五


- [一.sizeof和strlen的对⽐](#sizeofstrlen_3)


- [1.sizeof](#1sizeof_5)


- [1.sizeof含义](#1sizeof_6)

- [2.例子：](#2_8)


- [2.strlen](#2strlen_20)


- [1.strlen的含义](#1strlen_21)

- [2.例子](#2_23)


- [二.数组指针笔试题解析](#_31)


## 一.sizeof和strlen的对⽐


首先在学习中时，我们通常会经常遇到sizeof，以及strlen函数，我们在使用时经常会分不清sizeof以及strlen，我们经常会用着用着，将两个函数用颠倒，大家对此简直是苦不堪言，因此呢，我将用这节为大家详细介绍两者区别，相信大家在听过我的讲解之后，一定会在今后的学习中，对两者运用的更加之熟练。


### 1.sizeof


#### 1.sizeof含义


sizeof 主要计算的是变量所占内存内存空间⼤⼩的，单位是字节，如果操作数是类型的话，计算的是使⽤类型创建的变量所占内存空间的⼤小，sizeof 只关注占⽤内存空间的⼤⼩，不在乎内存中存放什么数据。


#### 2.例子：


```
int a=1;
sizeof(a);//因此呢，算出的数值是4.

```


又有例子：


```
int a=4;
int * s=&a;
sizeof(s);//可以看出由于地址的存储在内存中是64根地址线或者是32根地址线因此地址无论是整形或者是字符型亦或者是数组型
//它们其实都是4或者8

```


### 2.strlen


#### 1.strlen的含义


它的功能是，求字符的长度，遇到‘\0’则停止，否则会在内存中找到‘\0’,这样才会停下来，如此一番，求出的则是随机值。


#### 2.例子


```
char a="hello bit";
int a=strlen(a);//由于“”省略了\0，因此求出的是8
又有例子：
char a[]={'hello','bit'};
int a=strlen(a);//在这里，由于没有设置‘\0’,那么的话，结果就有可能是随机值。

```


## 二.数组指针笔试题解析


例题1：


```
int a[] = {1,2,3,4};
printf("%d\n",sizeof(a));//sizeof加数组名指的是整个数组的大小，也就是说打印出来的是16.
printf("%d\n",sizeof(a+0));//在这里的意思是，数组的首元素的地址而地址的大小则是4或者8，因此打印出来的是4或者是8
printf("%d\n",sizeof(*a));//在这里指的是数组的首元素，因此答案也就是4
printf("%d\n",sizeof(a+1));//在这里的意思是数组的第二个元素的地址也就是说答案是4或者是8.
printf("%d\n",sizeof(a[1]));//这里是数组的第二个元素，也就是说答案是4
printf("%d\n",sizeof(&a));//这里是数组的地址，也就是说是4或者是8.
printf("%d\n",sizeof(*&a));//注意*&相当于没有因此该式子也就是sizeof(a)，注意是16
12345678
printf("%d\n",sizeof(&a+1));//在这里的意思是指向数组的后面的地址，也就是4或者是8
printf("%d\n",sizeof(&a[0]));//这里是首元素的地址，是4或者是8
printf("%d\n",sizeof(&a[0]+1));//是第二个元素的地址是4或者是8.

```


例题2：


```
char arr[] = {'a','b','c','d','e'};
printf("%d\n", sizeof(arr));//由于没有‘\0’那么的话，就是5
printf("%d\n", sizeof(arr+0));//这里是首元素的地址，那么是4或者是8
printf("%d\n", sizeof(*arr));//是首元素那么就是1
printf("%d\n", sizeof(arr[1]));//在这里也是首元素，那么是1
printf("%d\n", sizeof(&arr));//这里是数组的地址是4或者是8
printf("%d\n", sizeof(&arr+1));//这里是在数组之后的地址，也就是4或者是8
printf("%d\n", sizeof(&arr[0]+1));//是第二个元素地址是4或者是8

```


```
char arr[]="abcdef”；
printf("%d\n",strlen(arr));//这里是说字符串的长度是6
printf("%d\n",strlen(*arr);//在这里会出错。
printf("%d\n",strlen(arr[1]));//在这里也会出错
printf("%d\n",strlen(&arr));//是6
printf("%d\n",strlen(&arr+1));//这会跳出这个数组，应该是0
printf("%d\n",strlen(&arr[0]+1));//这里第二个元素的地址是5

```


完（。）
