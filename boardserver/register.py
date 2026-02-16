#!/usr/bin/env python3

"""
This script is designed to run from a cron job in the board server. It simply repeatedly ensures that 
the board details are in the redis server. It does not unlock boards.

Ian Gray, 2016
"""

import sys
from vlabredis import *

if len(sys.argv) < 5:
	print("Usage: {} {{serial}} {{host hostname}} {{host port}} {{redis server}}".format(sys.argv[0]))
	sys.exit(1)

serial, hostname, host_port, redis_server = sys.argv[1:5]

db = connect_to_redis(redis_server)

check_in_set(db, "vlab:knownboards", serial,
             "Board with serial number {} is not in the VLAB database. Exiting.".format(serial))

boardtype = db.get("vlab:knownboard:{}:type".format(serial))
boardclass = db.get("vlab:knownboard:{}:class".format(serial))

db.sadd("vlab:boardclasses", boardclass)
db.sadd("vlab:boardclass:{}:boards".format(boardclass), serial)
# We do not add the board to "vlab:boardclass:{}:availableboards" or "vlab:boardclass:{}:unlockedboards" to avoid
# accidentally marking it as available/unlocked. If this is a new board registration, this will be picked up by
# 'checkboards.py' on the relay (run in a cronjob) and the board will be unlocked and set available then.

# Set up our board with details provided
db.set("vlab:board:{}:user".format(serial), "vlab")
db.set("vlab:board:{}:server".format(serial), hostname)
db.set("vlab:board:{}:port".format(serial), host_port)
