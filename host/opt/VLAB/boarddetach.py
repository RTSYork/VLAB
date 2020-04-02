#!/usr/bin/env python3

"""
This script is invoked by udev when a board is removed.

Ian Gray, 2016
"""

import json
import logging
import os
import subprocess
import sys
import redis

CONFIG_FILE = '/opt/VLAB/boardhost.conf'

logging.basicConfig(level=logging.INFO, format='%(asctime)s ; %(levelname)s ; %(name)s ; %(message)s')
log = logging.getLogger(os.path.basename(sys.argv[0]))

if len(sys.argv) < 2:
	print("Usage: {} {{serial number}}".format(sys.argv[0]))
	sys.exit(1)

serial = sys.argv[1]

log.info("Board serial {} detached. Deregistering...".format(serial))

redis_server = "localhost"
redis_port = 6379

# Open the config file and parse it
try:
	with open(CONFIG_FILE) as f:
		f_no_comments = ""
		for line in f:
			ls = line.strip()
			if len(ls) > 0 and ls[0] != '#':
				f_no_comments = f_no_comments + ls + "\n"
		config = json.loads(f_no_comments)
		if 'server' in config:
			redis_server = config['server']
		if 'port' in config:
			redis_port = config['port']
		log.info("{} parsed successfully; using server ({}:{})".format(CONFIG_FILE, redis_server, redis_port))
except ValueError as e:
	log.info("Error parsing config file `{}`; using default server ({}:{}).".format(CONFIG_FILE, redis_server, redis_port))
except FileNotFoundError as e:
	log.info("Cannot find config file `{}`; using default server ({}:{}).".format(CONFIG_FILE, redis_server, redis_port))

try:
	db = redis.StrictRedis(host=redis_server, port=redis_port, db=0, decode_responses=True)
	db.ping()
except redis.exceptions.ConnectionError as e:
	log.critical("Error whilst connecting to host {}\n{}".format(redis_server, e))
	sys.exit(1)

# Check with the redis server to see if the serial number of the board is known
# From the serial we learn its type (e.g. "a Digilent Zybo") and class (e.g. "EMBS Zybo", vs "research Zybo")
if not db.sismember("vlab:knownboards", serial):
	log.critical("Board with serial number {} is not in the VLAB database. Exiting.".format(serial))
	sys.exit(1)

boardtype = db.get("vlab:knownboard:{}:type".format(serial))
boardclass = db.get("vlab:knownboard:{}:class".format(serial))

db.srem("vlab:boardclass:{}:boards".format(boardclass), serial)
db.srem("vlab:boardclass:{}:unlockedboards".format(boardclass), serial)
db.delete("vlab:board:{}:user".format(serial))
db.delete("vlab:board:{}:server".format(serial))
db.delete("vlab:board:{}:port".format(serial))
db.delete("vlab:board:{}:lock:username".format(serial))
db.delete("vlab:board:{}:lock:time".format(serial))

container_name = "cnt-{}".format(serial)
try:
	s = subprocess.check_output(['docker', 'kill', container_name])
except subprocess.CalledProcessError:
	pass

log.info("Board serial {} detached and deregistered.".format(serial))
