#!/bin/sh

# This script installs the necessary files to set up a VLAB board host.
# It must be executed with administrative privileges.


INSTALL_DIR=/opt/VLAB/

mkdir -p $INSTALL_DIR

#Copy the contents of all subdirectories to the filesystem
for f in *; do
	if [ -d $f ]; then
		cp -r $f/* /$f
	fi
done

echo "Install completed.
You can test by connecting a supported FPGA and checking that the boardserver 
container is created. Plug in the device and run:
    docker ps
"
