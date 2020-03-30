import json

"""
Routines for opening and checking the vlab.conf file
"""


def open_log(log, logfile):
	with open(logfile) as f:
		f_no_comments = ""
		for line in f:
			ls = line.strip()
			if len(ls) > 0 and ls[0] != '#':
				f_no_comments = f_no_comments + ls + "\n"

	try:
		config = json.loads(f_no_comments)
	except ValueError as e:
		log.critical("Error in {}".format(logfile))
		num = 1
		for line in f_no_comments.split("\n"):
			log.critical("{}: {}".format(num, line))
			num = num + 1
		log.critical("\nLine numbers refer to the file as printed above.\nERROR: {}".format(e))
		return None

	# Verify the contents of the config
	if "users" not in config:
		log.critical("Configuration does not contain a valid 'users' section.")
		return None
	if "boards" not in config:
		log.critical("Configuration does not contain a valid 'boards' section.")
		return None

	users = config['users']

	allowed_user_properties = ["overlord", "allowedboards"]
	required_board_properties = ["class", "type"]

	for user in users:
		for k in users[user].keys():
			if k not in allowed_user_properties:
				log.critical("User {} has unknown property {}.".format(user, k))
				return None

	for board in config['boards'].keys():
		for p in required_board_properties:
			if p not in config['boards'][board]:
				log.critical("Board {} does not have property {}.".format(board, p))
				return None

	return config
