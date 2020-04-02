#!/bin/sh

serial=$1
running=`docker inspect -f {{.State.Running}} cnt-$serial`

if [ "$running" != "true" ] ; then
	/opt/VLAB/boardattach.py $serial
else
	echo "Warning: Board $serial attach event fired but its Docker container is already running."
fi
