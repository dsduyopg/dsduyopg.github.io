---
comments: true
title: "C语言的分支与循环上"
date: 2026-08-18
draft: false
ShowToc: false
---
{{< toc >}}

## if语句


在if语句中他的语法是if(表达式)


                                       语句


表达式成立那么语句执行，不成立那么语句不执行。


在if语句中只要是true就执行，false不执行。


那么true通常是1，而false则是0，比如nun%2==1，它执行的是判断num是否是奇数，其实这样写也可以，但是不是更很直观


没有前者更加直观一些。


在if语句中if语句只可以跟着一条语句，但是如果过于多的话可以调整为大括号


由此我们可以知道这样的道理，else是在一些情况可以省略的，不必再写像


if(num%2)


   printf("%d 是奇数"，num);


printf("%d 是偶数",num);


 


 


 


 


##
