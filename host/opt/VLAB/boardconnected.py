#!/usr/bin/env python3

"""
This script is invoked by udev to create a docker container for each attached board.

This script might be invoked multiple times simultaneously for each new board because
some boards are actually detected as two or three devices. Therefore the script should
first check that all device nodes exist before proceeding, and should attempt to 
ensure that only one instance of a container is ever launched.

Ian Gray, 2016
"""

import os, sys, socket, subprocess, logging, json
import redis

CONFIGFILE='/opt/VLAB/boardhost.conf'

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
	sys.exit(4)


# Check with the redis server to see if the serial number of the board is known
# From the serial we learn its type (i.e. "a Digilent Zybo") and class (i.e. "this is a VLAB Zybo", vs "this is a research Zybo")
if not db.sismember("vlab:knownboards", serial):
	log.critical("Board with serial number {} is not in the VLAB database. Exiting.".format(serial))
	sys.exit(5)

btype = db.get("vlab:knownboard:{}:type".format(serial))
bclass = db.get("vlab:knownboard:{}:class".format(serial))

# At this point we can fire up different containers based on btype.
# Currently, only one container is required to support all boards, but this may change in the future.

log.info("Device serial {} is of type {} and class {}".format(serial, btype, bclass))

# udev rules have created us symlinks to the FPGA at /dev/vlab/<serial number>/[tty | dev]
tty_node = "/dev/vlab/{}/tty".format(serial) # The actual USB device of the FPGA
device_node = "/dev/vlab/{}/dev".format(serial) # The tty device of the FPGA

if not debug:
	if not os.path.islink(tty_node):
		log.critical("/dev/vlab/{} should contain a tty symlink but does not.".format(serial))
		sys.exit(6)
	if not os.path.islink(device_node):
		log.critical("/dev/vlab/{} should contain a dev symlink but does not.".format(serial))
		sys.exit(7)

# The container has an SSH port 22 which we map into the host's ephemeral port range
# We also map into the container the USB device of the FPGA and the TTY device
# We have to map the realpath of the USB device symlink because of a bug in Docker when mapping symlinks
# It doesn't matter where we map the USB device, as the Xilinx hw server searches the entire bus range
if not debug:
	mapping_arguments = ["-p", "22", "--device", "{}".format(os.path.realpath(device_node)), "--device", "{}:/dev/ttyFPGA".format(os.path.realpath(tty_node))]
else:
	mapping_arguments = ["-p", "22"]


# Remove the container in case it already exists, then run it
containername = "cnt-{}".format(serial)
try:
	s = subprocess.check_output(['docker', 'rm', '-f', containername])
except:
	pass
try:
	s = subprocess.check_output(['docker', 'run', '-d', '--name', containername] + mapping_arguments + ["vlab/boardserver"]) 
except Exception as e:
	log.critical("Running container {} failed. {}".format(containername, e))
	sys.exit(18)

# Now we need to see which host port the SSH port on the container was given
hostport = subprocess.check_output(['docker', 'port', containername, "22"])
hostport = str(hostport, 'ascii')
hostport = int(hostport.split(":")[1])


# Set up a cron inside the container to reregister itself periodically
cmd = 'echo \* \* \* \* \* python3 /vlab/register.py {} {} {} {} > /etc/cron.d/vlab-cron'.format(serial, socket.gethostname(), hostport, redisserver)
s = subprocess.check_output(['docker', 'exec', containername, '/bin/sh', '-c', cmd])

# Finally, we register our new board with the redis server ourselves as well

# Get our IP address
# We use this method because on machines with multiple interfaces this will get the one used for external routes
soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
soc.connect(("8.8.8.8", 22)) #This can be any IP address that is not on your local LAN
ip = soc.getsockname()[0]
soc.close()


# Set up our boardclass
db.sadd("vlab:boardclasses", bclass)
db.sadd("vlab:boardclass:{}:boards".format(bclass), serial)
db.sadd("vlab:boardclass:{}:unlockedboards".format(bclass), serial)

# Set up our board with details provided. Remove any locks.
db.set("vlab:board:{}:user".format(serial), "root")
db.set("vlab:board:{}:server".format(serial), ip)
db.set("vlab:board:{}:port".format(serial), hostport)
db.delete("vlab:board:{}:lock:username".format(serial))
db.delete("vlab:board:{}:lock:time".format(serial))

log.info("Board serial {} connected and registered.".format(serial))
