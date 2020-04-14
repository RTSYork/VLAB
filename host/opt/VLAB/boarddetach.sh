#!/bin/bash

serial=$1
dev=/dev/vlab/$serial
running=`docker inspect -f {{.State.Running}} cnt-$serial`

if [[ -e "$dev/jtag" && -L "$dev/jtag" && -a "$dev/jtag" && -e "$dev/tty" && -L "$dev/tty" && -a "$dev/tty" ]]; then
	echo "Warning: Board $serial detach event fired but its device is still present, so ignoring."
elif [[ "$running" != "true" ]]; then
	echo "Warning: Board $serial detach event fired but its Docker container is not running, so ignoring."
else
	/opt/VLAB/boarddetach.py $serial
fi
