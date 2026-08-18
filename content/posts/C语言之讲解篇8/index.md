---
title: "C语言之讲解篇8"
date: 2026-08-18
draft: false
---
例题：


>


输入一个整数数组，实现一个函数，来调整该数组中数字的顺序使得数组中所有的奇数位于数组的前半部分,所有偶数位于数组的后半部分。


## 1.首先设置一个逆序输出的函数。


由于他们是没有任何返回值的因此呢，我们可以设定一个没有一个返回值的函数，同时还需要做到，对原来的函数进行修改，因此我们考虑使用数组或者指针。所以结合以上，所设置的函数可以是：


```
void swap_arr(int arr[], int sz);

```


## 2.其次呢再设定两个变量，left,right.


### 1.left,right的初始化


>


在这里，我们首先可以假定left是数组的最小者，而right是数组的最大者，由于数组的小标是从0开始的那么最大者就是数组的长度减去1，而求数组的长度就可以使用sz，那么的话，最大者就是：sz-1


```
left 0;
right sz-1;

```


### 2.left与right的具体实现


#### 1.left的具体实现


`是通过遇到偶数时停止循环造成的。`


##### 1.left的的执行功能


left首先是定义为寻找奇数，而遇到偶数时就停止循环，并将那个偶数带回到left身上。


#### 2.实现操作与基本逻辑


我们可以通过循环来实现，在众多的循环当中我们可以选择的是，while循环而循环条件就是小标为left的数组，是奇数并且保证left<=right，当其为偶数时就跳出循环。

基本语句如下：


```
while(left<right)
	{
     // 从前往后，找到一个偶数，找到后停止
		while((left<right)&&(arr[left]%2==1))
		{
			left++;
		}
	}

```


#### 2.right的具体实现


`是通过遇到奇数时停止循环造成的。`


##### 1.right的的执行功能


right首先是定义为寻找偶数数，而遇到奇数时就停止循环，并将那个偶数带回到right身上。


#### 2.实现操作与基本逻辑


我们可以通过循环来实现，在众多的循环当中我们可以选择的是，while循环而循环条件就是下标为right的数组，是偶数并且保证left<=right，当其为奇数时就跳出循环。

基本语句如下：


```
while((left<right)&& (arr[right]%2==0))
		{
			right--;
		}

```


### 3.最后是left,ritht的交换与现实


最后我们将这些整合在一起，得到了函数并将left,right进行交换，由于left是偶数，right是奇数俩者交换，求出则为奇数在前偶数在后，函数完整的代码如下：


```
void swap_arr(int arr[], int sz)
{
	int left = 0;
	int right = sz-1;
	int tmp = 0;


	while(left<right)
	{
     // 从前往后，找到一个偶数，找到后停止
		while((left<right)&&(arr[left]%2==1))
		{
			left++;
		}

		// 从后往前找，找一个奇数，找到后停止
		while((left<right)&& (arr[right]%2==0))
		{
			right--;
		}

     // 如果偶数和奇数都找到，交换这两个数据的位置
     // 然后继续找，直到两个指针相遇
		if(left<right)
		{
			tmp = arr[left];
			arr[left] = arr[right];
			arr[right] = tmp;
		}
	}
}

```


## 3.最后就可完成函数了。


将函数部分搞定之后我们就可以，把整个代码搞定了，如下：


```
#include<stdio.h>
void swap_arr(int arr[], int sz)
{
	int left = 0;
	int right = sz-1;
	int tmp = 0;


	while(left<right)
	{
     // 从前往后，找到一个偶数，找到后停止
		while((left<right)&&(arr[left]%2==1))
		{
			left++;
		}

		// 从后往前找，找一个奇数，找到后停止
		while((left<right)&& (arr[right]%2==0))
		{
			right--;
		}

     // 如果偶数和奇数都找到，交换这两个数据的位置
     // 然后继续找，直到两个指针相遇
		if(left<right)
		{
			tmp = arr[left];
			arr[left] = arr[right];
			arr[right] = tmp;
		}
	}
}
int main() {

    int arr[] = {1, 2, 3, 4, 5, 6, 7, 8, 9};

    int len = sizeof(arr) / sizeof(arr[0]);
       swap_arr(arr, len);
    for (int i = 0; i < len; i++) {
        printf("%d ", arr[i]);

    }

    return 0;

}
最后我们写这个代码，他可以实现对于无符号整形数组实现奇数在前，偶数在后，我们搞定了本函数。

```
