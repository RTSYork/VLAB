/*
 * Linker script for capture daemon.
 *
 * Memory map (top 3MB of 512MB DDR):
 *   0x00000000 - 0x1FCFFFFF  Student code & framebuffers (untouched)
 *   0x1FD00000 - 0x1FDFEFFF  Stack (~1020KB, grows down from 0x1FDFF000)
 *   0x1FDFF000 - 0x1FDFFFFF  Shared params, flags & fault diagnostics (4KB)
 *   0x1FE00000 - 0x1FEFFFFF  JPEG output buffer (~1MB)
 *   0x1FF00000 - 0x1FFFFFFF  Capture daemon code + data (~1MB)
 */

MEMORY
{
    STACK (rw)  : ORIGIN = 0x1FD00000, LENGTH = 0xFF000
    PARAMS (rw) : ORIGIN = 0x1FDFF000, LENGTH = 4K
    JPEGBUF (rw) : ORIGIN = 0x1FE00000, LENGTH = 1M
    CODE (rwx) : ORIGIN = 0x1FF00000, LENGTH = 1M
}

_stack_top = ORIGIN(PARAMS);

ENTRY(_start)

SECTIONS
{
    .text : {
        *(.text.vectors)
        *(.text.startup)
        *(.text*)
    } > CODE

    .rodata : {
        *(.rodata*)
    } > CODE

    .data : {
        *(.data*)
    } > CODE

    .bss (NOLOAD) : {
        __bss_start = .;
        *(.bss*)
        *(COMMON)
        __bss_end = .;
    } > CODE

    /* Discard sections we don't need */
    /DISCARD/ : {
        *(.note*)
        *(.comment)
        *(.ARM.attributes)
        *(.ARM.exidx*)
        *(.eh_frame*)
    }
}
