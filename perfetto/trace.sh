#!/bin/sh
adb shell perfetto \
  -c - --txt \
  -o /data/misc/perfetto-traces/example.perfetto-trace \
< example.cfg

adb pull /data/misc/perfetto-traces/example.perfetto-trace 
