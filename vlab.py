#!/usr/bin/env python3

"""
The VLAB client script.

Example usage:
	./vlab.py -k keyfile.vlabkey -b an_fpga_board

The script will assume your username is the same as the system user. To specify a different username
use the -u option.

The VLAB server and port are given as defaults to the -r and -p arguments so the user should not
have to specify them, but they can be overridden if required.

Ian Gray, 2017
"""

import argparse
import os
import sys
import urllib.request
import urllib.error
from subprocess import Popen, PIPE

############################
# Update version string here and in 'current_version' file when updating this script
# Version number must be in 'x.y.z' format
current_version = '1.1.2'
current_branch = 'master'
############################


def err(s):
	print(s)
	sys.exit(1)


parser = argparse.ArgumentParser(description="VLAB client script")
parser.add_argument('-r', '--relay', nargs=1, default=["rts001.cs.york.ac.uk"],
                    help="The hostname of the relay server.")
parser.add_argument('-p', '--port', nargs=1, default=["2222"], help="The ssh port of the relay server to connect to.")
parser.add_argument('-l', '--localport', nargs=1, default=["12345"], help="Local port to forward connections to.")
parser.add_argument('-w', '--webport', nargs=1, default=["9001"], help="Local port to forward web server connections to.")

parser.add_argument('-k', '--key', nargs=1, help="VLAB keyfile to use for authentication.")
parser.add_argument('-u', '--user', nargs=1, help="VLAB username.")

parser.add_argument('-b', '--board', nargs=1, default=["vlab_zybo-z7"], help="Requested board class.")
parser.add_argument('-s', '--serial', nargs=1, help="Requested board serial number.")

parser.add_argument('-v', '--verbose', default=False, help="Enable verbose logging.", action='store_true')
parsed = parser.parse_args()

error_info = "Read the instructions at\n" \
             "\thttps://wiki.york.ac.uk/display/RTS/Using+the+Xilinx+Tools+Remotely"


# Check for an update from GitHub repository
update_url = 'https://raw.githubusercontent.com/RTSYork/VLAB/{}/client_version'.format(current_branch)

if parsed.verbose:
	print("Checking for update at URL: {}".format(update_url))

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
		print('Download the latest version from https://raw.githubusercontent.com/RTSYork/VLAB/{}/vlab.py'.format(
			current_branch))
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
if parsed.user != None:
	ssh_cmd = ['ssh', '-oPasswordAuthentication=no', '-i', parsed.key[0], '-p', parsed.port[0], '-l', parsed.user[0], parsed.relay[0], 'getport']
else:
	ssh_cmd = ['ssh', '-oPasswordAuthentication=no', '-i', parsed.key[0], '-p', parsed.port[0], parsed.relay[0], 'getport']
if parsed.verbose:
	print("First ssh command: {}".format(ssh_cmd))
stdout, stderr = Popen(ssh_cmd, stdout=PIPE, stderr=PIPE).communicate()

try:
	error = stderr.decode('ascii').strip()
except UnicodeError:
	reply = None
	err("Could not decode error output from ssh subprocess")

if len(stdout) == 0 and len(error) > 0:
	errstr = ""
	if error.find("UNPROTECTED PRIVATE KEY FILE") != -1:
		errstr += "The permissions on the key {} are too permissive.\n".format(parsed.key[0])
		errstr += "Only your user should be able to access the key, or it will be rejected by ssh.\n"
		errstr += "To fix this, run the command\n\tchmod 0600 {}\n".format(parsed.key[0])
	elif error.find("Operation timed out") != -1 or error.find("Connection refused") != -1:
		errstr += "Cannot see the VLAB relay server: {}\n".format(parsed.relay[0])
		errstr += "Try the following:\n\tssh {}\n".format(parsed.relay[0])
		errstr += "You should get a password prompt:\n\t> <yourusername>@{}'s password\n".format(parsed.relay[0])
		errstr += "If this doesn't connect, or the prompt is for any other server, set up your .ssh/config file\n"
	elif error.find("Permission denied") != -1:
		errstr += error
		errstr += "\nEnsure that you have copied your private key:\n"
		errstr += "\tssh-copy-id csteach1.york.ac.uk\n\t(or csresearch1.york.ac.uk for staff)\n"
		errstr += "Also, if your VLAB username is different to your normal username, set it with -u:\n"
		errstr += "\t./vlab.py -k {} -u myusername\n".format(parsed.key[0])
	elif error.find("Resource temporarily unavailable") != -1:
		errstr += error
		errstr += "\nThis often means a firewall has blocked the connection. Try temporarily disabling your firewall application.\n"
	elif error.find("Connection closed by") != -1:
		errstr += error
		errstr += "\nEnsure that you have set the correct usernames in your ssh config.\n"
	elif error.find("REMOTE HOST IDENTIFICATION HAS CHANGED") != -1:
		errstr += error
		errstr += "\n\n\nThe host key in the VLAB has changed. This should not happen and might indicate a man-in-the-middle attack.\n"
		errstr += "If you are sure this is not the case, delete the line mentioned above from the file ~/.ssh/known_hosts\n"
	else:
		print(error)
	errstr += error_info
	err(errstr)

try:
	reply = stdout.decode('ascii').strip()
except UnicodeError:
	reply = None
	err("Invalid reply from VLAB server. Incorrect message format.\n{}".format(error_info))

if len(reply) > 9:
	if reply[:9] == "VLABPORT:":
		port_string = reply[9:]
		ephemeral_port = int(port_string)
	else:
		ephemeral_port = None
		err("Invalid reply from VLAB server. Wrong header.\n{}".format(error_info))
else:
	ephemeral_port = None
	err("Invalid reply from VLAB server. Message too short.\n{}".format(error_info))

print("Tunnelling to relay server '{}' using port {}...".format(parsed.relay[0], ephemeral_port))

# Now create the actual connection
ssh_user = ""
if parsed.user != None:
	ssh_user = " -l {} ".format(parsed.user[0])

# Assemble the command we send to the relay shell
if parsed.serial != None:
	relay_command = "{}:{}:{}".format(parsed.board[0], ephemeral_port, parsed.serial[0])
else:
	relay_command = "{}:{}".format(parsed.board[0], ephemeral_port)

ssh_cmd = "ssh -L {}:localhost:9001 -L {}:localhost:{} -e none -i {} {} -p {} -tt {} {}".format(
	parsed.webport[0],
	parsed.localport[0],
	ephemeral_port,
	parsed.key[0],
	ssh_user,
	parsed.port[0],
	parsed.relay[0],
	relay_command)

if parsed.verbose:
	print("Second ssh command: {}".format(ssh_cmd))

os.system(ssh_cmd)
