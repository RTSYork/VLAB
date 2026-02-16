#!/bin/bash

DIR=/dev/vlab

# Check the currently identified boards in /dev/vlab and if any of them
# do not have their associated boardserver container running then create it.

if [[ -d "$DIR" ]]; then
	for f in $DIR/*
	do
		serial=$(basename $f)
		running=$(docker inspect -f {{.State.Running}} cnt-$serial)

		# Check for and remove broken symlinks
		if [[ -L "$f/tty" ]] && [[ ! -a "$f/tty" ]]; then
			rm $f/tty
		fi
		if [[ -L "$f/jtag" ]] && [[ ! -a "$f/jtag" ]]; then
			rm $f/jtag
		fi

		if [[ "$running" != "true" && -e "$f/tty" && -e "$f/jtag" ]]; then
			/opt/VLAB/boardevent.sh attach $serial
		fi
	done
fi


# Iterate through Docker containers and detach any that do not have associated devices active.

containers=$(docker ps -q -f name="cnt-")
if [[ ! -z $containers ]]; then
	while read -r container; do
		name=$(docker inspect -f {{.Name}} $container)
		serial=${name:5}
		if [[ ! -e "$DIR/$serial/tty" || ! -e "$DIR/$serial/jtag" ]]; then
			echo $(date --rfc-3339=s) Docker container for $serial is running but device is not present. Killing container...
			/opt/VLAB/boardevent.sh detach $serial
		fi
	done <<< $containers
fi
