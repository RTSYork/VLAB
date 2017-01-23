#!/usr/bin/env python3

"""
This script is designed to run from a cron job in the board server. It simply repeatedly ensures that 
the board details are in the redis server. It does not unlock boards.

Ian Gray, 2016
"""

import os, sys
import redis
from vlabredis import *

if len(sys.argv) < 5:
	print("Usage: {} {{serial}} {{host hostname}} {{host port}} {{redis server}}".format(sys.argv[0]))
	sys.exit(1)

serial, hostname, hostport, redisserver = sys.argv[1:5]

db = connecttoredis(redisserver)

checkInSet(db, "vlab:knownboards", serial, "Board with serial number {} is not in the VLAB database. Exiting.".format(serial))

btype = db.get("vlab:knownboard:{}:type".format(serial))
bclass = db.get("vlab:knownboard:{}:class".format(serial))

db.sadd("vlab:boardclasses", bclass)
db.sadd("vlab:boardclass:{}:boards".format(bclass), serial)
# We do not add ourselves to "vlab:boardclass:{}:unlockedboards" to avoid accidentally unlocking ourselves

# Set up our board with details provided
db.set("vlab:board:{}:user".format(serial), "vlab")
db.set("vlab:board:{}:server".format(serial), hostname)
db.set("vlab:board:{}:port".format(serial), hostport)
