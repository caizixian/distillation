#!/bin/sh
# A wrapper script to invoke art_gc.py in the background with timestamp
su <<EOF
nohup /data/androdeb/run-command /art_gc.py /data/local/$(date +"%Y-%m-%d-%H%M%S").out > /dev/null 2>&1 &
EOF
