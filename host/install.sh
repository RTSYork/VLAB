#!/bin/bash

# This script installs the necessary files to set up a VLAB board host.
# It must be executed with administrative privileges.
# Usage example:
#   sudo ./install.sh /tools/Xilinx/SDK/2019.1

echo "Installing files..."

# Copy the contents of all subdirectories to /
for f in *; do
	if [ -d $f ]; then
		cp -rv $f/* /$f
	fi
done

if [ $# -eq 0 ]; then
  echo "No Xilinx SDK path supplied, skipping xsct symlink creation."
  echo "Manually create an 'xsct' symlink in /opt/VLAB to the SDK install path, or run this script again with the path supplied."
else
  ln -s $1 /opt/VLAB/xsct
fi

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
