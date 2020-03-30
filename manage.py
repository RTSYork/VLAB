#!/usr/bin/env python3

"""
Management script for the VLAB. Used to rebuild images, start containers, manage keypairs, etc.
"""

import argparse
import glob
import json
import os
import sys

containers = ['vlabcommon', 'boardserver', 'relay', 'web']


def build_arg_parsers():
	main_parser = argparse.ArgumentParser(description='VLAB management')

	subparsers = main_parser.add_subparsers(help='Operation', dest='mode')

	build_parser = subparsers.add_parser('build', help='Rebuild the VLAB containers')
	build_parser.add_argument('images', nargs='*', help='List the images to build, or none to build all images.')

	subparsers.add_parser('list', help='If the relay is running, list the currently available boards.')

	subparsers.add_parser('stats', help='If the relay is running, parse the access log and display usage stats.')

	start_parser = subparsers.add_parser('start', help='Restart the VLAB relay')
	start_parser.add_argument('-p', '--port', nargs=1, default=["2222"],
	                          help='The SSH port to bind the relay container to')

	regenkeys_parser = subparsers.add_parser('generatekeys', help='Regenerate keypairs')
	regenkeys_parser.add_argument('-i', '--internal', action="store_true", default=False,
	                              help='Regenerate the internal keypair')
	regenkeys_parser.add_argument('-u', '--user', nargs=1,
	                              help='Regenerate the keypair for a given user')
	regenkeys_parser.add_argument('-a', '--allnew', action="store_true", default=False,
	                              help='Generate keys for all users in vlab.conf which do not already have a keypair')

	return main_parser


def build_docker_image(image_name):
	def find_hardware_server_archive():
		"""
		We need to extract the name of the HW server installer which varies because of the version number
		Returns the base name of the archive, without path or file extensions
		Errors if there is not exactly one suitable archive.
		"""
		res = glob.glob('./boardserver/Xilinx_HW_Server_Lin*')
		if len(res) < 1:
			err("Download the Xilinx Hardware Server tar.gz and place it in the ./boardserver folder before building "
			    "this image.")
		if len(res) > 1:
			err("There are multiple versions of the Xilinx_HW_Server_Lin in the ./boardserver folder. Select only one.")
		name = os.path.basename(res[0])
		if not name.endswith(".tar.gz"):
			err("Ensure that you downloaded the .tar.gz version of the Xilinx hardware server.")
		basename = name[:-len(".tar.gz")]
		return basename

	if image_name == "boardserver":
		os.system(
			'docker build --build-arg HWFILE="{}" -t vlab/{} {}/'.format(find_hardware_server_archive(), image_name,
			                                                             image_name))
	else:
		os.system("docker build -t vlab/{} {}/".format(image_name, image_name))


def main():
	main_parser = build_arg_parsers()
	args = main_parser.parse_args()

	# Grab the config file
	conf_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "vlab.conf")
	if not os.path.exists(conf_file):
		err("vlab.conf should be located in the directory {}".format(os.path.dirname(os.path.realpath(__file__))))
	config = load_vlab_conf(conf_file)

	if args.mode == "build":
		print("Rebuilding VLAB docker containers...")
		if args.images:
			for im in args.images:
				if im in containers:
					build_docker_image(im)
				else:
					print("Unknown image specified: {}".format(im))
					print("Known images: {}".format(containers))
		else:
			for im in containers:
				build_docker_image(im)

	elif args.mode == "generatekeys":
		if args.internal:
			print("Generating new internal key pair...")
			remove_if_exists("keys/id_rsa")
			remove_if_exists("keys/id_rsa.pub")
			os.system('ssh-keygen -q -N "" -f keys/id_rsa')
			os.system("cp keys/id_rsa.pub boardserver/authorized_keys")
			print("Creating 'VLAB keys owner' user and setting key permissions (requires root)...")
			os.system("sudo useradd -M -d /nonexistent -s /usr/sbin/nologin -u 50000 vlab_keys_owner")
			os.system('sudo chown 50000:50000 keys/id_rsa keys/id_rsa.pub')
			os.system('sudo chmod 444 keys/id_rsa keys/id_rsa.pub')
			print("Keys generated. Now run: {} build".format(sys.argv[0]))
		elif args.allnew:
			for user, _ in config['users'].items():
				if not os.path.isfile("keys/{}".format(user)) or not os.path.isfile("keys/{}.pub".format(user)):
					print("Generating keypair for user {}".format(user))
					generate_key(user)
		else:
			if args.user is None:
				err("Specify either --internal, --allnew, or --user")
			else:
				if not args.user[0] in config['users']:
					print("Warning: User {} is not currently in vlab.conf.".format(args.user[0]))
				print("Generating key pair for user {}...".format(args.user[0]))
				generate_key(args.user[0])

	elif args.mode == "start":
		print("Restarting the VLAB relay and web...")
		os.system("docker-compose up --force-recreate")

	elif args.mode == "list":
		print("Currently available boards:")
		os.system("docker exec vlab_relay_1 python3 /vlab/checkboards.py -v")

	elif args.mode == "stats":
		os.system("docker exec vlab_relay_1 python3 /vlab/logparse.py")

	else:
		main_parser.print_usage()


def remove_if_exists(filename):
	if os.path.isfile(filename):
		os.remove(filename)


def err(s):
	print(s)
	sys.exit(1)


def load_vlab_conf(filename):
	with open(filename) as f:
		f_no_comments = ""
		for line in f:
			ls = line.strip()
			if len(ls) > 0 and ls[0] != '#':
				f_no_comments = f_no_comments + ls + "\n"
	try:
		config = json.loads(f_no_comments)
	except ValueError as e:
		print("Error in {}".format(filename))
		num = 1
		for line in f_no_comments.split("\n"):
			print("{}: {}".format(num, line))
			num = num + 1
		print("\nLine numbers refer to the file as printed above.\nERROR: {}".format(e))
		sys.exit(1)
	return config


def generate_key(user):
	remove_if_exists("keys/{}".format(user))
	remove_if_exists("keys/{}.pub".format(user))
	os.system('ssh-keygen -q -N "" -f keys/{}'.format(user))
	os.system('sudo chown 50000:50000 keys/{0} keys/{0}.pub'.format(user))
	os.system('sudo chmod 444 keys/{0} keys/{0}.pub'.format(user))


if __name__ == '__main__':
	main()
