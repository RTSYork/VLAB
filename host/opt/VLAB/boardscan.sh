#!/bin/bash

DIR=/dev/vlab

# Check the currently identified boards in /dev/vlab and if any of them
# do not have their associated boardserver container running then create it.

if [[ -d "$DIR" ]]; then
	# Force the Digilent utilities to update and enumerate boards
	dadutil enum >> /dev/null

	for f in $DIR/*
	do
		serial=`basename $f`
		running=`docker inspect -f {{.State.Running}} cnt-$serial`

		if [ "$running" != "true" ] ; then
			/opt/VLAB/boardevent.sh attach $serial
		fi
	done
fi
