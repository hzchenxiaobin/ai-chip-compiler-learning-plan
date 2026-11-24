	.file	"<string>"
	.section	.ltext,"axl",@progbits
	.globl	step_dead
	.p2align	4
	.type	step_dead,@function
step_dead:
	.cfi_startproc
	leal	-20(%rdi), %ecx
	leal	20(%rdi), %eax
	cmpl	$21, %edi
	cmovll	%ecx, %eax
	retq
.Lfunc_end0:
	.size	step_dead, .Lfunc_end0-step_dead
	.cfi_endproc

	.section	".note.GNU-stack","",@progbits
