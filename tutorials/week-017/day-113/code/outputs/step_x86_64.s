	.file	"<string>"
	.section	.ltext,"axl",@progbits
	.globl	step
	.p2align	4
	.type	step,@function
step:
	.cfi_startproc
	leal	-20(%rdi), %ecx
	leal	20(%rdi), %eax
	cmpl	$21, %edi
	cmovll	%ecx, %eax
	retq
.Lfunc_end0:
	.size	step, .Lfunc_end0-step
	.cfi_endproc

	.section	".note.GNU-stack","",@progbits
