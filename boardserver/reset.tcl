connect

# Check if device is a Zynq
if {[targets -filter {name =~ "APU"}] ne ""} {
	# Reset Zynq SoC (also clears FPGA)
	puts "Resetting Zynq and clearing FPGA..."
	targets -set -filter {name =~ "APU"} -index 0
	rst -system
} else {
	# Clear FPGA by attempting to program an invlaid bitstream
	puts "Clearing FPGA..."
	fpga reset.bin
}

disconnect
