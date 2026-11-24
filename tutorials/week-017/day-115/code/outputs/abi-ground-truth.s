; gcc -O2 -S 编译产物（第 115 天，真实输出）
; 输入源码见 func_lowering.py 的 GCC_SRC

	.arch armv8-a
	.file	"abi.c"
	.text
	.align	2
	.p2align 3,,7
	.global	getoff_c
	.type	getoff_c, %function
getoff_c:
.LFB0:
	.cfi_startproc
	ldr	x0, [x0, 16]
	ret
	.cfi_endproc
.LFE0:
	.size	getoff_c, .-getoff_c
	.align	2
	.p2align 3,,7
	.global	getoff_p
	.type	getoff_p, %function
getoff_p:
.LFB1:
	.cfi_startproc
	ldr	x0, [x0, 16]
	ret
	.cfi_endproc
.LFE1:
	.size	getoff_p, .-getoff_p
	.align	2
	.p2align 3,,7
	.global	make_desc
	.type	make_desc, %function
make_desc:
.LFB2:
	.cfi_startproc
	adrp	x0, .LANCHOR0
	add	x0, x0, :lo12:.LANCHOR0
	ldp	x2, x3, [x0]
	stp	x2, x3, [x8]
	ldp	x2, x3, [x0, 16]
	stp	x2, x3, [x8, 16]
	ldp	x2, x3, [x0, 32]
	stp	x2, x3, [x8, 32]
	ldr	x0, [x0, 48]
	str	x0, [x8, 48]
	ret
	.cfi_endproc
.LFE2:
	.size	make_desc, .-make_desc
	.section	.text.startup,"ax",@progbits
	.align	2
	.p2align 3,,7
	.global	main
	.type	main, %function
main:
.LFB3:
	.cfi_startproc
	mov	w0, 56
	ret
	.cfi_endproc
.LFE3:
	.size	main, .-main
	.section	.rodata
	.align	3
	.set	.LANCHOR0,. + 0
.LC0:
	.xword	0
	.xword	0
	.xword	7
	.xword	1
	.xword	2
	.xword	3
	.xword	4
	.ident	"GCC: (Ubuntu 9.4.0-1ubuntu1~20.04.2) 9.4.0"
	.section	.note.GNU-stack,"",@progbits
