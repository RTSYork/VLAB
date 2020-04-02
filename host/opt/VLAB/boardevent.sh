#!/bin/sh

LOGFILE=/opt/VLAB/log/attachdetach.log

if [ $# -eq 0 ]; then
	echo "No board event type supplied. Options are: 'attach', 'detach'." >> $LOGFILE
else
	if [ "$1" = "attach" ]; then
		# Add a small delay here so any detach events that are fired simultaneously are queued first
		sleep 1
		tsp -n sh -c "/opt/VLAB/boardattach.sh $2 >> $LOGFILE 2>&1"
	elif [ "$1" = "detach" ]; then
		tsp -n sh -c "/opt/VLAB/boarddetach.sh $2 >> $LOGFILE 2>&1"
	else
		echo "Invalid board event type supplied. Options are: 'attach', 'detach'." >> $LOGFILE
	fi
fi
