#!/usr/bin/env python3

'''
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
'''

import os, sys, getpass, time, socket, argparse
import redis
from vlabredis import *

parser = argparse.ArgumentParser(description="VLAB board test script")
parser.add_argument('-s', action="store_true", default=False, dest='ssh_to_boards')
parser.add_argument('-k', action="store_true", default=True, dest='check_locks')
parser.add_argument('-v', action="store_true", default=False, dest='verbose')
parsed = parser.parse_args()

MAX_LOCK_TIME = 600

db = connecttoredis('localhost')

def checkSSHConnection(hostname, port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		s.connect((hostname, int(port)))
		rv = True
	except socket.error as e:
		rv = False
	s.close()
	return rv

def log(s, v):
	if (v and parsed.verbose) or (v == False):
		print("{} checkboards.py: {}".format(time.strftime("%Y-%m-%d-%H:%M:%S"), s))

def checkLocks(db):
	for bc in db.smembers("vlab:boardclasses"):
		log("Boardclass: {}".format(bc), True)
		if db.get("vlab:boardclass:{}:locking".format(bc)) == None:
			for b in db.smembers("vlab:boardclass:{}:boards".format(bc)):
				log("\tBoard: {}".format(b), True)

				bd = getBoardDetails(db, b, ["server", "port"])
				log("\t\tServer: {}:{}".format(bd['server'], bd['port']), True)

				if not db.sismember("vlab:boardclass:{}:unlockedboards".format(bc), b):
					locker = db.get("vlab:board:{}:lock:username".format(b))
					locktime = db.get("vlab:board:{}:lock:time".format(b))

					if locker == None or locktime == None:
						log("Board {} available but no lock info. Setting available.".format(b), False)

						try:
							if db.get("vlab:knownboard:{}:reset".format(b)) == "true":
								cmd = "/opt/xsct/bin/xsdb /vlab/reset.tcl"
								target = "root@{}".format(bd['server'])
								keyfile = "/vlab/keys/id_rsa"
								sshcmd = "ssh -o \"StrictHostKeyChecking no\" -i {} -p {} {} \"{}\"".format(keyfile, bd['port'], target, cmd)
								os.system(sshcmd)
						except Exception as e:
							log("Exception {} when resetting board {}".format(e, b), False)

						unlockBoard(db, b, bc)
					else:
						# check time
						log("\t\tLocked by {} at {}.".format(locker, locktime), True)
						currenttime = int(time.time())
						if currenttime - int(locktime) > MAX_LOCK_TIME:
							log("Board {} lock timed out. Forced release.".format(b), False)
							unlockBoard(db, b, bc)
				else:
					log("\t\tAvailable", True)
		else:
			log("\tCurrently being locked by a user.", True)


def checkSSHToBoards(db):
	for bc in db.smembers("vlab:boardclasses"):
		for board in db.smembers("vlab:boardclass:{}:boards".format(bc)):
			dets = getBoardDetails(db, board, ['server', 'port'])
			if not checkSSHConnection(dets['server'], dets['port']):
				log("Board {} failed SSH connection. Removing.".format(board), False)
				db.srem("vlab:boardclass:{}:boards".format(bc), board)
				db.srem("vlab:boardclass:{}:unlockedboards".format(bc), board)
			else:
				log("Board {} connection OK.".format(dets['server']), True)



if parsed.check_locks:
	checkLocks(db)

if parsed.ssh_to_boards:
	log("Checking SSH connections", True)
	checkSSHToBoards(db)
