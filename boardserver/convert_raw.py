#!/usr/bin/env python3
"""Convert raw framebuffer dump to JPEG.

Usage: python3 convert_raw.py input.raw width height output.jpg

The raw file is expected to be 32bpp (RGBX — 4 bytes per pixel,
high byte unused), as produced by capture_rawjtag.tcl.
"""

import sys
from PIL import Image


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 convert_raw.py input.raw width height output.jpg")
        sys.exit(1)

    input_path = sys.argv[1]
    width = int(sys.argv[2])
    height = int(sys.argv[3])
    output_path = sys.argv[4]

    expected_size = width * height * 4
    with open(input_path, "rb") as f:
        data = f.read()

    if len(data) < expected_size:
        print(f"WARNING: file is {len(data)} bytes, expected {expected_size}")
        # Pad with zeros
        data = data + b"\x00" * (expected_size - len(data))
    elif len(data) > expected_size:
        print(f"NOTE: file is {len(data)} bytes, using first {expected_size}")
        data = data[:expected_size]

    # VDMA framebuffer is BGRX (Blue, Green, Red, unused) on Zynq
    # Confirmed: top-left blue pixel reads as 0x000000FF (byte 0 = Blue)
    img = Image.frombytes("BGRX", (width, height), data)
    img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=85)
    print(f"Saved {output_path} ({width}x{height})")


if __name__ == "__main__":
    main()
