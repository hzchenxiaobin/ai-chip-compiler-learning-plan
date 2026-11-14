	.file	"<string>"
	.section	.ltext,"axl",@progbits
	.globl	step5
	.p2align	4
	.type	step5,@function
step5:
	.cfi_startproc
	leal	-25(%rdi), %ecx
	leal	25(%rdi), %eax
	cmpl	$26, %edi
	cmovll	%ecx, %eax
	retq
.Lfunc_end0:
	.size	step5, .Lfunc_end0-step5
	.cfi_endproc

	.section	".note.GNU-stack","",@progbits
