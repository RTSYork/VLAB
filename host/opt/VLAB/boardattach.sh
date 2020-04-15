#!/bin/bash

serial=$1
running=`docker inspect -f {{.State.Running}} cnt-$serial`

if [[ "$running" == "true" ]]; then
	echo `date --rfc-3339=s` "Warning: Board $serial attach event fired but its Docker container is already running, so ignoring."
else
	/opt/VLAB/boardattach.py $serial
fi
