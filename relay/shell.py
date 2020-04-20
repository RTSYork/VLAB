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
import subprocess
from vlabredis import *

KEYS_DIR = "/vlab/keys/"

# This should match MAX_LOCK_TIME in 'checkboards.py' (a better solution would be good)
MAX_LOCK_TIME = 600

logging.basicConfig(
	filename='/vlab/log/access.log', level=logging.INFO, format='%(asctime)s ; %(levelname)s ; %(name)s ; %(message)s')
log = logging.getLogger(os.path.basename(sys.argv[0]))

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

# Otherwise the arg should be of the form boardclass:port
pos = arg.find(':')
if pos == -1:
	print("Argument should be of the form boardclass:port")
	sys.exit(1)

boardclass = arg[:pos]
tunnel_port = arg[(pos + 1):]
try:
	tunnel_port = int(tunnel_port)
except ValueError:
	print("Argument should be of the form boardclass:port")
	sys.exit(1)

# Do the specified user and boardclass exist in redis?
check_in_set(db, 'vlab:boardclasses', boardclass, "Board class '{}' does not exist.".format(boardclass))
check_in_set(db, 'vlab:users', username, "User '{}' is not a VLAB user.".format(username))

# Can the user access the requested boardclass?
# Either they are an overlord user, or vlab:user:<username>:allowedboards includes the boardclass in question
if not db.get("vlab:user:{}:overlord".format(username)):
	check_in_set(db, "vlab:user:{}:allowedboards".format(username),
	             boardclass,
	             "User '{}' cannot access board class '{}'.".format(username, boardclass)
	             )

# Do we already own it?
# For each board in the board class, check if one is locked by us
board = None
for b in db.smembers("vlab:boardclass:{}:boards".format(boardclass)):
	if db.get("vlab:board:{}:lock:username".format(b)) == username:
		board = b
		break

locktime = int(time.time())

if board is None:
	# Try to grab a lock for the boardclass
	db.set("vlab:boardclass:{}:locking".format(boardclass), 1)
	db.expire("vlab:boardclass:{}:locking".format(boardclass), 2)

	print("Requesting least-recently-unlocked board of class '{}'...".format(boardclass))
	board = allocate_board_of_class(db, boardclass)

	if board is None:
		db.delete("vlab:boardclass:{}:locking".format(boardclass))
		print("All boards of type '{}' are currently locked by other VLAB users.".format(boardclass))
		print("Try again in a few minutes (locks expire after {} minutes).".format(int(MAX_LOCK_TIME / 60)))
		log.critical("NOFREEBOARDS: {}, {}".format(username, boardclass))
		sys.exit(1)

	db.set("vlab:board:{}:lock:username".format(board), username)
	db.set("vlab:board:{}:lock:time".format(board), locktime)
else:
	# Refresh the lock time
	db.set("vlab:board:{}:lock:time".format(board), locktime)

unlocked_count = db.zcard("vlab:boardclass:{}:unlockedboards".format(boardclass))
log.info("LOCK: {}, {}, {} remaining in set".format(username, boardclass, unlocked_count))

# Fetch the details of the locked board
board_details = get_board_details(db, board, ["user", "server", "port"])

lock_start = time.strftime("%H:%M:%S %Z", time.localtime(locktime))
lock_end = time.strftime("%d/%m/%y at %H:%M:%S %Z", time.localtime(locktime + MAX_LOCK_TIME))
lock_end_caps = time.strftime("%d/%m/%y AT %H:%M:%S %Z", time.localtime(locktime + MAX_LOCK_TIME))
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
	cmd = "/opt/xsct/bin/xsdb /vlab/reset.tcl"
	ssh_cmd = "ssh -q -o \"StrictHostKeyChecking no\" -i {} -p {} {} \"{}\""\
		.format(keyfile, port, target, cmd)
	print("Resetting board...")
	subprocess.run(ssh_cmd, shell=True)

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
subprocess.run(ssh_cmd, shell=True)

print("User disconnected. Cleaning up...")
log.info("RELEASE: {}, {}".format(username, boardclass))

if db.get("vlab:knownboard:{}:reset".format(board)) == "true":
	cmd = "/opt/xsct/bin/xsdb /vlab/reset.tcl"
	ssh_cmd = "ssh -q -o \"StrictHostKeyChecking no\" -i {} -p {} {} \"{}\""\
		.format(keyfile, port, target, cmd)
	print("Resetting board...")
	subprocess.run(ssh_cmd, shell=True)

print("Releasing lock...")
unlock_board_if_user_time(db, board, boardclass, username, locktime)
print("Disconnected successfully.")
