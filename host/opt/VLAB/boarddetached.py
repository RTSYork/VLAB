#!/usr/bin/env python3

"""
This script is invoked by udev when a board is removed.

Ian Gray, 2016
"""

import os, sys, subprocess, logging
import redis

logging.basicConfig(level=logging.INFO, format='%(asctime)s ; %(levelname)s ; %(name)s ; %(message)s')
log = logging.getLogger(os.path.basename(sys.argv[0]))


if len(sys.argv) < 3:
	print("Usage: {} {{serial number}} {{redis server}}".format(sys.argv[0]))
	sys.exit(1)

serial = sys.argv[1]
redisserver = sys.argv[2]

log.info("Board serial {} detached. Deregistering...".format(serial))

try:
	db = redis.StrictRedis(host=redisserver, port=6379, db=0, decode_responses=True)
	db.ping()
except redis.exceptions.ConnectionError as e:
	log.critical("Error whilst connecting to host {}\n{}".format(redisserver, e))
	sys.exit(1)


# Check with the redis server to see if the serial number of the board is known
# From the serial we learn its type (i.e. "a Digilent Zybo") and class (i.e. "this is a VLAB Zybo", vs "this is a research Zybo")
if not db.sismember("vlab:knownboards", serial):
	log.critical("Board with serial number {} is not in the VLAB database. Exiting.".format(serial))
	sys.exit(1)

btype = db.get("vlab:knownboard:{}:type".format(serial))
bclass = db.get("vlab:knownboard:{}:class".format(serial))

db.srem("vlab:boardclass:{}:boards".format(bclass), serial)
db.srem("vlab:boardclass:{}:unlockedboards".format(bclass), serial)
db.delete("vlab:board:{}:user".format(serial))
db.delete("vlab:board:{}:server".format(serial))
db.delete("vlab:board:{}:port".format(serial))
db.delete("vlab:board:{}:lock:username".format(serial))
db.delete("vlab:board:{}:lock:time".format(serial))

containername = "cnt-{}".format(serial)
try:
	s = subprocess.check_output(['docker', 'kill', containername])
except:
	pass

log.info("Board serial {} detached and deregistered.".format(serial))
