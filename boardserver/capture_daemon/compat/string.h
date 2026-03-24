/* Minimal string.h shim for bare-metal builds without newlib. */
#ifndef _COMPAT_STRING_H
#define _COMPAT_STRING_H

#include <stddef.h>

void *memset(void *, int, size_t);
void *memcpy(void *, const void *, size_t);
void *memmove(void *, const void *, size_t);
int memcmp(const void *, const void *, size_t);
size_t strlen(const char *);

#endif
