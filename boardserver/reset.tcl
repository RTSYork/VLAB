# Return the board to clean state, either before handing it to a user or after they disconnect.
#
# Exit codes:
#   0  OK
#   1  could not talk to the hardware server
#   2  the board is a Zynq but its PS is not on the JTAG chain (the pernicious error we keep seeing)

set TARGET_RETRIES 5
set RETRY_DELAY 500

proc find_target {filter} {
	global TARGET_RETRIES RETRY_DELAY
	for {set i 0} {$i < $TARGET_RETRIES} {incr i} {
		if {[catch {targets -filter $filter} result]} {
			set result ""
		}
		if {$result ne ""} {
			return $result
		}
		after $RETRY_DELAY
	}
	return ""
}

if {[catch {connect} msg]} {
	puts stderr "ERROR: cannot connect to the hardware server: $msg"
	exit 1
}

# Check if device is a Zynq
if {[find_target {name =~ "APU"}] ne ""} {
	# Reset Zynq SoC (also clears FPGA)
	puts "Resetting Zynq and clearing FPGA..."
	targets -set -filter {name =~ "APU"} -index 0
	if {[catch {rst -system} msg]} {
		puts stderr "ERROR: system reset failed: $msg"
		catch {disconnect}
		exit 2
	}
	catch {disconnect}
	exit 0
}

# No PS found on the chain
if {[find_target {name =~ "xc7z*"}] ne ""} {
	puts stderr "ERROR: this is a Zynq board, but its PS (APU) is not on the JTAG chain."
	puts stderr "The board cannot be programmed in this state and needs attention."
	catch {disconnect}
	exit 2
}

# A normal non-Zynq FPGA. Clear it by attempting to program an invalid bitstream.
# This will fail with "DONE PIN is not HIGH" once the part has been wiped, so the error from 'fpga' is caught and discarded.
puts "Clearing FPGA..."
catch {fpga /vlab/reset.bin}
catch {disconnect}
exit 0
