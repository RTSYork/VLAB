#!/usr/bin/env python3

"""
Iterate over all boards in the VLAB. For any board which exists but isn't available, check it has
a valid lock. If it does, check that the lock has not expired. In any other case, forcibly
unlock the board. It is intended this is run periodically on the VLAB relay server.

Then ping all boards to ensure that we can make an SSH connection to them. Remove any we cannot.

Options:
-v   Verbose: Print out the names of the boards as they are being checked
-s   Check connections: Attempt to ping each available boardserver to ensure it is still operational

Regardless of provided options, if a board is found "half locked" or that has been locked for too long, it
will be freed.

Currently "too long" is defined as MAX_LOCK_TIME below (in seconds).

Ian Gray, 2016
"""

import argparse
import os
import socket
from vlabredis import *

parser = argparse.ArgumentParser(description="VLAB board test script")
parser.add_argument('-s', action="store_true", default=False, dest='ssh_to_boards')
parser.add_argument('-k', action="store_true", default=True, dest='check_locks')
parser.add_argument('-v', action="store_true", default=False, dest='verbose')
parsed = parser.parse_args()

PING_TIMEOUT = 30
KEYS_DIR = "/vlab/keys/"


def check_ssh_connection(hostname, port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		s.connect((hostname, int(port)))
		rv = True
	except socket.error:
		rv = False
	s.close()
	return rv


def log(s, v):
	if (v and parsed.verbose) or (v is False):
		print("{} checkboards.py: {}".format(time.strftime("%Y-%m-%d-%H:%M:%S"), s))


def reset_board(db, board, server, port):
	try:
		if db.get("vlab:knownboard:{}:reset".format(board)) == "true":
			cmd = "/opt/xsct/bin/xsdb /vlab/reset.tcl"
			target = "root@{}".format(server)
			keyfile = "{}{}".format(KEYS_DIR, "id_rsa")
			ssh_cmd = "ssh -o \"StrictHostKeyChecking no\" -i {} -p {} {} \"{}\"" \
				.format(keyfile, port, target, cmd)
			os.system(ssh_cmd)
	except Exception as e:
		log("Exception {} when resetting board {}".format(e, board), False)


def check_sessions(db):
	for bc in db.smembers("vlab:boardclasses"):
		log("Boardclass: {}".format(bc), True)

		while db.get("vlab:boardclass:{}:locking".format(bc)) is not None:
			log("\tBoardclass currently being locked by a user, waiting for 1 second...", True)
			time.sleep(1)

		for b in db.smembers("vlab:boardclass:{}:boards".format(bc)):
			log("\tBoard: {}".format(b), True)

			bd = get_board_details(db, b, ["server", "port"])
			server = bd["server"]
			port = bd["port"]
			log("\t\tServer: {}:{}".format(server, port), True)

			board_available_since = db.zscore("vlab:boardclass:{}:availableboards".format(bc), b)

			if board_available_since is None:
				# Board is not in available list
				session_username = db.get("vlab:board:{}:session:username".format(b))
				session_start_time = db.get("vlab:board:{}:session:starttime".format(b))
				session_ping_time = db.get("vlab:board:{}:session:pingtime".format(b))

				if session_username is None or session_start_time is None or session_ping_time is None:
					# Board is not marked as available, but also does not have a valid session
					log("Board {} marked as in-use but has no session info. Setting as available.".format(b), False)
					reset_board(db, b, server, port)
					# Restart the board server container to ensure any sessions are killed
					target = "vlab@{}".format(server)
					keyfile = "{}{}".format(KEYS_DIR, "id_rsa")
					cmd = "/opt/VLAB/boardrestart.sh {}".format(b)
					ssh_cmd = "ssh -q -o \"StrictHostKeyChecking no\" -e none -i {} {} \"{}\"".format(keyfile, target, cmd)
					print("Restarting target container...")
					os.system(ssh_cmd)
					unlock_board(db, b, bc)
					end_session(db, b, bc)
				else:
					# Check if session is still active
					log("\t\tIn use by {} since {} (last ping at {})."
					    .format(session_username, session_start_time, session_ping_time), True)
					current_time = int(time.time())
					if current_time - int(session_ping_time) > PING_TIMEOUT:
						log("Board {} ping timed out. Set as available and unlocked.".format(b), False)
						reset_board(db, b, server, port)
						unlock_board(db, b, bc)
						end_session(db, b, bc)

			board_unlocked_since = db.zscore("vlab:boardclass:{}:unlockedboards".format(bc), b)

			if board_unlocked_since is None:
				# Board is not in unlocked list
				lock_username = db.get("vlab:board:{}:lock:username".format(b))
				lock_time = db.get("vlab:board:{}:lock:time".format(b))

				if lock_username is None or lock_time is None:
					# Board is not marked as unlocked, but also does not have a valid lock
					log("Board {} marked as locked but has no lock info. Setting as unlocked.".format(b), False)
					reset_board(db, b, server, port)
					unlock_board(db, b, bc)
				else:
					# Check if lock is still active
					log("\t\tLocked by {} at {} until {}.".format(lock_username, lock_time, int(lock_time) + MAX_LOCK_TIME), True)
					current_time = int(time.time())
					if current_time - int(lock_time) > MAX_LOCK_TIME:
						log("Board {} lock timed out. Forced release.".format(b), False)
						unlock_board(db, b, bc)

			board_available_since = db.zscore("vlab:boardclass:{}:availableboards".format(bc), b)
			board_unlocked_since = db.zscore("vlab:boardclass:{}:unlockedboards".format(bc), b)
			if board_available_since is not None:
				log("\t\tAvailable since {}".format(int(board_available_since)), True)
			elif board_unlocked_since is not None:
				log("\t\tIn use, but unlocked since {}".format(int(board_unlocked_since)), True)


def check_ssh_to_boards(db):
	for bc in db.smembers("vlab:boardclasses"):
		for board in db.smembers("vlab:boardclass:{}:boards".format(bc)):
			details = get_board_details(db, board, ['server', 'port'])
			server = details['server']
			port = details['port']
			if not check_ssh_connection(server, port):
				log("Board {} on {}:{} failed SSH connection. Waiting 3 seconds and checking again..."
				    .format(board, server, port), False)
				time.sleep(3.0)
				details = get_board_details(db, board, ['server', 'port'])
				server = details['server']
				port = details['port']
				if not check_ssh_connection(server, port):
					log("Board {} on {}:{} failed SSH connection. Removing from database."
					    .format(board, server, port), False)
					remove_board(db, board)
				else:
					log("Board {} on {}:{} connection OK.".format(board, server, port), True)
			else:
				log("Board {} on {}:{} connection OK.".format(board, server, port), True)


redis_db = connect_to_redis('localhost')

if parsed.check_locks:
	check_sessions(redis_db)

if parsed.ssh_to_boards:
	log("Checking SSH connections", True)
	check_ssh_to_boards(redis_db)
