#!/usr/bin/env python3

'''
Management script for the VLAB. Used to rebuild images, start containers, manage keypairs, etc. 
'''

import os, argparse, sys, getpass, json, subprocess, glob

containers = ['vlabcommon', 'boardserver', 'relay', 'web']


def build_parser():
	mainparser = argparse.ArgumentParser(description='VLAB management')

	subparsers = mainparser.add_subparsers(help='Operation', dest='mode')
	
	build_parser = subparsers.add_parser('build', help='Rebuild the VLAB containers')
	build_parser.add_argument('images', nargs='*', help='List the images to build, or none to build all images.')
	
	subparsers.add_parser('list', help='If the relay is running, list the currently available boards.')

	subparsers.add_parser('stats', help='If the relay is running, parse the access log and display usage stats.')

	start_parser = subparsers.add_parser('start', help='Restart the VLAB relay')
	start_parser.add_argument('-p', '--port', nargs=1, default=["2222"], help='The SSH port to bind the relay container to')

	regenkeys_parser = subparsers.add_parser('generatekeys', help='Regenerate keypairs')
	regenkeys_parser.add_argument('-i', '--internal', action="store_true", default=False, 
		help='Regenerate the internal keypair')
	regenkeys_parser.add_argument('-u', '--user', nargs=1, 
		help='Regenerate the keypair for a given user')
	regenkeys_parser.add_argument('-a', '--allnew', action="store_true", default=False, 
		help='Generate keys for all users in vlab.conf which do not already have a keypair')

	return mainparser



def buildDockerImage(imagename):
	def findHardwareServerArchive():
		"""
		We need to extract the name of the HW server installer which varies because of the version number
		Returns the base name of the archive, without path or file extensions
		Errors if there is not exactly one suitable archive.
		"""
		res = glob.glob('./boardserver/Xilinx_HW_Server_Lin*')
		if len(res) < 1:
			err("Download the Xilinx Hardware Server tar.gz and place it in the ./boardserver folder before building this image.")
		if len(res) > 1:
			err("There are multiple versions of the Xilinx_HW_Server_Lin in the ./boardserver folder. Select only one.")
		name = os.path.basename(res[0])
		if not name.endswith(".tar.gz"):
			err("Ensure that you downloaded the .tar.gz version of the Xilinx hardware server.")
		basename = name[:-len(".tar.gz")]
		return basename

	if imagename == "boardserver":
		os.system('docker build --build-arg HWFILE="{}" -t vlab/{} {}/'.format(findHardwareServerArchive(), imagename, imagename))
	else:
		os.system("docker build -t vlab/{} {}/".format(imagename, imagename))


def main():
	mainparser = build_parser()
	args = mainparser.parse_args()

	#Grab the config file
	conffile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "vlab.conf")
	if not os.path.exists(conffile):
		err("vlab.conf should be located in the directory {}".format(os.path.dirname(os.path.realpath(__file__))))
	config = load_vlab_conf(conffile)

	if args.mode == "build":
		print("Rebuilding VLAB docker containers...")
		if args.images:
			for im in args.images:
				if im in containers:
					buildDockerImage(im)
				else:
					print("Unknown image specified: {}".format(im))
					print("Known images: {}".format(containers))
		else:
			for im in containers:
				buildDockerImage(im)

	elif args.mode == "generatekeys":
		if args.internal == True:
			print("Generating new internal key pair...")
			remove_if_exists("keys/id_rsa")
			remove_if_exists("keys/id_rsa.pub")
			os.system('ssh-keygen -q -N "" -f keys/id_rsa')
			os.system("cp keys/id_rsa.pub boardserver/authorized_keys")
			print("Keys generated. Now run: {} build".format(sys.argv[0]))
		elif args.allnew == True:
			for user, _ in config['users'].items():
				if not os.path.isfile("keys/{}".format(user)) or not os.path.isfile("keys/{}.pub".format(user)):
					print("Generating keypair for user {}".format(user))
					generate_key(user)
		else:
			if args.user == None:
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
		mainparser.print_usage()




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



if __name__ == '__main__':
	main()
