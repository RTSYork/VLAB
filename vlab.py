#!/usr/bin/env python3

'''
The VLAB client script.

Example usage:
	./client.py -k vlabkeyfile -b an_fpga_board

The script will assume your username is the same as the system user. To specify a different username
use the -u option.

The VLAB server and port are given as defaults to the -r and -p arguments so the user should not 
have to specify them, but they can be overridden if required.

Ian Gray, 2017
'''

############################
# Update version string here and in 'current_version' file when updating this script
# Version number must be in 'x.y.z' format
current_version = '1.0.0'
current_branch = 'master'
############################

import os, argparse, sys, getpass
from subprocess import Popen, PIPE
import urllib.request

def err(s):
	print(s)
	sys.exit(1)

parser = argparse.ArgumentParser(description="VLAB client script")
parser.add_argument('-r', '--relay', nargs=1, default=["rts001.cs.york.ac.uk"], help="The hostname of the relay server.")
parser.add_argument('-p', '--port', nargs=1, default=["2222"], help="The ssh port of the relay server to connect to.")
parser.add_argument('-l', '--localport', nargs=1, default=["12345"], help="Local port to forward connections to.")

parser.add_argument('-k', '--key', nargs=1, help="VLAB keyfile to use for authentication.")
parser.add_argument('-u', '--user', nargs=1, default=[getpass.getuser()], help="VLAB username.")

parser.add_argument('-b', '--board', nargs=1, default=["vlab_zybo-z7"], help="Requested board class.")
parsed = parser.parse_args()


# Check for an update from GitHub repository
update_url = 'https://raw.githubusercontent.com/RTSYork/VLAB/{}/client_version'.format(current_branch)
req = urllib.request.Request(update_url)
try:
	response = urllib.request.urlopen(req)
	content = response.readline()
	remote_version_string = content.decode('utf-8')
	remote_version = tuple(map(int, (remote_version_string.split("."))))
	local_version = tuple(map(int, (current_version.split("."))))
	if local_version < remote_version:
		print('A new version of the VLAB script is available on GitHub')
		print('You have version v{} and the latest is v{}'.format(current_version, remote_version_string))
		print('Download the latest version from https://raw.githubusercontent.com/RTSYork/VLAB/{}/vlab.py'.format(current_branch))
		print()
		try:
			input("Press Control-C to exit, or press Enter to continue...")
		except KeyboardInterrupt:
			sys.exit(0)
except urllib.error.URLError as e:
	print('Error checking for script updates:', e.reason)


# Check the keyfile exists
if not parsed.key:
	err("Specify a keyfile with --key.")
if not os.path.isfile(parsed.key[0]):
	err("Keyfile {} does not exist. Specify a keyfile with --key.".format(parsed.key[0]))


# First get a port to use on the relay server
sshcmd = ['ssh', '-i', parsed.key[0], '-p', parsed.port[0], '{}@{}'.format(parsed.user[0], parsed.relay[0]), 'getport']
stdout, stderr = Popen(sshcmd, stdout=PIPE).communicate()
try:
	reply = stdout.decode('ascii').strip()
	if len(reply) > 9:
		if reply[:9] == "VLABPORT:":
			portstr = reply[9:]
			ephemeralport = int(portstr)
		else:
			err("Invalid reply from VLAB server. Wrong header.")
	else:
		err("Invalid reply from VLAB server. Message too short.")
except:
	err("Invalid reply from VLAB server. Incorrect message format.")

print("Using tunnel port {}".format(ephemeralport))


# Now create the actual connection
sshcmd = "ssh -L {}:localhost:{} -o \"StrictHostKeyChecking no\" -e none -i {} -p {} -tt {}@{} {}:{}".format(
	parsed.localport[0], 
	ephemeralport, 
	parsed.key[0], 
	parsed.port[0],
	parsed.user[0], 
	parsed.relay[0], 
	parsed.board[0], 
	ephemeralport)
os.system(sshcmd)
