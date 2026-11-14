	.file	"<string>"
	.text
	.globl	step5
	.p2align	2
	.type	step5,@function
step5:
	.cfi_startproc
	add	w8, w0, #25
	subs	w9, w0, #25
	csel	w0, w8, w9, gt
	ret
.Lfunc_end0:
	.size	step5, .Lfunc_end0-step5
	.cfi_endproc

	.section	".note.GNU-stack","",@progbits
