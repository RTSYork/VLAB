/* Minimal math.h shim for bare-metal builds without newlib.
 * Only frexp is actually called (HDR path); it gets GC'd since
 * we only use the JPEG encoder.
 */
#ifndef _COMPAT_MATH_H
#define _COMPAT_MATH_H

double frexp(double, int *);

#endif
