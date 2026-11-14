	.file	"<string>"
	.text
	.globl	step
	.p2align	2
	.type	step,@function
step:
	.cfi_startproc
	add	w8, w0, #20
	subs	w9, w0, #20
	csel	w0, w8, w9, gt
	ret
.Lfunc_end0:
	.size	step, .Lfunc_end0-step
	.cfi_endproc

	.section	".note.GNU-stack","",@progbits
