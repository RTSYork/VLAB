#!/bin/bash

##
## VLAB Board Server Docker Image Update Script
##
## Run `manage.py build` first to update the 'boardserver' image, then use this script to copy and load it onto hosts.
## Run with a list of board hosts as arguments (use localhost to update the local machine), e.g.:
##  ./boardserver-update.sh localhost server1 server2
##

echo Saving boardserver Docker image...
docker save -o boardserver.tar vlab/boardserver

for host in "$@"
do
	if [[ $host == "localhost" ]]; then
		echo Reloading boardserver image on local machine...
		/opt/VLAB/boardserver_load.sh
	else
		echo Copying boardserver image to $host...
		scp boardserver.tar $host:
		echo Loading boardserver image on $host...
		ssh $host /opt/VLAB/boardserver-load.sh boardserver.tar
	fi
done

echo Done.
