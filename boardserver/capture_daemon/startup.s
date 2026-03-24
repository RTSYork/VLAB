/*
 * Minimal ARM Cortex-A9 startup for Core 1 capture daemon.
 * Sets up vector table, stack pointer, and jumps to main().
 * No interrupts, no MMU, no cache init — we want caches OFF
 * to ensure we read fresh data from DDR.
 *
 * Exception handlers write fault diagnostics to shared memory
 * so the host can read them via JTAG for debugging.
 */

/* Shared memory addresses — above the stack top (0x1FDFF000) */
.equ DONE_FLAG_ADDR,    0x1FDFF008
.equ FAULT_TYPE_ADDR,   0x1FDFF010
.equ FAULT_PC_ADDR,     0x1FDFF014
.equ FAULT_DFAR_ADDR,   0x1FDFF018
.equ FAULT_DFSR_ADDR,   0x1FDFF01C

/*
 * Vector table — must be 32-byte aligned.
 * VBAR is set to point here during startup.
 */
.section .text.vectors
.align 5
.global vector_table
vector_table:
    b       _start              /* 0x00: Reset */
    b       _undef_handler      /* 0x04: Undefined Instruction */
    b       _svc_handler        /* 0x08: SVC */
    b       _pabort_handler     /* 0x0C: Prefetch Abort */
    b       _dabort_handler     /* 0x10: Data Abort */
    b       .                   /* 0x14: Reserved */
    b       .                   /* 0x18: IRQ (spin) */
    b       .                   /* 0x1C: FIQ (spin) */

/*
 * Entry point — execution starts here after dow + con.
 */
.section .text.startup
.global _start

_start:
    /* Switch to SVC mode with IRQ/FIQ disabled */
    cps     #0x13
    cpsid   if

    /* Set VBAR to our vector table */
    ldr     r0, =vector_table
    mcr     p15, 0, r0, c12, c0, 0
    isb

    /* Disable alignment fault checking (clear SCTLR.A bit)
     * and ensure MMU and D-cache are off */
    mrc     p15, 0, r0, c1, c0, 0
    bic     r0, r0, #(1 << 1)      /* Clear A — no alignment faults */
    bic     r0, r0, #(1 << 0)      /* Clear M — MMU off */
    bic     r0, r0, #(1 << 2)      /* Clear C — D-cache off */
    mcr     p15, 0, r0, c1, c0, 0
    isb

    /* Enable VFP/NEON — the JPEG encoder uses floating point */
    /* Enable CP10 and CP11 in the Coprocessor Access Control Register */
    mrc     p15, 0, r0, c1, c0, 2
    orr     r0, r0, #(0xF << 20)   /* Full access for CP10 and CP11 */
    mcr     p15, 0, r0, c1, c0, 2
    isb
    /* Set the FPEXC.EN bit to enable the FPU */
    mov     r0, #(1 << 30)
    vmsr    fpexc, r0

    /* Clear fault diagnostic area */
    ldr     r0, =FAULT_TYPE_ADDR
    mov     r1, #0
    str     r1, [r0]
    str     r1, [r0, #4]
    str     r1, [r0, #8]
    str     r1, [r0, #12]

    /* Set stack pointer — ~1MB stack region below params */
    ldr     sp, =_stack_top

    /* Clear BSS */
    ldr     r0, =__bss_start
    ldr     r1, =__bss_end
    mov     r2, #0
.Lclear_bss:
    cmp     r0, r1
    bge     .Lbss_done
    str     r2, [r0], #4
    b       .Lclear_bss
.Lbss_done:

    /* Call main */
    bl      main

    /* If main returns, enter WFI loop */
.Lhalt:
    wfi
    b       .Lhalt

/*
 * Exception handlers — write diagnostics to shared memory then halt.
 *
 * Each handler writes:
 *   +0x00  FAULT_TYPE: 1=undef, 2=SVC, 3=prefetch abort, 4=data abort
 *   +0x04  FAULT_PC:   faulting instruction / branch target
 *   +0x08  FAULT_DFAR: DFAR or IFAR
 *   +0x0C  FAULT_DFSR: DFSR or IFSR
 *   +0x10  CALLER_LR:  LR from SVC mode (return addr of the caller)
 *   +0x14  CALLER_SP:  SP from SVC mode
 *   +0x18  STACK_0:    word at [SP_svc + 0]
 *   +0x1C  STACK_1:    word at [SP_svc + 4]
 *   +0x20  STACK_2:    word at [SP_svc + 8]
 *   +0x24  STACK_3:    word at [SP_svc + 12]
 *   DONE_FLAG: set to 0xDEAD to signal fault to host
 */

_undef_handler:
    ldr     r0, =FAULT_TYPE_ADDR
    mov     r1, #1
    str     r1, [r0]
    sub     r1, lr, #4
    str     r1, [r0, #4]
    mov     r1, #0
    str     r1, [r0, #8]
    str     r1, [r0, #12]
    b       _save_caller_and_halt

_svc_handler:
    ldr     r0, =FAULT_TYPE_ADDR
    mov     r1, #2
    str     r1, [r0]
    sub     r1, lr, #4
    str     r1, [r0, #4]
    mov     r1, #0
    str     r1, [r0, #8]
    str     r1, [r0, #12]
    b       _save_caller_and_halt

_pabort_handler:
    ldr     r0, =FAULT_TYPE_ADDR
    mov     r1, #3
    str     r1, [r0]
    sub     r1, lr, #4
    str     r1, [r0, #4]
    mrc     p15, 0, r1, c6, c0, 2
    str     r1, [r0, #8]
    mrc     p15, 0, r1, c5, c0, 1
    str     r1, [r0, #12]
    b       _save_caller_and_halt

_dabort_handler:
    ldr     r0, =FAULT_TYPE_ADDR
    mov     r1, #4
    str     r1, [r0]
    sub     r1, lr, #8
    str     r1, [r0, #4]
    mrc     p15, 0, r1, c6, c0, 0
    str     r1, [r0, #8]
    mrc     p15, 0, r1, c5, c0, 0
    str     r1, [r0, #12]
    b       _save_caller_and_halt

/*
 * Common tail — grab SVC-mode LR & SP, plus top of stack,
 * then signal fault and halt.
 * r0 still points to FAULT_TYPE_ADDR from the handler above.
 */
_save_caller_and_halt:
    /* Switch to SVC mode to read its banked LR and SP */
    cps     #0x13
    mov     r2, lr                  /* LR_svc = return addr in calling code */
    mov     r3, sp                  /* SP_svc = stack pointer at fault time */
    cps     #0x17                   /* back to ABT mode (safe for UND too) */

    str     r2, [r0, #16]          /* CALLER_LR */
    str     r3, [r0, #20]          /* CALLER_SP */

    /* Save 4 words from top of SVC stack */
    ldr     r1, [r3, #0]
    str     r1, [r0, #24]          /* STACK_0 */
    ldr     r1, [r3, #4]
    str     r1, [r0, #28]          /* STACK_1 */
    ldr     r1, [r3, #8]
    str     r1, [r0, #32]          /* STACK_2 */
    ldr     r1, [r3, #12]
    str     r1, [r0, #36]          /* STACK_3 */

    /* Signal fault */
    ldr     r0, =DONE_FLAG_ADDR
    ldr     r1, =0xDEAD
    str     r1, [r0]
    dsb
1:  wfi
    b       1b
