#!/bin/bash

LOGFILE=/opt/VLAB/log/boardrestart.log

/opt/VLAB/boardrestart.py $1 >> $LOGFILE 2>&1
