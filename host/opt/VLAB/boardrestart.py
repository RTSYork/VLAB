#!/usr/bin/env python3

"""
This script is invoked by shell.py on the relay to restart a board/container when a user is connecting.

Russell Joyce, 2017
"""

import os, sys, socket, subprocess, logging, json, time
import redis

CONFIGFILE='/opt/VLAB/boardhost.conf'

logging.basicConfig(level=logging.INFO, format='%(asctime)s ; %(levelname)s ; %(name)s ; %(message)s')
log = logging.getLogger(os.path.basename(sys.argv[0]))


if len(sys.argv) < 2:
	print("Usage: {} {{serial number}}".format(sys.argv[0]))
	sys.exit(1)

serial = sys.argv[1]

log.info("Board serial {} restarting...".format(serial))


redisserver = "localhost"
redisport = 6379

# Open the config file and parse it
try:
	with open(CONFIGFILE) as f:
		f_no_comments = ""
		for line in f:
			ls = line.strip()
			if len(ls) > 0 and ls[0] != '#':
				f_no_comments = f_no_comments + ls + "\n"
		config = json.loads(f_no_comments)
		if 'server' in config:
			redisserver = config['server']
		if 'port' in config:
			redisport = config['port']
		log.info("{} parsed successfully; using server ({}:{})".format(CONFIGFILE, redisserver, redisport))
except ValueError as e:
	log.info("Error parsing config file `{}`; using default server ({}:{}).".format(CONFIGFILE, redisserver, redisport))
except FileNotFoundError as e:
	log.info("Cannot find config file `{}`; using default server ({}:{}).".format(CONFIGFILE, redisserver, redisport))


try:
	db = redis.StrictRedis(host=redisserver, port=redisport, db=0, decode_responses=True)
	db.ping()
except redis.exceptions.ConnectionError as e:
	log.critical("Error whilst connecting to host {}\n{}".format(redisserver, e))
	sys.exit(1)


# Check with the redis server to see if the serial number of the board is known
# If the board is somehow not known, we shouldn't be restarting it, so can just let the standard attach/scan scripts deal with it.
if not db.sismember("vlab:knownboards", serial):
	log.critical("Board with serial number {} is not in the VLAB database. Exiting.".format(serial))
	sys.exit(1)


# Restart the board server container
containername = "cnt-{}".format(serial)
try:
	s = subprocess.check_output(['docker', 'restart', containername])
except Exception as e:
	log.critical("Running container {} failed. {}".format(containername, e))
	sys.exit(18)

# The host port of the SSH server could have changed, so get this again
hostport = subprocess.check_output(['docker', 'port', containername, "22"])
hostport = str(hostport, 'ascii')
hostport = int(hostport.split(":")[1])

# Update the cron inside the container with the new port
cmd = 'echo \* \* \* \* \* root /usr/bin/python3 /vlab/register.py {} {} {} {} > /etc/cron.d/vlab-cron'.format(serial, socket.gethostname(), hostport, redisserver)
s = subprocess.check_output(['docker', 'exec', containername, '/bin/sh', '-c', cmd])

# Finally, update the port of the board on the redis server
db.set("vlab:board:{}:port".format(serial), hostport)

log.info("Board serial {} restarted successfully.".format(serial))
