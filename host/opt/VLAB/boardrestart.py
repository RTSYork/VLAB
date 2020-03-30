#!/usr/bin/env python3

"""
This script is invoked by shell.py on the relay to restart a board/container when a user is connecting.

Russell Joyce, 2017
"""

import json
import logging
import os
import socket
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

log.info("Board serial {} restarting...".format(serial))

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

# Check with the redis server to see if the serial number of the board is known.
# If the board is somehow not known, we shouldn't be restarting it - the standard attach/scan scripts can deal with it.
if not db.sismember("vlab:knownboards", serial):
	log.critical("Board with serial number {} is not in the VLAB database. Exiting.".format(serial))
	sys.exit(1)

# Restart the board server container
container_name = "cnt-{}".format(serial)
try:
	s = subprocess.check_output(['docker', 'restart', container_name])
except Exception as e:
	log.critical("Running container {} failed. {}".format(container_name, e))
	sys.exit(18)

# The host port of the SSH server could have changed, so get this again
host_port = subprocess.check_output(['docker', 'port', container_name, "22"])
host_port = str(host_port, 'ascii')
host_port = int(host_port.split(":")[1])

# Update the cron inside the container with the new port
cmd = 'echo \\* \\* \\* \\* \\* root /usr/bin/python3 /vlab/register.py {} {} {} {} > /etc/cron.d/vlab-cron'\
	.format(serial, socket.gethostname(), host_port, redis_server)

subprocess.check_output(['docker', 'exec', container_name, '/bin/sh', '-c', cmd])

# Finally, update the port of the board on the redis server
db.set("vlab:board:{}:port".format(serial), host_port)

log.info("Board serial {} restarted successfully.".format(serial))
