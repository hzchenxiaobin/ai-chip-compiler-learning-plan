	.build_version macos, 27, 2
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_main_kernel                    ; -- Begin function main_kernel
	.p2align	2
_main_kernel:                           ; @main_kernel
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	.cfi_def_cfa_offset 48
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	ldr	x20, [sp, #104]
	ldr	x21, [sp, #48]
	mov	w0, #20480                      ; =0x5000
	mov	x19, x1
	bl	_malloc
	movi	d0, #0000000000000000
	mov	x8, xzr
	mov	x9, xzr
	mov	w10, #160                       ; =0xa0
	b	LBB0_2
LBB0_1:                                 ;   in Loop: Header=BB0_2 Depth=1
	add	x9, x9, #1
	add	x8, x8, #128
LBB0_2:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_5 Depth 2
                                        ;       Child Loop BB0_7 Depth 3
	cmp	x9, #31
	b.gt	LBB0_8
; %bb.3:                                ; %.preheader
                                        ;   in Loop: Header=BB0_2 Depth=1
	mov	x11, xzr
	mov	x12, xzr
	b	LBB0_5
LBB0_4:                                 ;   in Loop: Header=BB0_5 Depth=2
	fcmp	s1, #0.0
	madd	x13, x9, x10, x12
	add	x12, x12, #1
	add	x11, x11, #4
	fcsel	s1, s1, s0, gt
	str	s1, [x0, x13, lsl #2]
LBB0_5:                                 ;   Parent Loop BB0_2 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_7 Depth 3
	cmp	x12, #159
	b.gt	LBB0_1
; %bb.6:                                ;   in Loop: Header=BB0_5 Depth=2
	ldr	s1, [x20, x12, lsl #2]
	mov	x13, xzr
	mov	x14, x8
	mov	x15, x11
	cmp	x13, #31
	b.gt	LBB0_4
LBB0_7:                                 ;   Parent Loop BB0_2 Depth=1
                                        ;     Parent Loop BB0_5 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldr	s2, [x19, x14]
	ldr	s3, [x21, x15]
	add	x13, x13, #1
	add	x15, x15, #640
	add	x14, x14, #4
	fmul	s2, s2, s3
	fadd	s1, s1, s2
	cmp	x13, #31
	b.le	LBB0_7
	b	LBB0_4
LBB0_8:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	mov	x1, x0
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	mov	x2, xzr
	mov	w3, #32                         ; =0x20
	mov	w4, #160                        ; =0xa0
	mov	w5, #160                        ; =0xa0
	mov	w6, #1                          ; =0x1
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	__mlir_ciface_main_kernel       ; -- Begin function _mlir_ciface_main_kernel
	.p2align	2
__mlir_ciface_main_kernel:              ; @_mlir_ciface_main_kernel
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #128
	stp	x20, x19, [sp, #96]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #112]            ; 16-byte Folded Spill
	.cfi_def_cfa_offset 128
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldp	x8, x4, [x1, #24]
	mov	x19, x0
	ldp	x10, x9, [x1, #8]
	ldr	x11, [x1]
	ldp	x5, x6, [x1, #40]
	ldr	x7, [x2]
	mov	x0, x11
	ldur	q0, [x2, #8]
	ldur	q1, [x2, #24]
	mov	x1, x10
	ldr	x14, [x3, #32]
	ldp	x12, x13, [x2, #40]
	mov	x2, x9
	ldp	q2, q3, [x3]
	mov	x3, x8
	str	x14, [sp, #80]
	stp	x12, x13, [sp, #32]
	stp	q0, q1, [sp]
	stp	q2, q3, [sp, #48]
	bl	_main_kernel
	stp	x0, x1, [x19]
	ldp	x29, x30, [sp, #112]            ; 16-byte Folded Reload
	stp	x2, x3, [x19, #16]
	stp	x4, x5, [x19, #32]
	str	x6, [x19, #48]
	ldp	x20, x19, [sp, #96]             ; 16-byte Folded Reload
	add	sp, sp, #128
	ret
	.cfi_endproc
                                        ; -- End function
.subsections_via_symbols
