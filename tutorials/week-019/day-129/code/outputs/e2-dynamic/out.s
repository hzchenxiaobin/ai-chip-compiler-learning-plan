	.build_version macos, 27, 2
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_kernel_dynamic                 ; -- Begin function kernel_dynamic
	.p2align	2
_kernel_dynamic:                        ; @kernel_dynamic
	.cfi_startproc
; %bb.0:
	stp	x26, x25, [sp, #-80]!           ; 16-byte Folded Spill
	stp	x24, x23, [sp, #16]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #32]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #48]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #64]             ; 16-byte Folded Spill
	.cfi_def_cfa_offset 80
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	ldp	x20, x24, [sp, #104]
	mov	x21, x5
	ldr	x25, [sp, #80]
	mov	x22, x4
	mov	x19, x3
	mov	x23, x1
	mul	x8, x20, x3
	lsl	x0, x8, #2
	bl	_malloc
	mov	x8, xzr
	b	LBB0_2
LBB0_1:                                 ;   in Loop: Header=BB0_2 Depth=1
	add	x8, x8, #1
LBB0_2:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_5 Depth 2
                                        ;       Child Loop BB0_7 Depth 3
	cmp	x8, x19
	b.ge	LBB0_8
; %bb.3:                                ; %.preheader1
                                        ;   in Loop: Header=BB0_2 Depth=1
	mov	x9, xzr
	b	LBB0_5
LBB0_4:                                 ;   in Loop: Header=BB0_5 Depth=2
	madd	x10, x8, x20, x9
	add	x9, x9, #1
	str	s0, [x0, x10, lsl #2]
LBB0_5:                                 ;   Parent Loop BB0_2 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_7 Depth 3
	cmp	x9, x20
	b.ge	LBB0_1
; %bb.6:                                ; %.preheader
                                        ;   in Loop: Header=BB0_5 Depth=2
	movi	d0, #0000000000000000
	mov	x10, xzr
	cmp	x10, x22
	b.ge	LBB0_4
LBB0_7:                                 ;   Parent Loop BB0_2 Depth=1
                                        ;     Parent Loop BB0_5 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	madd	x11, x8, x21, x10
	madd	x12, x10, x24, x9
	add	x10, x10, #1
	ldr	s1, [x23, x11, lsl #2]
	ldr	s2, [x25, x12, lsl #2]
	fmul	s1, s1, s2
	fadd	s0, s0, s1
	cmp	x10, x22
	b.lt	LBB0_7
	b	LBB0_4
LBB0_8:
	mov	x3, x19
	mov	x4, x20
	mov	x5, x20
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	mov	x1, x0
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	mov	x2, xzr
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	mov	w6, #1                          ; =0x1
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	__mlir_ciface_kernel_dynamic    ; -- Begin function _mlir_ciface_kernel_dynamic
	.p2align	2
__mlir_ciface_kernel_dynamic:           ; @_mlir_ciface_kernel_dynamic
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
	bl	_kernel_dynamic
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
