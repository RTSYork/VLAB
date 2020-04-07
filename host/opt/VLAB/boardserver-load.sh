#!/bin/bash

hostname=`hostname`

if [[ $# -gt 0 ]] ; then
	image=$1
	echo Loading Docker image $image on $hostname...
	docker load -i $image
fi

echo Killing and removing all boardserver containers on $hostname...
containers=`docker ps -q -f name=cnt`
if [[ $containers != "" ]]; then
	docker kill $containers
fi
containers=`docker ps -q -a -f name=cnt`
if [[ $containers != "" ]]; then
	docker rm $containers
fi

echo Cleaning up old Docker images on $hostname...
docker image prune -f

echo $hostname done.
