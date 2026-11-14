	.text
	.file	"LLVMDialectModule"
	.globl	gemm                            // -- Begin function gemm
	.p2align	2
	.type	gemm,@function
gemm:                                   // @gemm
	.cfi_startproc
// %bb.0:
	str	x30, [sp, #-32]!                // 8-byte Folded Spill
	stp	x20, x19, [sp, #16]             // 16-byte Folded Spill
	.cfi_def_cfa_offset 32
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w30, -32
	ldr	x20, [sp, #32]
	mov	w0, #48                         // =0x30
	mov	x19, x1
	bl	malloc
	mov	x8, xzr
	b	.LBB0_2
.LBB0_1:                                //   in Loop: Header=BB0_2 Depth=1
	add	x8, x8, #1
	add	x19, x19, #24
.LBB0_2:                                // =>This Loop Header: Depth=1
                                        //     Child Loop BB0_5 Depth 2
                                        //       Child Loop BB0_7 Depth 3
	cmp	x8, #3
	b.gt	.LBB0_8
// %bb.3:                               // %.preheader1
                                        //   in Loop: Header=BB0_2 Depth=1
	add	x10, x8, x8, lsl #1
	mov	x9, xzr
	mov	x11, x20
	b	.LBB0_5
.LBB0_4:                                //   in Loop: Header=BB0_5 Depth=2
	add	x12, x10, x9
	add	x9, x9, #1
	add	x11, x11, #4
	str	s0, [x0, x12, lsl #2]
.LBB0_5:                                //   Parent Loop BB0_2 Depth=1
                                        // =>  This Loop Header: Depth=2
                                        //       Child Loop BB0_7 Depth 3
	cmp	x9, #2
	b.gt	.LBB0_1
// %bb.6:                               // %.preheader
                                        //   in Loop: Header=BB0_5 Depth=2
	movi	d0, #0000000000000000
	mov	x12, xzr
	mov	x13, x11
	cmp	x12, #5
	b.gt	.LBB0_4
.LBB0_7:                                //   Parent Loop BB0_2 Depth=1
                                        //     Parent Loop BB0_5 Depth=2
                                        // =>    This Inner Loop Header: Depth=3
	ldr	s1, [x19, x12, lsl #2]
	ldr	s2, [x13], #12
	add	x12, x12, #1
	fmul	s1, s1, s2
	fadd	s0, s0, s1
	cmp	x12, #5
	b.le	.LBB0_7
	b	.LBB0_4
.LBB0_8:
	ldp	x20, x19, [sp, #16]             // 16-byte Folded Reload
	mov	x1, x0
	mov	x2, xzr
	mov	w3, #4                          // =0x4
	mov	w4, #3                          // =0x3
	mov	w5, #3                          // =0x3
	mov	w6, #1                          // =0x1
	ldr	x30, [sp], #32                  // 8-byte Folded Reload
	ret
.Lfunc_end0:
	.size	gemm, .Lfunc_end0-gemm
	.cfi_endproc
                                        // -- End function
	.section	".note.GNU-stack","",@progbits
