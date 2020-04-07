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
import time
from vlabredis import *

parser = argparse.ArgumentParser(description="VLAB board test script")
parser.add_argument('-s', action="store_true", default=False, dest='ssh_to_boards')
parser.add_argument('-k', action="store_true", default=True, dest='check_locks')
parser.add_argument('-v', action="store_true", default=False, dest='verbose')
parsed = parser.parse_args()

MAX_LOCK_TIME = 600


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


def check_locks(db):
	for bc in db.smembers("vlab:boardclasses"):
		log("Boardclass: {}".format(bc), True)
		if db.get("vlab:boardclass:{}:locking".format(bc)) is None:
			for b in db.smembers("vlab:boardclass:{}:boards".format(bc)):
				log("\tBoard: {}".format(b), True)

				bd = get_board_details(db, b, ["server", "port"])
				log("\t\tServer: {}:{}".format(bd['server'], bd['port']), True)

				board_unlocked_since = db.zscore("vlab:boardclass:{}:unlockedboards".format(bc), b)
				if board_unlocked_since is None:
					locker = db.get("vlab:board:{}:lock:username".format(b))
					lock_time = db.get("vlab:board:{}:lock:time".format(b))

					if locker is None or lock_time is None:
						log("Board {} available but no lock info. Setting available.".format(b), False)

						try:
							if db.get("vlab:knownboard:{}:reset".format(b)) == "true":
								cmd = "/opt/xsct/bin/xsdb /vlab/reset.tcl"
								target = "root@{}".format(bd['server'])
								keyfile = "/vlab/keys/id_rsa"
								ssh_cmd = "ssh -o \"StrictHostKeyChecking no\" -i {} -p {} {} \"{}\""\
									.format(keyfile, bd['port'], target, cmd)
								os.system(ssh_cmd)
						except Exception as e:
							log("Exception {} when resetting board {}".format(e, b), False)

						unlock_board(db, b, bc)
					else:
						# check time
						log("\t\tLocked by {} at {} until {}.".format(locker, lock_time, int(lock_time) + MAX_LOCK_TIME), True)
						current_time = int(time.time())
						if current_time - int(lock_time) > MAX_LOCK_TIME:
							log("Board {} lock timed out. Forced release.".format(b), False)
							unlock_board(db, b, bc)
				else:
					log("\t\tAvailable since {}".format(int(board_unlocked_since)), True)
		else:
			log("\tCurrently being locked by a user.", True)


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
					db.srem("vlab:boardclass:{}:boards".format(bc), board)
					db.zrem("vlab:boardclass:{}:unlockedboards".format(bc), board)
				else:
					log("Board {} on {}:{} connection OK.".format(board, server, port), True)
			else:
				log("Board {} on {}:{} connection OK.".format(board, server, port), True)


redis_db = connect_to_redis('localhost')

if parsed.check_locks:
	check_locks(redis_db)

if parsed.ssh_to_boards:
	log("Checking SSH connections", True)
	check_ssh_to_boards(redis_db)
