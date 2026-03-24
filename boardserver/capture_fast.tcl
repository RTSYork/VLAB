# capture_fast.tcl — Core 1 injection framebuffer capture
#
# Injects capture_daemon.elf onto Core 1 to capture and JPEG-compress
# the framebuffer on-chip. Core 0 is NOT disturbed.
#
# Usage: xsdb capture_fast.tcl <vdma_base_addr> [capture_daemon.elf path]
# e.g.:  xsdb capture_fast.tcl 0x43000000
#        xsdb capture_fast.tcl 0x43000000 /path/to/capture_daemon.elf
#
# Output: output.jpg

# Memory map for Core 1 communication
# Params region at 0x1FDFF000, ABOVE the stack top, so stack can't clobber them
set PARAM_FB_ADDR   0x1FDFF000
set PARAM_WIDTH     0x1FDFF004
set DONE_FLAG       0x1FDFF008
set JPEG_LENGTH     0x1FDFF00C
set JPEG_OUTPUT     0x1FE00000

# Fault diagnostic addresses (written by exception handlers)
set FAULT_TYPE      0x1FDFF010
set FAULT_PC        0x1FDFF014
set FAULT_DFAR      0x1FDFF018
set FAULT_DFSR      0x1FDFF01C
set CALLER_LR       0x1FDFF020
set CALLER_SP       0x1FDFF024
set STACK_0         0x1FDFF028
set STACK_1         0x1FDFF02C
set STACK_2         0x1FDFF030
set STACK_3         0x1FDFF034

# Timeout for capture completion (milliseconds)
set CAPTURE_TIMEOUT 10000
set POLL_INTERVAL   100

if {$argc > 2} {
	puts "Usage: xsdb capture_fast.tcl \[vdma_base_addr\] \[capture_daemon.elf\]"
	puts "  e.g. xsdb capture_fast.tcl 0x43000000"
	exit 1
}

set vdma_base "0x43000000"
if {$argc >= 1} {
	set vdma_base [lindex $argv 0]
	# Ensure hex prefix — accept both "0x43000000" and "43000000"
	if {![string match "0x*" $vdma_base] && ![string match "0X*" $vdma_base]} {
		set vdma_base "0x$vdma_base"
	}
}

if {$argc == 2} {
	set elf_path [lindex $argv 1]
} else {
	# Default: same directory as this script
	set script_dir [file dirname [info script]]
	set elf_path [file join $script_dir capture_daemon capture_daemon.elf]
}

if {![file exists $elf_path]} {
	puts "ERROR: ELF not found: $elf_path"
	puts "Build it first: cd capture_daemon && make"
	exit 1
}

puts "VDMA base: $vdma_base"
puts "Capture daemon ELF: $elf_path"

connect

# Allow access to PL AXI peripherals (VDMA registers)
configparams force-mem-accesses 1

set start_time [clock milliseconds]

# Read VDMA registers to find framebuffer (using Core 0's debug port for memory access)
targets -set -filter {name =~ "ARM*#0"}

# Read frame 0 start address (VDMA_BASE + 0x5C)
set fb_addr_reg [expr {$vdma_base + 0x5C}]
set fb_addr [mrd -value $fb_addr_reg]
puts "Framebuffer at: [format 0x%08X $fb_addr]"

# Also read the width from VDMA HSIZE register (0x54 = MM2S_HSIZE)
set hsize_reg [expr {$vdma_base + 0x54}]
set hsize_val [mrd -value $hsize_reg]
# HSIZE is in bytes, divide by 4 for pixel width (32bpp)
set width [expr {$hsize_val / 4}]
puts "Detected width from VDMA HSIZE: $width pixels (HSIZE=$hsize_val bytes)"

# Read stride (FRMDLY_STRIDE register 0x58, stride in bits [15:0])
set stride_reg [expr {$vdma_base + 0x58}]
set stride_raw [mrd -value $stride_reg]
set stride [expr {$stride_raw & 0xFFFF}]
puts "Detected stride: $stride bytes ([expr {$stride / 4}] pixels, raw reg=[format 0x%08X $stride_raw])"

if {$stride != $hsize_val} {
	puts "NOTE: stride ($stride) != HSIZE ($hsize_val) — padding present"
}

# Write parameters to shared memory area
# (Using Core 0's debug port — this is just a memory write, doesn't affect Core 0)
mwr $PARAM_FB_ADDR $fb_addr
mwr $PARAM_WIDTH $width

# Clear done flag and fault diagnostic area
mwr $DONE_FLAG 0
mwr $FAULT_TYPE 0
mwr $FAULT_PC 0
mwr $FAULT_DFAR 0
mwr $FAULT_DFSR 0
mwr $CALLER_LR 0
mwr $CALLER_SP 0

# Target Core 1
targets -set -filter {name =~ "ARM*#1"}
puts "Selected Core 1"

# Reset Core 1's processor state (does NOT affect PS peripherals or DDR)
# This is needed for dow to work — without it the core is in an
# undefined state from the boot ROM WFE loop.
rst -processor
after 200

# Download and start the capture daemon
puts "Downloading capture daemon to Core 1..."
dow $elf_path
after 100
con
puts "Core 1 running capture daemon"

# Poll for completion
puts -nonewline "Waiting for capture to complete"
set elapsed 0
set done 0
while {$elapsed < $CAPTURE_TIMEOUT} {
	after $POLL_INTERVAL
	set elapsed [expr {$elapsed + $POLL_INTERVAL}]

	# Read done flag (single word read is fast via JTAG)
	# 1 = success, 0xDEAD = exception occurred
	set done [mrd -value $DONE_FLAG]
	if {$done == 1} {
		puts ""
		puts "Capture complete!"
		break
	}
	if {$done == 0xDEAD} {
		puts ""
		puts "Exception detected on Core 1!"
		stop
		break
	}
	puts -nonewline "."
	flush stdout
}

# Stop Core 1
stop

# Handle timeout
if {$elapsed >= $CAPTURE_TIMEOUT} {
	puts ""
	puts "ERROR: Capture timed out after ${CAPTURE_TIMEOUT}ms"
	puts ""
	puts "=== Core 1 state at timeout ==="
	set regs [rrd]
	puts "$regs"
	puts ""
	puts "Done flag value: [format 0x%08X [mrd -value $DONE_FLAG]]"
	puts "JPEG length:     [format 0x%08X [mrd -value $JPEG_LENGTH]]"
}

# Check for exception — only if capture did NOT succeed normally
if {$done != 1} {
	set fault_names [dict create 0 "none" 1 "Undefined Instruction" 2 "SVC" 3 "Prefetch Abort" 4 "Data Abort"]
	set fault_type [mrd -value $FAULT_TYPE]
	if {$fault_type != 0 && [dict exists $fault_names $fault_type]} {
		set fault_pc [mrd -value $FAULT_PC]
		set fault_dfar [mrd -value $FAULT_DFAR]
		set fault_dfsr [mrd -value $FAULT_DFSR]
		set fault_name [dict get $fault_names $fault_type]
		set caller_lr [mrd -value $CALLER_LR]
		set caller_sp [mrd -value $CALLER_SP]
		set stk0 [mrd -value $STACK_0]
		set stk1 [mrd -value $STACK_1]
		set stk2 [mrd -value $STACK_2]
		set stk3 [mrd -value $STACK_3]
		puts ""
		puts "*** EXCEPTION: $fault_name (type $fault_type) ***"
		puts "  Branch target: [format 0x%08X $fault_pc]  (where it tried to go)"
		puts "  Fault Address: [format 0x%08X $fault_dfar]  (xFAR)"
		puts "  Fault Status:  [format 0x%08X $fault_dfsr]  (xFSR)"
		puts ""
		puts "  Caller LR:     [format 0x%08X $caller_lr]  (return addr in calling code)"
		puts "  Caller SP:     [format 0x%08X $caller_sp]"
		puts "  Stack\[SP+0\]:   [format 0x%08X $stk0]"
		puts "  Stack\[SP+4\]:   [format 0x%08X $stk1]"
		puts "  Stack\[SP+8\]:   [format 0x%08X $stk2]"
		puts "  Stack\[SP+12\]:  [format 0x%08X $stk3]"
		if {$fault_type == 4} {
			set fs_3_0 [expr {$fault_dfsr & 0xF}]
			set fs_4 [expr {($fault_dfsr >> 10) & 1}]
			set fs [expr {($fs_4 << 4) | $fs_3_0}]
			set wnr [expr {($fault_dfsr >> 11) & 1}]
			puts "  DFSR decode: FS=0x[format %02X $fs] ([expr {$wnr ? "Write" : "Read"}])"
		}
		if {$fault_type == 3} {
			set fs_3_0 [expr {$fault_dfsr & 0xF}]
			set fs_4 [expr {($fault_dfsr >> 10) & 1}]
			set fs [expr {($fs_4 << 4) | $fs_3_0}]
			puts "  IFSR decode: FS=0x[format %02X $fs]"
			set fs_names [dict create 0x01 "Alignment" 0x05 "Translation (Section)" \
				0x07 "Translation (Page)" 0x08 "Synchronous External Abort" \
				0x0D "Permission (Section)" 0x0F "Permission (Page)"]
			if {[dict exists $fs_names $fs]} {
				puts "  Fault meaning: [dict get $fs_names $fs]"
			}
		}
		puts ""
		puts "  Look up Caller LR in: arm-none-eabi-objdump -d capture_daemon.elf"
	} else {
		puts "No exception detected — Core 1 may be stuck or looping"
	}
	disconnect
	exit 1
}

# === Success path — read JPEG data ===

set jpeg_len [mrd -value $JPEG_LENGTH]
puts "JPEG size: $jpeg_len bytes"

if {$jpeg_len == 0 || $jpeg_len > 1048576} {
	puts "ERROR: Invalid JPEG length: $jpeg_len"
	disconnect
	exit 1
}

# Read JPEG data — mrd works in 32-bit words, round up
set num_words [expr {($jpeg_len + 3) / 4}]
puts "Reading $num_words words from [format 0x%08X $JPEG_OUTPUT]..."
mrd -bin -file output.jpg $JPEG_OUTPUT $num_words

set end_time [clock milliseconds]
set total_elapsed [expr {($end_time - $start_time) / 1000.0}]

puts "Done in ${total_elapsed}s"
puts "Output: output.jpg"

disconnect
