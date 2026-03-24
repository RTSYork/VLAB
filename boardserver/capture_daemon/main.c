/*
 * capture_daemon — Bare-metal Core 1 framebuffer capture & JPEG compression.
 *
 * Runs on Zynq Core 1 (injected via JTAG while Core 0 runs the student app).
 * Reads the framebuffer from DDR (address passed via shared memory),
 * compresses it to JPEG, and writes the result to a known DDR location
 * for the host to read back via JTAG.
 *
 * Memory interface:
 *   0x1FDFFFF0  [in]  Framebuffer physical address (written by xsdb)
 *   0x1FDFFFF4  [in]  Width in pixels (written by xsdb)
 *   0x1FDFFFF8  [out] Done flag (1 = capture complete)
 *   0x1FDFFFFC  [out] JPEG length in bytes
 *   0x1FE00000  [out] JPEG data
 *
 * Resolution: width from params, height fixed at 900 (1440x900 is our target).
 * Pixel format: 32bpp RGBX (4 bytes per pixel, high byte unused).
 *
 * Build: arm-none-eabi-gcc (see Makefile)
 */

#include <stdint.h>
#include <stddef.h>

/*
 * Minimal libc replacements — stb_image_write needs memset and memcpy
 * but we have no libc in bare-metal.
 */
void *memset(void *s, int c, size_t n)
{
	unsigned char *p = (unsigned char *)s;
	while (n--)
		*p++ = (unsigned char)c;
	return s;
}

void *memcpy(void *dest, const void *src, size_t n)
{
	unsigned char *d = (unsigned char *)dest;
	const unsigned char *s2 = (const unsigned char *)src;
	while (n--)
		*d++ = *s2++;
	return dest;
}

/* stb_image_write JPEG encoder — configure before include */
#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STBI_WRITE_NO_STDIO
#define STB_IMAGE_WRITE_STATIC

/* We provide our own stbi_write_func callback, no FILE* needed */
#include "stb_image_write.h"

/* Shared memory addresses (must match capture_fast.tcl)
 * These live ABOVE the stack top (0x1FDFF000) so the stack can't clobber them. */
#define PARAM_FB_ADDR    (*(volatile uint32_t *)0x1FDFF000)
#define PARAM_WIDTH      (*(volatile uint32_t *)0x1FDFF004)
#define DONE_FLAG        (*(volatile uint32_t *)0x1FDFF008)
#define JPEG_LENGTH      (*(volatile uint32_t *)0x1FDFF00C)

#define JPEG_OUTPUT_BASE 0x1FE00000
#define JPEG_OUTPUT_MAX  (1024 * 1024)  /* 1MB max */

/* Fault diagnostics (written by exception handlers in startup.s) */
#define FAULT_TYPE       (*(volatile uint32_t *)0x1FDFF010)
#define FAULT_PC         (*(volatile uint32_t *)0x1FDFF014)
#define FAULT_DFAR       (*(volatile uint32_t *)0x1FDFF018)
#define FAULT_DFSR       (*(volatile uint32_t *)0x1FDFF01C)

/* Default height — 1440x900 is the standard HDMI mode */
#define DEFAULT_HEIGHT   900

/* JPEG quality (1-100) */
#define JPEG_QUALITY     80

/*
 * JPEG write context — tracks position in output buffer.
 */
typedef struct {
	uint8_t *base;
	uint32_t offset;
	uint32_t max_size;
} jpeg_ctx_t;

/*
 * stb_image_write callback — writes JPEG data to DDR output buffer.
 */
static void jpeg_write_func(void *context, void *data, int size)
{
	jpeg_ctx_t *ctx = (jpeg_ctx_t *)context;
	uint8_t *src = (uint8_t *)data;

	for (int i = 0; i < size && ctx->offset < ctx->max_size; i++) {
		ctx->base[ctx->offset++] = src[i];
	}
}

/*
 * Data Synchronization Barrier — ensures all memory writes are visible.
 */
static inline void dsb(void)
{
	__asm__ volatile("dsb" ::: "memory");
}

/*
 * Data Memory Barrier.
 */
static inline void dmb(void)
{
	__asm__ volatile("dmb" ::: "memory");
}

/*
 * Wait For Interrupt — halts the core until debug stop.
 */
static inline void wfi(void)
{
	__asm__ volatile("wfi");
}

/*
 * Invalidate entire L1 D-cache by set/way.
 * We need this to ensure we read fresh framebuffer data from DDR,
 * not stale cache lines.
 */
static void invalidate_dcache(void)
{
	uint32_t ccsidr, sets, ways, set, way;

	/* Select L1 data cache */
	__asm__ volatile("mcr p15, 2, %0, c0, c0, 0" :: "r"(0));
	__asm__ volatile("isb");

	/* Read Cache Size ID Register */
	__asm__ volatile("mrc p15, 1, %0, c0, c0, 0" : "=r"(ccsidr));

	sets = ((ccsidr >> 13) & 0x7FFF) + 1;
	ways = ((ccsidr >> 3) & 0x3FF) + 1;

	for (way = 0; way < ways; way++) {
		for (set = 0; set < sets; set++) {
			uint32_t val = (way << 30) | (set << 5);
			/* DCISW — Invalidate by set/way */
			__asm__ volatile("mcr p15, 0, %0, c7, c6, 1" :: "r"(val));
		}
	}
	dsb();
}

int main(void)
{
	/* Read parameters written by xsdb */
	uint32_t fb_addr = PARAM_FB_ADDR;
	uint32_t width = PARAM_WIDTH;
	uint32_t height = DEFAULT_HEIGHT;

	/* Sanity checks */
	if (width == 0 || width > 4096)
		width = 1440;
	if (fb_addr == 0)
		fb_addr = 0x00100000;

	uint8_t *fb = (uint8_t *)(uintptr_t)fb_addr;

	/* Set up JPEG output context */
	jpeg_ctx_t ctx;
	ctx.base = (uint8_t *)JPEG_OUTPUT_BASE;
	ctx.offset = 0;
	ctx.max_size = JPEG_OUTPUT_MAX;

	/* Encode to JPEG */
	int result = stbi_write_jpg_to_func(
		jpeg_write_func,
		&ctx,
		(int)width,
		(int)height,
		4,            /* 4 components (RGBX) — encoder uses RGB, ignores X */
		fb,
		JPEG_QUALITY
	);

	dsb();

	if (result && ctx.offset > 0) {
		/* Write JPEG length and set done flag */
		JPEG_LENGTH = ctx.offset;
		dsb();
		DONE_FLAG = 1;
	} else {
		/* Encoding failed — signal with length 0 but still set done */
		JPEG_LENGTH = 0;
		dsb();
		DONE_FLAG = 1;
	}

	dsb();

	/* Halt — host will stop us via JTAG anyway */
	wfi();

	return 0;
}
