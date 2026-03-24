/* Minimal stdlib.h shim for bare-metal builds without newlib.
 * Only declarations — no implementations. Functions used only in
 * non-JPEG stb_image_write paths are eliminated by --gc-sections.
 */
#ifndef _COMPAT_STDLIB_H
#define _COMPAT_STDLIB_H

#include <stddef.h>

void *malloc(size_t);
void *realloc(void *, size_t);
void free(void *);
int abs(int);

#endif
