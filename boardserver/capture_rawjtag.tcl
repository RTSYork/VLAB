# capture_rawjtag.tcl — Baseline JTAG framebuffer capture
#
# Reads the framebuffer directly via JTAG memory reads.
# This halts Core 0 briefly during the read.
#
# Usage: xsdb capture_rawjtag.tcl <vdma_base_addr> <width> <height>
# e.g.:  xsdb capture_rawjtag.tcl 0x43000000 1440 900
#
# Output: framebuffer.raw (can be converted with convert_raw.py)

if {$argc != 3} {
	puts "Usage: xsdb capture_rawjtag.tcl <vdma_base_addr> <width> <height>"
	puts "  e.g. xsdb capture_rawjtag.tcl 0x43000000 1440 900"
	exit 1
}

set vdma_base [lindex $argv 0]
set width [lindex $argv 1]
set height [lindex $argv 2]

# 32bpp (4 bytes per pixel)
set framebuffer_size [expr {$width * $height * 4}]
# mrd works in 32-bit words
set num_words [expr {$framebuffer_size / 4}]

puts "VDMA base: $vdma_base"
puts "Resolution: ${width}x${height}, 32bpp"
puts "Framebuffer size: $framebuffer_size bytes ($num_words words)"

connect

# Allow access to PL AXI peripherals (VDMA registers)
configparams force-mem-accesses 1

# Target Core 0
targets -set -filter {name =~ "ARM*#0"}

# Read frame 0 start address (VDMA_BASE + 0x5C)
# Most student designs use a single framebuffer (frame 0 only).
set fb_addr_reg [expr {$vdma_base + 0x5C}]
set fb_addr [mrd -value $fb_addr_reg]
puts "Framebuffer at: [format 0x%08X $fb_addr]"

# Halt Core 0 for the memory read
puts "Halting Core 0..."
set start_time [clock milliseconds]
stop

# Read framebuffer to binary file
puts "Reading $num_words words from [format 0x%08X $fb_addr]..."
mrd -bin -file framebuffer.raw $fb_addr $num_words

# Resume Core 0 immediately
con
set end_time [clock milliseconds]
set elapsed [expr {($end_time - $start_time) / 1000.0}]

puts "Core 0 resumed."
puts "Capture complete in ${elapsed}s"
puts "Output: framebuffer.raw"
puts "Convert with: python3 convert_raw.py framebuffer.raw $width $height output.jpg"

disconnect
