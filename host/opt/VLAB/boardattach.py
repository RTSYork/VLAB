#!/usr/bin/env python3

"""
This script is invoked by udev to create a docker container for each attached board.

This script might be invoked multiple times simultaneously for each new board because
some boards are actually detected as two or three devices. Therefore the script should
first check that all device nodes exist before proceeding, and should attempt to 
ensure that only one instance of a container is ever launched.

Ian Gray, 2016
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
	sys.exit(10)

if len(sys.argv) > 2 and sys.argv[2] == "debug":
	debug = True
else:
	debug = False

serial = sys.argv[1]

log.info("VLAB device {} connected.".format(serial))

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
	sys.exit(4)

# Check with the redis server to see if the serial number of the board is known
# From the serial we learn its type (e.g. "a Digilent Zybo") and class (e.g. "EMBS Zybo", vs "research Zybo")
if not db.sismember("vlab:knownboards", serial):
	log.critical("Board with serial number {} is not in the VLAB database. Exiting.".format(serial))
	sys.exit(5)

boardtype = db.get("vlab:knownboard:{}:type".format(serial))
boardclass = db.get("vlab:knownboard:{}:class".format(serial))

# At this point we can fire up different containers based on boardtype.
# Currently, only one container is required to support all boards, but this may change in the future.

log.info("Device serial {} is of type {} and class {}".format(serial, boardtype, boardclass))

# udev rules have created us symlinks to the FPGA at /dev/vlab/<serial number>/[tty | jtag]
tty_node = "/dev/vlab/{}/tty".format(serial)  # The UART tty device of the FPGA
jtag_node = "/dev/vlab/{}/jtag".format(serial)  # The USB JTAG device of the FPGA

if not debug:
	if not os.path.islink(tty_node):
		log.critical("/dev/vlab/{} should contain a 'tty' symlink but does not.".format(serial))
		sys.exit(6)
	if not os.path.islink(jtag_node):
		log.critical("/dev/vlab/{} should contain a 'jtag' symlink but does not.".format(serial))
		sys.exit(7)

# The container has an SSH port 22 which we map into the host's ephemeral port range
# We also map into the container the USB device of the FPGA and the TTY device
# We have to map the realpath of the USB device symlink because of a bug in Docker when mapping symlinks
# It doesn't matter where we map the USB device, as the Xilinx hw server searches the entire bus range
# Also, if the Xilinx command line tools are located at /opt/VLAB/xsct they are mapped into the container
if not debug:
	mapping_arguments = ["-p", "22",
	                     "--device", "{}".format(os.path.realpath(jtag_node)),
	                     "--device", "{}:/dev/ttyFPGA".format(os.path.realpath(tty_node)),
	                     "-v", "/opt/VLAB/xsct/:/opt/xsct"]
else:
	mapping_arguments = ["-p", "22"]

# Remove the container in case it already exists, then run it
container_name = "cnt-{}".format(serial)
try:
	subprocess.check_output(['docker', 'rm', '-f', container_name])
except subprocess.CalledProcessError:
	pass
try:
	subprocess.check_output(['docker', 'run', '-d', '--name', container_name] + mapping_arguments + ["vlab/boardserver"])
except Exception as e:
	log.critical("Running container {} failed. {}".format(container_name, e))
	sys.exit(18)

# Now we need to see which host port the SSH port on the container was given
host_port = subprocess.check_output(['docker', 'port', container_name, "22"])
host_port = str(host_port, 'ascii')
host_port = int(host_port.split(":")[1])

# Set up a cron inside the container to re-register itself periodically
cmd = 'echo \\* \\* \\* \\* \\* root /usr/bin/python3 /vlab/register.py {} {} {} {} > /etc/cron.d/vlab-cron'\
	.format(serial, socket.gethostname(), host_port, redis_server)
subprocess.check_output(['docker', 'exec', container_name, '/bin/sh', '-c', cmd])

# If the board is marked as reset on connection, reset it now just to be sure that its configuration is clean
if db.get("vlab:knownboard:{}:reset".format(serial)) == "true":
	cmd = "/opt/xsct/bin/xsdb /vlab/reset.tcl"
	log.info("Resetting FPGA configuration on board {}...".format(serial))
	subprocess.check_output(['docker', 'exec', container_name, '/bin/sh', '-c', cmd])

# Finally, we register our new board with the redis server ourselves as well

# Set up our boardclass
db.sadd("vlab:boardclasses", boardclass)
db.sadd("vlab:boardclass:{}:boards".format(boardclass), serial)
db.zadd("vlab:boardclass:{}:unlockedboards".format(boardclass), 0, serial)

# Set up our board with details provided. Remove any locks.
db.set("vlab:board:{}:user".format(serial), "root")
db.set("vlab:board:{}:server".format(serial), socket.gethostname())
db.set("vlab:board:{}:port".format(serial), host_port)
db.delete("vlab:board:{}:lock:username".format(serial))
db.delete("vlab:board:{}:lock:time".format(serial))

log.info("Board serial {} connected and registered.".format(serial))
