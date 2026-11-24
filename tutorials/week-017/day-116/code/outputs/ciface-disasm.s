; 第 116 天：@add 与 _mlir_ciface_add 的真实汇编（llvmlite LLVM 22 输出，aarch64；noinline 保留调用边界）
	.file	"<string>"
	.text
	.p2align	2
	.type	add,@function
add:
	.cfi_startproc
	str	x30, [sp, #-80]!
	stp	x26, x25, [sp, #16]
	stp	x24, x23, [sp, #32]
	stp	x22, x21, [sp, #48]
	stp	x20, x19, [sp, #64]
	.cfi_def_cfa_offset 80
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -24
	.cfi_offset w22, -32
	.cfi_offset w23, -40
	.cfi_offset w24, -48
	.cfi_offset w25, -56
	.cfi_offset w26, -64
	.cfi_offset w30, -80
	ldp	x23, x24, [sp, #112]
	mov	w0, #16
	ldp	x26, x25, [sp, #80]
	mov	x19, x6
	mov	x20, x5
	mov	x21, x2
	mov	x22, x1
	bl	malloc
	ldr	s0, [x22, x21, lsl #2]
	ldr	s1, [x26, x25, lsl #2]
	add	x8, x21, x19
	add	x9, x25, x24
	mov	x1, x0
	mov	x2, xzr
	fadd	s0, s0, s1
	mov	w3, #2
	mov	w4, #2
	mov	w5, #2
	mov	w6, #1
	str	s0, [x0]
	ldr	s0, [x22, x8, lsl #2]
	ldr	s1, [x26, x9, lsl #2]
	add	x8, x21, x20
	add	x9, x25, x23
	fadd	s0, s0, s1
	str	s0, [x0, #4]
	ldr	s0, [x22, x8, lsl #2]
	ldr	s1, [x26, x9, lsl #2]
	add	x8, x8, x19
	add	x9, x9, x24
	ldp	x20, x19, [sp, #64]
	fadd	s0, s0, s1
	ldp	x24, x23, [sp, #32]
	str	s0, [x0, #8]
	ldr	s0, [x22, x8, lsl #2]
	ldr	s1, [x26, x9, lsl #2]
	ldp	x22, x21, [sp, #48]
	fadd	s0, s0, s1
	ldp	x26, x25, [sp, #16]
	str	s0, [x0, #12]
	ldr	x30, [sp], #80
	ret
.Lfunc_end0:
	.size	add, .Lfunc_end0-add
	.cfi_endproc

	.globl	_mlir_ciface_add
	.p2align	2
	.type	_mlir_ciface_add,@function
_mlir_ciface_add:
	.cfi_startproc
	sub	sp, sp, #64
	stp	x30, x19, [sp, #48]
	.cfi_def_cfa_offset 64
	.cfi_offset w19, -8
	.cfi_offset w30, -16
	ldp	x9, x8, [x0, #8]
	mov	x19, x2
	ldp	x5, x6, [x0, #40]
	ldr	x7, [x1]
	ldp	x3, x4, [x0, #24]
	ldr	x0, [x0]
	mov	x2, x8
	ldur	q0, [x1, #8]
	ldur	q1, [x1, #24]
	ldp	x10, x11, [x1, #40]
	mov	x1, x9
	stp	q0, q1, [sp]
	stp	x10, x11, [sp, #32]
	bl	add
	stp	x0, x1, [x19]
	stp	x2, x3, [x19, #16]
	stp	x4, x5, [x19, #32]
	str	x6, [x19, #48]
	ldp	x30, x19, [sp, #48]
	add	sp, sp, #64
	ret
.Lfunc_end1:
	.size	_mlir_ciface_add, .Lfunc_end1-_mlir_ciface_add
	.cfi_endproc

	.section	".note.GNU-stack","",@progbits
