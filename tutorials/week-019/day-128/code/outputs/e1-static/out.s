	.build_version macos, 27, 2
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_kernel_static                  ; -- Begin function kernel_static
	.p2align	2
_kernel_static:                         ; @kernel_static
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	.cfi_def_cfa_offset 32
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldr	x20, [sp, #32]
	mov	w0, #48                         ; =0x30
	mov	x19, x1
	bl	_malloc
	mov	x8, xzr
	mov	x9, xzr
	b	LBB0_2
LBB0_1:                                 ;   in Loop: Header=BB0_2 Depth=1
	add	x9, x9, #1
	add	x8, x8, #24
LBB0_2:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_5 Depth 2
                                        ;       Child Loop BB0_7 Depth 3
	cmp	x9, #3
	b.gt	LBB0_8
; %bb.3:                                ; %.preheader1
                                        ;   in Loop: Header=BB0_2 Depth=1
	add	x11, x9, x9, lsl #1
	mov	x10, xzr
	mov	x12, xzr
	b	LBB0_5
LBB0_4:                                 ;   in Loop: Header=BB0_5 Depth=2
	add	x13, x11, x12
	add	x12, x12, #1
	add	x10, x10, #4
	str	s0, [x0, x13, lsl #2]
LBB0_5:                                 ;   Parent Loop BB0_2 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_7 Depth 3
	cmp	x12, #2
	b.gt	LBB0_1
; %bb.6:                                ; %.preheader
                                        ;   in Loop: Header=BB0_5 Depth=2
	movi	d0, #0000000000000000
	mov	x13, xzr
	mov	x14, x8
	mov	x15, x10
	cmp	x13, #5
	b.gt	LBB0_4
LBB0_7:                                 ;   Parent Loop BB0_2 Depth=1
                                        ;     Parent Loop BB0_5 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldr	s1, [x19, x14]
	ldr	s2, [x20, x15]
	add	x13, x13, #1
	add	x15, x15, #12
	add	x14, x14, #4
	fmul	s1, s1, s2
	fadd	s0, s0, s1
	cmp	x13, #5
	b.le	LBB0_7
	b	LBB0_4
LBB0_8:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	mov	x1, x0
	mov	x2, xzr
	mov	w3, #4                          ; =0x4
	mov	w4, #3                          ; =0x3
	mov	w5, #3                          ; =0x3
	mov	w6, #1                          ; =0x1
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	__mlir_ciface_kernel_static     ; -- Begin function _mlir_ciface_kernel_static
	.p2align	2
__mlir_ciface_kernel_static:            ; @_mlir_ciface_kernel_static
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #80
	stp	x20, x19, [sp, #48]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #64]             ; 16-byte Folded Spill
	.cfi_def_cfa_offset 80
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldp	x9, x8, [x1, #8]
	mov	x19, x0
	ldp	x5, x6, [x1, #40]
	ldr	x10, [x1]
	ldp	x3, x4, [x1, #24]
	ldr	x7, [x2]
	mov	x0, x10
	mov	x1, x9
	ldur	q0, [x2, #8]
	ldp	x11, x12, [x2, #40]
	ldur	q1, [x2, #24]
	mov	x2, x8
	stp	q0, q1, [sp]
	stp	x11, x12, [sp, #32]
	bl	_kernel_static
	stp	x0, x1, [x19]
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	stp	x2, x3, [x19, #16]
	stp	x4, x5, [x19, #32]
	str	x6, [x19, #48]
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	add	sp, sp, #80
	ret
	.cfi_endproc
                                        ; -- End function
.subsections_via_symbols
