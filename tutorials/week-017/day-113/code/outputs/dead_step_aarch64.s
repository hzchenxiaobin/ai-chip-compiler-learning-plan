	.file	"<string>"
	.text
	.globl	step_dead
	.p2align	2
	.type	step_dead,@function
step_dead:
	.cfi_startproc
	add	w8, w0, #20
	subs	w9, w0, #20
	csel	w0, w8, w9, gt
	ret
.Lfunc_end0:
	.size	step_dead, .Lfunc_end0-step_dead
	.cfi_endproc

	.section	".note.GNU-stack","",@progbits
