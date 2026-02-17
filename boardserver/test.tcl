connect

# Check if device is a Zynq (has APU)
if {[targets -filter {name =~ "APU"}] ne ""} {
	# Zynq: program bitstream + download ELF
	puts "Programming test bitstream (Zynq)..."
	targets -set -filter {name =~ "APU"} -index 0
	rst -system
	after 500

	# Program the PL
	targets -set -filter {name =~ "xc7z*"}
	fpga /vlab/test/test.bit

	# Initialise the PS (DDR, clocks, MIO)
	targets -set -filter {name =~ "ARM*#0"}
	rst -processor
	after 500
	source /vlab/test/ps7_init.tcl
	ps7_init
	after 500
	ps7_post_config
	after 500

	# Download and run the test ELF
	dow /vlab/test/test.elf
	con

	puts "Waiting for test application..."
	after 5000
} else {
	# Non-Zynq: bitstream only
	puts "Programming test bitstream..."
	fpga /vlab/test/test.bit

	puts "Waiting for test output..."
	after 5000
}

disconnect
