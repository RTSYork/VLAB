#!/usr/bin/env python3

"""
Reads a list of users from CONFIGFILE and populates the redis database with them.
Also checks that each named user has an associated system user account with appropriate shell.
This script is idempotent and can be re-run on a live system to apply config changes.
"""

import logging
import os
import shutil
import subprocess
import sys
import time
import redis
import vlabconfig

CONFIG_FILE = '/vlab/vlab.conf'

logging.basicConfig(
	filename='/vlab/log/relay.log',	level=logging.INFO,	format='%(asctime)s ; %(levelname)s ; %(name)s ; %(message)s')
log = logging.getLogger(os.path.basename(sys.argv[0]))

log.info("Begin relay server start up.")

# Open the config file and parse it
config = vlabconfig.open_log(log, CONFIG_FILE)
log.info("{} parsed successfully.".format(CONFIG_FILE))
users = config['users']

# As we are started at the same time as the redis server it may time some time for it to become available
connection_attempts = 1
while True:
	try:
		db = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
		db.ping()
		break
	except redis.exceptions.ConnectionError as c:
		log.info("Connection to redis server failed. Retrying...({}/5)".format(connection_attempts))
		time.sleep(2)
	connection_attempts = connection_attempts + 1
	if connection_attempts > 5:
		log.critical("Cannot connect to the redis server. Aborting.")
		sys.exit(6)

log.info("Config file format accepted. Begin user generation.")

# We are now connected, sync the user details with Redis and construct any new users in the container
try:
	# Remove users that are no longer in config
	existing_redis_users = db.smembers("vlab:users")
	for removed_user in existing_redis_users - set(users.keys()):
		log.info("User {} removed from config. Cleaning up Redis keys.".format(removed_user))
		db.srem("vlab:users", removed_user)
		db.delete("vlab:user:{}:overlord".format(removed_user))
		db.delete("vlab:user:{}:allowedboards".format(removed_user))
		# System account is intentionally left in place (may have an active session)

	# Add/update all users in config
	for user in users:
		db.sadd("vlab:users", user)

		# Delete first to handle revocations, then re-set if present
		db.delete("vlab:user:{}:overlord".format(user))
		if "overlord" in users[user]:
			db.set("vlab:user:{}:overlord".format(user), "true")

		# Delete first to handle removed boards, then re-add current set
		db.delete("vlab:user:{}:allowedboards".format(user))
		if 'allowedboards' in users[user]:
			for bc in users[user]['allowedboards']:
				db.sadd("vlab:user:{}:allowedboards".format(user), bc)

		if os.path.isfile("/vlab/keys/{}.pub".format(user)):
			log.info("\tProcessing user: {}".format(user))
			# Check if system user already exists
			result = subprocess.call(["/usr/bin/id", user], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			if result != 0:
				try:
					useradd_output = subprocess.check_output(
						["/usr/sbin/useradd", "-m", "--shell", "/vlab/shell.py", "{}".format(user)])
				except subprocess.CalledProcessError as e:
					log.critical("CalledProcessError calling useradd. Message: {}".format(e.output))
					sys.exit(52)
				else:
					log.info("\tuseradd complete.")
			else:
				log.info("\tSystem user {} already exists, skipping useradd.".format(user))

			# Only copy SSH keys if not already in place
			auth_keys_path = "/home/{}/.ssh/authorized_keys".format(user)
			if not os.path.isfile(auth_keys_path):
				log.info("\tAdding keys for user: {}".format(user))
				os.makedirs("/home/{}/.ssh".format(user), exist_ok=True)
				shutil.copyfile("/vlab/keys/{}.pub".format(user), auth_keys_path)
				shutil.chown("/home/{}/.ssh/".format(user), user="{}".format(user), group="{}".format(user))
				shutil.chown("/home/{}/.ssh/authorized_keys".format(user), user="{}".format(user), group="{}".format(user))
				log.info("\tchmod 600 /home/{}/.ssh/authorized_keys".format(user))
				os.chmod("/home/{}/.ssh/authorized_keys".format(user), 0o600)
			else:
				log.info("\tSSH keys already in place for user: {}".format(user))
except Exception as e:
	log.critical("Error creating users. {}".format(e))
	sys.exit(90)

log.info("Users generated. Adding known boards to redis server.")

# Sync known boards with config (handle additions and removals)
existing_known_boards = db.smembers("vlab:knownboards")
for rb in existing_known_boards - set(config['boards'].keys()):
	log.info("Board {} removed from config. Removing from vlab:knownboards.".format(rb))
	db.srem("vlab:knownboards", rb)
	db.delete("vlab:knownboard:{}:class".format(rb))
	db.delete("vlab:knownboard:{}:type".format(rb))
	db.delete("vlab:knownboard:{}:reset".format(rb))

for board in config['boards'].keys():
	db.sadd("vlab:knownboards", board)
	db.set("vlab:knownboard:{}:class".format(board), config['boards'][board]['class'])
	db.set("vlab:knownboard:{}:type".format(board), config['boards'][board]['type'])
	if 'reset' in config['boards'][board]:
		db.set("vlab:knownboard:{}:reset".format(board), config['boards'][board]['reset'])

# Set the initial port counter only if it does not already exist (setnx is safe to call on reload)
db.setnx("vlab:port", 30000)

log.info("Relay server start up completed successfully.")
sys.exit(0)
