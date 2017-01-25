#!/bin/sh

# This script installs the necessary files to set up a VLAB board host.
# It must be executed with administrative privileges.

echo "Installing files..."

# Copy the contents of all subdirectories to /
for f in *; do
	if [ -d $f ]; then
		cp -rv $f/* /$f
	fi
done

chmod 777 /opt/VLAB/log/*.log

echo "
Install completed.

Now set the relay server hostname and port in /opt/VLAB/boardhost.conf

You can test by connecting a supported FPGA and checking that the boardserver 
container is created. Plug in the device and run:
    docker ps

Errors will be logged to:
    /opt/VLAB/log/attachdetach.log and
    /opt/VLAB/log/boardscan.log
"
