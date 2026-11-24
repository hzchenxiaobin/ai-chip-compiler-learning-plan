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
	mov	w0, #48                         ; =0x30
	mov	x19, x1
	bl	_malloc
	movi	d0, #0000000000000000
	mov	x8, xzr
	mov	x9, xzr
	b	LBB0_2
LBB0_1:                                 ;   in Loop: Header=BB0_2 Depth=1
	add	x9, x9, #1
	add	x8, x8, #24
LBB0_2:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_5 Depth 2
                                        ;       Child Loop BB0_8 Depth 3
                                        ;         Child Loop BB0_11 Depth 4
                                        ;           Child Loop BB0_14 Depth 5
                                        ;             Child Loop BB0_16 Depth 6
	cmp	x9, #3
	b.gt	LBB0_17
; %bb.3:                                ; %.preheader3
                                        ;   in Loop: Header=BB0_2 Depth=1
	mov	x10, xzr
	mov	x11, xzr
	b	LBB0_5
LBB0_4:                                 ;   in Loop: Header=BB0_5 Depth=2
	add	x11, x11, #1
	add	x10, x10, #4
LBB0_5:                                 ;   Parent Loop BB0_2 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_8 Depth 3
                                        ;         Child Loop BB0_11 Depth 4
                                        ;           Child Loop BB0_14 Depth 5
                                        ;             Child Loop BB0_16 Depth 6
	cmp	x11, #2
	b.gt	LBB0_1
; %bb.6:                                ; %.preheader2
                                        ;   in Loop: Header=BB0_5 Depth=2
	mov	x12, xzr
	b	LBB0_8
LBB0_7:                                 ;   in Loop: Header=BB0_8 Depth=3
	add	x12, x12, #1
LBB0_8:                                 ;   Parent Loop BB0_2 Depth=1
                                        ;     Parent Loop BB0_5 Depth=2
                                        ; =>    This Loop Header: Depth=3
                                        ;         Child Loop BB0_11 Depth 4
                                        ;           Child Loop BB0_14 Depth 5
                                        ;             Child Loop BB0_16 Depth 6
	cmp	x12, #5
	b.gt	LBB0_4
; %bb.9:                                ; %.preheader1
                                        ;   in Loop: Header=BB0_8 Depth=3
	mov	x13, x8
	mov	x14, x9
	b	LBB0_11
LBB0_10:                                ;   in Loop: Header=BB0_11 Depth=4
	add	x14, x14, #1
	add	x13, x13, #24
LBB0_11:                                ;   Parent Loop BB0_2 Depth=1
                                        ;     Parent Loop BB0_5 Depth=2
                                        ;       Parent Loop BB0_8 Depth=3
                                        ; =>      This Loop Header: Depth=4
                                        ;           Child Loop BB0_14 Depth 5
                                        ;             Child Loop BB0_16 Depth 6
	cmp	x14, #3
	b.gt	LBB0_7
; %bb.12:                               ; %.preheader
                                        ;   in Loop: Header=BB0_11 Depth=4
	add	x15, x14, x14, lsl #1
	mov	x16, x10
	mov	x17, x11
	b	LBB0_14
LBB0_13:                                ;   in Loop: Header=BB0_14 Depth=5
	fcmp	s1, #0.0
	add	x1, x15, x17
	add	x17, x17, #1
	add	x16, x16, #4
	fcsel	s1, s1, s0, gt
	str	s1, [x0, x1, lsl #2]
LBB0_14:                                ;   Parent Loop BB0_2 Depth=1
                                        ;     Parent Loop BB0_5 Depth=2
                                        ;       Parent Loop BB0_8 Depth=3
                                        ;         Parent Loop BB0_11 Depth=4
                                        ; =>        This Loop Header: Depth=5
                                        ;             Child Loop BB0_16 Depth 6
	cmp	x17, #2
	b.gt	LBB0_10
; %bb.15:                               ;   in Loop: Header=BB0_14 Depth=5
	ldr	s1, [x20, x17, lsl #2]
	mov	x1, xzr
	mov	x2, x13
	mov	x3, x16
	cmp	x1, #5
	b.gt	LBB0_13
LBB0_16:                                ;   Parent Loop BB0_2 Depth=1
                                        ;     Parent Loop BB0_5 Depth=2
                                        ;       Parent Loop BB0_8 Depth=3
                                        ;         Parent Loop BB0_11 Depth=4
                                        ;           Parent Loop BB0_14 Depth=5
                                        ; =>          This Inner Loop Header: Depth=6
	ldr	s2, [x19, x2]
	ldr	s3, [x21, x3]
	add	x1, x1, #1
	add	x3, x3, #12
	add	x2, x2, #4
	fmul	s2, s2, s3
	fadd	s1, s1, s2
	cmp	x1, #5
	b.le	LBB0_16
	b	LBB0_13
LBB0_17:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	mov	x1, x0
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	mov	x2, xzr
	mov	w3, #4                          ; =0x4
	mov	w4, #3                          ; =0x3
	mov	w5, #3                          ; =0x3
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
