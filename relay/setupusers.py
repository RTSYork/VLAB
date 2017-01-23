#/usr/bin/env python3

'''
Reads a list of users from CONFIGFILE and populates the redis database with them.
Also checks that each named user has an associated system user account with appropriate shell.
'''

import json, sys, os, time, subprocess, shutil, logging
import redis

CONFIGFILE='/vlab/vlab.conf'

logging.basicConfig(filename='/vlab/log/relay.log', level=logging.INFO, format='%(asctime)s ; %(levelname)s ; %(name)s ; %(message)s')
log = logging.getLogger(os.path.basename(sys.argv[0]))

log.info("Begin relay server start up.")


# Open the config file and parse it

with open(CONFIGFILE) as f:
	f_no_comments = ""
	for line in f:
		ls = line.strip()
		if len(ls) > 0 and ls[0] != '#':
			f_no_comments = f_no_comments + ls + "\n"
    
try:
	config = json.loads(f_no_comments)
except ValueError as e:
	log.critical("Error in {}".format(CONFIGFILE))
	num = 1
	for line in f_no_comments.split("\n"):
		log.critical("{}: {}".format(num, line))
		num = num + 1
	log.critical("\nLine numbers refer to the file as printed above.\nERROR: {}".format(e))
	sys.exit(1)

log.info("{} parsed successfully.".format(CONFIGFILE))


# Verify the contents of the config

if not "users" in config:
	log.critical("Configuration does not contain a valid 'users' section.")
	sys.exit(2)
if not "boards" in config:
	log.critical("Configuration does not contain a valid 'boards' section.")
	sys.exit(3)


users = config['users']

allowed_user_properties = ["overlord", "allowedboards"]
required_board_properties = ["class", "type"]


for user in users:
	for k in users[user].keys():
		if not k in allowed_user_properties:
			log.critical("User {} has unknown property {}.".format(user, k))
			sys.exit(4)


for board in config['boards'].keys():
	for p in required_board_properties:
		if not p in config['boards'][board]:
			log.critical("Board {} does not have property {}.".format(board, p))
			sys.exit(5)



# As we are started at the same time as the redis server it may time some time for it to become available
connectionattempts = 1
while True:
	try:
		db = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
		db.ping()
		break
	except redis.exceptions.ConnectionError as c:
		log.info("Connection to redis server failed. Retrying...({}/5)".format(connectionattempts))
		time.sleep(2)

	connectionattempts = connectionattempts + 1
	if connectionattempts > 5:
		log.critical("Cannot connect to the redis server. Aborting.")
		sys.exit(6)

log.info("Config file format accepted. Begin user generation.")

# We are now connected, add the user details to the dictionary and construct the users in the container
try:
	for user in users:
		db.sadd("vlab:users", user)
		if "overlord" in users[user]:
			db.set("vlab:user:{}:overlord".format(user), "true")
		if 'allowedboards' in users[user]:
			for bc in users[user]['allowedboards']:
				db.sadd("vlab:user:{}:allowedboards".format(user), bc)

		if os.path.isfile("/vlab/keys/{}.pub".format(user)):
			log.info("\tAdding user: {}".format(user))
			try:
				useradd_output = subprocess.check_output(["useradd", "-m", "--shell", "/vlab/shell.py", "{}".format(user)])
			except subprocess.CalledProcessError as e:
				log.critical("CalledProcessError calling useradd. Message: {}".format(e.output))
				sys.exit(52)
			else:
				log.info("\nuseradd complete.")
			log.info("\tAdding keys for user: {}".format(user))
			os.mkdir("/home/{}/.ssh".format(user))
			shutil.copyfile("/vlab/keys/{}.pub".format(user), "/home/{}/.ssh/authorized_keys".format(user))
			shutil.chown("/home/{}/.ssh/".format(user), user="{}".format(user), group="{}".format(user))
			shutil.chown("/home/{}/.ssh/authorized_keys".format(user), user="{}".format(user), group="{}".format(user))
			log.info("\tchmod 666 /home/{}/.ssh/authorized_keys".format(user))
			os.chmod("/home/{}/.ssh/authorized_keys".format(user), 0o600)
except Exception as e:
	log.critical("Error creating users. {}".format(e))
	sys.exit(90)

log.info("Users generated. Adding known boards to redis server.")

# Add the known boards to the dictionary
for board in config['boards'].keys():
	db.sadd("vlab:knownboards", board)
	db.set("vlab:knownboard:{}:class".format(board), config['boards'][board]['class'])
	db.set("vlab:knownboard:{}:type".format(board), config['boards'][board]['type'])


# And finally our free port number
db.set("vlab:port", 30000)

log.info("Relay server start up completed successfully.")
sys.exit(0)
