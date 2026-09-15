#!/usr/bin/env python3

"""
The VLAB relay shell. Called from bash when a remote user connects, this script
is given one argument, which is the board class that the user is requesting.

The script checks whether this user is allowed that board, and if so, locks the
board and assembles the required ssh command to be executed by the calling shell
script which will forward the user's ssh connection on the target board server.

Ian Gray, 2016
"""

import getpass
import logging
import os
import re
import subprocess
from vlabredis import *

KEYS_DIR = "/vlab/keys/"

# How many times to try resetting a board before giving up and withdrawing it
RESET_ATTEMPTS = 2
# reset.tcl returns this when the board is present but cannot be programmed
RESET_RC_UNUSABLE = 2
# Longest serial capture a client may ask for, in seconds
MAX_SERIAL_CAPTURE = 300

logging.basicConfig(
	filename='/vlab/log/access.log', level=logging.INFO, format='%(asctime)s ; %(levelname)s ; %(name)s ; %(message)s')
log = logging.getLogger(os.path.basename(sys.argv[0]))


def find_session_board(db, username):
	"""
	Return (board, boardclass) for the user's current board session, or (None, None)
	if they do not have one. Used by the commands that act on a session the user
	already holds, rather than allocating a board of their own.
	"""
	for bc in db.smembers("vlab:boardclasses"):
		for b in db.smembers("vlab:boardclass:{}:boards".format(bc)):
			if db.get("vlab:board:{}:session:username".format(b)) == username:
				return b, bc
	return None, None


def reset_board(board, keyfile, port, target, attempts=RESET_ATTEMPTS):
	"""
	Run boardserver/reset.tcl to try to clear and reset the board, retrying up to
	'attempts' times. Returns the return code of the last attempt, which is 0 on success.
	"""
	cmd = "/opt/xsct/bin/xsdb /vlab/reset.tcl"
	ssh_cmd = "ssh -q -o \"StrictHostKeyChecking no\" -i {} -p {} {} \"{}\"".format(keyfile, port, target, cmd)
	rc = -1
	for attempt in range(1, attempts + 1):
		rc = subprocess.run(ssh_cmd, shell=True).returncode
		if rc == 0:
			return 0
		log.warning("RESETFAIL: {}, rc={}, attempt {} of {}".format(board, rc, attempt, attempts))
		if attempt < attempts:
			print("Reset of board '{}' failed. Retrying...".format(board))
	return rc

db = connect_to_redis('localhost')

if len(sys.argv) < 3:
	print("Usage: {} {{requested board class}}".format(sys.argv[0]))
	sys.exit(1)

username = getpass.getuser()
arg = sys.argv[2]

# Is the user requesting a free ephemeral port?
if arg == 'getport':
	port = db.incr("vlab:port")
	if port > 35000:
		port = 30000
		db.set("vlab:port", 30000)
	print("VLABPORT:{}".format(port))
	sys.exit(0)

# Is the user requesting a framebuffer capture?
# The command is 'capture' or 'capture:<vdma_base>', where <vdma_base> overrides the
# default VDMA base address used by capture_fast.tcl.
if arg == 'capture' or arg.startswith('capture:'):
	# Parse and strictly validate the optional VDMA base address. This value comes from
	# the (untrusted) client and is interpolated into a shell command below, so anything
	# that is not a plain hex address must be rejected to avoid command injection.
	vdma_base = None
	if arg.startswith('capture:'):
		vdma_base = arg[len('capture:'):]
		if not re.fullmatch(r'0x[0-9A-Fa-f]{1,8}', vdma_base):
			print("Invalid VDMA base address. Expected a hex value such as 0x43000000.")
			sys.exit(1)

	board, boardclass = find_session_board(db, username)
	if board is None:
		print("You don't have an active board session. Connect with vlab.py first.")
		sys.exit(1)

	board_details = get_board_details(db, board, ["server", "port"])
	server = board_details['server']
	port = board_details['port']

	keyfile = "{}{}".format(KEYS_DIR, "id_rsa")
	target = "root@{}".format(server)

	log.info("CAPTURE: {}, {}:{}".format(username, boardclass, board))
	sys.stderr.write("Capturing framebuffer from board '{}'...\n".format(board))
	sys.stderr.flush()

	# Run capture on boardserver: xsdb output goes to stderr (visible to user), JPEG to stdout.
	# vdma_base has already been validated against a strict hex pattern above.
	vdma_arg = " {}".format(vdma_base) if vdma_base else ""
	cmd = "cd /tmp && /opt/xsct/bin/xsdb /vlab/capture_fast.tcl{} 1>&2 && cat output.jpg && rm -f output.jpg".format(vdma_arg)
	ssh_cmd = "ssh -q -o \"StrictHostKeyChecking no\" -i {} -p {} {} \"{}\"".format(
		keyfile, port, target, cmd)
	result = subprocess.run(ssh_cmd, shell=True)
	sys.exit(result.returncode)

# Is the user requesting a capture of the board's serial output?
if arg.startswith('serial:'):
	duration = arg[len('serial:'):]
	if not re.fullmatch(r'[0-9]{1,3}', duration) or not 1 <= int(duration) <= MAX_SERIAL_CAPTURE:
		# stdout carries the captured bytes for this command, so everything meant
		# for a human goes to stderr or the caller cannot tell it from serial data.
		sys.stderr.write("Invalid duration. Expected a whole number of seconds from 1 to {}.\n".format(
			MAX_SERIAL_CAPTURE))
		sys.exit(1)

	board, boardclass = find_session_board(db, username)
	if board is None:
		sys.stderr.write("You don't have an active board session. "
		                 "Connect with vlab.py --no-terminal first.\n")
		sys.exit(1)

	board_details = get_board_details(db, board, ["server", "port"])
	server = board_details['server']
	port = board_details['port']

	keyfile = "{}{}".format(KEYS_DIR, "id_rsa")
	target = "root@{}".format(server)

	log.info("SERIAL: {}, {}:{}, {}s".format(username, boardclass, board, duration))
	sys.stderr.write("Capturing {}s of serial output from board '{}'...\n".format(duration, board))
	sys.stderr.flush()

	# Serial bytes go to stdout
	# 'killall -s 0' just reports whether a matching process exists
	cmd = ("if killall -q -s 0 screen SCREEN 2>/dev/null; then "
	       "echo 'A terminal session is holding /dev/ttyFPGA. "
	       "Reconnect with --no-terminal to capture serial output.' >&2; exit 3; fi; "
	       "stty -F /dev/ttyFPGA 115200 raw -echo; "
	       "timeout {} cat /dev/ttyFPGA").format(duration)
	ssh_cmd = "ssh -q -o \"StrictHostKeyChecking no\" -i {} -p {} {} \"{}\"".format(
		keyfile, port, target, cmd)
	result = subprocess.run(ssh_cmd, shell=True)
	# timeout(1) exits 124 when it stops cat at the end of the window
	sys.exit(0 if result.returncode == 124 else result.returncode)

# Otherwise this is a board session request.
#
# A 'noterm:' prefix asks for a session with no interactive terminal
no_terminal = False
if arg.startswith('noterm:'):
	no_terminal = True
	arg = arg[len('noterm:'):]

# The rest should be of the form boardclass:port, or boardclass:port:serial to request a specific board
args = arg.split(":")
if len(args) < 2:
	print("Argument should be of the form boardclass:port")
	sys.exit(1)

boardclass = args[0]
tunnel_port = args[1]

requested_serial = None
if len(args) == 3:
	requested_serial = args[2]

try:
	tunnel_port = int(tunnel_port)
except ValueError:
	print("Argument should be of the form boardclass:port")
	sys.exit(1)

# Do the specified user and boardclass exist in redis?
check_in_set(db, 'vlab:boardclasses', boardclass, "Board class '{}' does not exist.".format(boardclass))
check_in_set(db, 'vlab:users', username, "User '{}' is not a VLAB user.".format(username))

if requested_serial is not None:
	if not db.get("vlab:user:{}:overlord".format(username)):
		print("Only overlord users can request specific boards.")
		sys.exit(1)

	# Does the requested board exist?
	check_in_set(db, 'vlab:boardclass:{}:boards'.format(boardclass), requested_serial,
	             "Board {} does not exist.".format(requested_serial))

# Can the user access the requested boardclass?
# Either they are an overlord user, or vlab:user:<username>:allowedboards includes the boardclass in question
if not db.get("vlab:user:{}:overlord".format(username)):
	check_in_set(db, "vlab:user:{}:allowedboards".format(username),
	             boardclass,
	             "User '{}' cannot access board class '{}'.".format(username, boardclass)
	             )

# Mark in the database that we are attempting to lock a board of this boardclass
db.set("vlab:boardclass:{}:locking".format(boardclass), 1)
db.expire("vlab:boardclass:{}:locking".format(boardclass), 2)

board = None

# If a specific board serial is requested, try to take that board (only Overload can request specific boards)
if requested_serial is not None:
	if db.get("vlab:board:{}:session:username".format(requested_serial)) == username \
			or db.get("vlab:board:{}:lock:username".format(requested_serial)) == username:
		# We already have an active session or lock for the board
		board = requested_serial
	elif db.zrem("vlab:boardclass:{}:unlockedboards".format(boardclass), requested_serial) > 0:
		# The board was removed from the unlocked list, therefore it was unlocked
		board = requested_serial
	else:
		# The board is currently locked by someone else
		lock_username = db.get("vlab:board:{}:lock:username".format(requested_serial))
		print("Requested board is currently locked by {}.".format(lock_username))
		db.delete("vlab:boardclass:{}:locking".format(boardclass))
		sys.exit(1)

# For each board in the board class, check if one is already in use or locked by us
if board is None:
	for b in db.smembers("vlab:boardclass:{}:boards".format(boardclass)):
		if db.get("vlab:board:{}:session:username".format(b)) == username \
				or db.get("vlab:board:{}:lock:username".format(b)) == username:
			board = b
			print("User already has an active session on board '{}', so reusing...".format(board))
			break

if board is None:
	# Try to get an available board for the boardclass
	print("Requesting least-recently-used board of class '{}'...".format(boardclass))
	board = allocate_available_board_of_class(db, boardclass)

if board is None:
	# Try to get an unlocked but in-use board for the boardclass
	print("No available boards of class '{}'. Checking for in-use boards with expired locks...".format(boardclass))
	print("Requesting least-recently-unlocked board of class '{}'...".format(boardclass))
	board = allocate_unlocked_board_of_class(db, boardclass)

if board is None:
	# If we still don't have a board at this point, all potential boards must be locked
	db.delete("vlab:boardclass:{}:locking".format(boardclass))
	print("All boards of type '{}' are currently locked by other VLAB users.".format(boardclass))
	print("Try again in a few minutes (locks expire after {} minutes).".format(int(MAX_LOCK_TIME / 60)))
	log.critical("NOFREEBOARDS: {}, {}".format(username, boardclass))
	sys.exit(1)

session_start_time = int(time.time())
start_session(db, board, boardclass, username, session_start_time)
log.info("START: {}, {}:{}".format(username, boardclass, board))
unlocked_count = db.zcard("vlab:boardclass:{}:unlockedboards".format(boardclass))
log.info("LOCK: {}, {}:{}, {} remaining in set".format(username, boardclass, board, unlocked_count))

# Fetch the details of the locked board
board_details = get_board_details(db, board, ["user", "server", "port"])

lock_start = time.strftime("%H:%M:%S %Z", time.localtime(session_start_time))
lock_end = time.strftime("%d/%m/%y at %H:%M:%S %Z", time.localtime(session_start_time + MAX_LOCK_TIME))
lock_end_caps = time.strftime("%d/%m/%y AT %H:%M:%S %Z", time.localtime(session_start_time + MAX_LOCK_TIME))
print("Locked board '{}' of type '{}' for user '{}' at {} for {} seconds"
      .format(board, boardclass, username, lock_start, MAX_LOCK_TIME))
print("*******************************************************************************************")
print("*              YOUR EXCLUSIVE BOARD LOCK EXPIRES ON {}              *".format(lock_end_caps))
print("* AFTER THIS TIME SOMEONE ELSE MIGHT BE ALLOCATED YOUR BOARD AND YOU WILL BE DISCONNECTED *")
print("*******************************************************************************************")

# All done. First restart the target container
target = "vlab@{}".format(board_details['server'])
keyfile = "{}{}".format(KEYS_DIR, "id_rsa")
cmd = "/opt/VLAB/boardrestart.sh {}".format(board)
ssh_cmd = "ssh -q -o \"StrictHostKeyChecking no\" -e none -i {} {} \"{}\"".format(keyfile, target, cmd)
print("Restarting target container...")
subprocess.run(ssh_cmd, shell=True)

# Execute the bounce command
print("Connecting to board server...")
time.sleep(2)

# Port details might have changed
board_details = get_board_details(db, board, ["user", "server", "port"])
server = board_details['server']
port = board_details['port']
tunnel = "-L {}:localhost:3121".format(tunnel_port)
keyfile = "{}{}".format(KEYS_DIR, "id_rsa")
target = "root@{}".format(server)

if db.get("vlab:knownboard:{}:reset".format(board)) == "true":
	print("Resetting board...")
	rc = reset_board(board, keyfile, port, target)

	if rc != 0:
		# The board cannot be put into a usable state, so there is no point handing it
		# to the user. Mark it failed so that checkboards.py will not quietly return it to the pool. It
		# comes back into service only if it passes a later run of testboards.py.
		log.critical("RESETFAIL: {}, {}:{}, rc={}, withdrawing board".format(username, boardclass, board, rc))
		unlock_board_if_user_time(db, board, boardclass, username, session_start_time)
		end_session_if_user_time(db, board, boardclass, username, session_start_time)
		withdraw_board(db, board, boardclass)
		record_hwtest_result(db, board, "fail", "reset.tcl failed with code {} when {} connected".format(rc, username))
		print("")
		print("ERROR: board '{}' could not be reset and is not usable.".format(board))
		if rc == RESET_RC_UNUSABLE:
			print("Its programmable logic is visible over JTAG but its processing system is not,")
			print("so it cannot be programmed from Vivado or Vitis.")
		print("The board has been taken out of service and the failure logged.")
		print("Please reconnect to be allocated a different board.")
		sys.exit(1)

if no_terminal:
	# Hold the session open without touching /dev/ttyFPGA
	cmd = "echo VLAB_SESSION_READY; while true; do sleep 5; done"
else:
	screenrc = "defhstatus \\\"{} (VLAB Shell)\\\"\\ncaption always\\ncaption string \\\" VLAB Shell [ User: {} | Lock " \
	           "expires: {} | Board class: {} | Board serial: {} | Server: {} ]\\\""\
		.format(boardclass, username, lock_end, boardclass, board, server)
	cmd = "echo -e '{}' > /vlab/vlabscreenrc;" \
	      "screen -c /vlab/vlabscreenrc -qdRR - /dev/ttyFPGA 115200;" \
	      "killall -q screen;" \
	      "pkill -SIGINT -nx sshd"\
		.format(screenrc)
ssh_cmd = "ssh -q -4 {} -o \"StrictHostKeyChecking no\" -e none -i {} -p {} -tt {} \"{}\""\
	.format(tunnel, keyfile, port, target, cmd)
proc = subprocess.Popen(ssh_cmd, shell=True)

# Wait for the process to end, while pinging session and checking locks every 10 seconds
locked = True
while True:
	try:
		current_time = int(time.time())
		if locked and current_time - int(session_start_time) > MAX_LOCK_TIME:
			if unlock_board_if_user_time(db, board, boardclass, username, session_start_time):
				locked = False
				log.info("RELEASE: {}, {}:{}".format(username, boardclass, board))
		if ping_session_if_user_time(db, board, username, session_start_time):
			log.debug("PING: {}, {}:{} at {}".format(username, boardclass, board, current_time))
		else:
			proc.terminate()
			print("Your lock has expired and board '{}' has been allocated to another user.\r".format(board))
			break
		proc.wait(10)
		break
	except subprocess.TimeoutExpired:
		continue

# Fix terminal in case screen has left it in a bad state
subprocess.run("stty sane", shell=True)

print("User disconnected. Cleaning up...")

reset_failed = False
if db.get("vlab:knownboard:{}:reset".format(board)) == "true":
	print("Resetting board...")
	if reset_board(board, keyfile, port, target) != 0:
		# Board has become unusable during the session so treat it as above
		reset_failed = True
		log.critical("RESETFAIL: {}, {}:{}, on disconnect".format(username, boardclass, board))
		print("This board could not be reset and has been taken out of service.")

print("Releasing lock and ending session...")
if unlock_board_if_user_time(db, board, boardclass, username, session_start_time):
	log.info("RELEASE: {}, {}:{}".format(username, boardclass, board))
if end_session_if_user_time(db, board, boardclass, username, session_start_time):
	log.info("END: {}, {}:{}".format(username, boardclass, board))

if reset_failed:
	withdraw_board(db, board, boardclass)
	record_hwtest_result(db, board, "fail",
	                     "reset.tcl failed when {} disconnected".format(username))

print("Disconnected successfully.")
