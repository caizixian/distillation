# Prerequisite
- [libpfm4](https://sourceforge.net/projects/perfmon2/files/libpfm4/)

# Build
Please adjust the definition of `JDK`, `DACAPO2006JAR`, and `DACAPOBACHJAR` in `Makefile` to point to the appropriate paths on your system.

To build, simple run `make`.
To verify that the artifact is working, please run `make test`.
The expected output should look like this.
```console
PERF_EVENTS=PERF_COUNT_HW_CPU_CYCLES LD_PRELOAD=`pwd`/libperf_statistics.so /usr/lib/jvm/temurin-17-amd64/bin/java -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:/usr/share/benchmarks/dacapo/dacapo-2006-10-MR2.jar -Xms32M -Xmx32M Harness -c Dacapo2006Callback -n 5 fop
===== DaCapo fop starting warmup =====
===== DaCapo fop completed warmup in 1016 msec =====
===== DaCapo fop starting warmup =====
===== DaCapo fop completed warmup in 778 msec =====
===== DaCapo fop starting warmup =====
===== DaCapo fop completed warmup in 756 msec =====
===== DaCapo fop starting warmup =====
===== DaCapo fop completed warmup in 750 msec =====
===== DaCapo fop starting =====
============================ Tabulate Statistics ============================
pauses  time    time.other      time.stw        PERF_COUNT_SW_TASK_CLOCK.other  PERF_COUNT_SW_TASK_CLOCK.stw    PERF_COUNT_HW_CPU_CYCLES.other  PERF_COUNT_HW_CPU_CYCLES.stw    freq.other      freq.stw
11      753     735     18      869495073       37739021        3669823502      153677531       4.22    4.07
-------------------------- End Tabulate Statistics --------------------------
===== DaCapo fop PASSED in 752 msec =====
PERF_EVENTS=PERF_COUNT_HW_CPU_CYCLES LD_PRELOAD=`pwd`/libperf_statistics.so /usr/lib/jvm/temurin-17-amd64/bin/java -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:/usr/share/benchmarks/dacapo/dacapo-9.12-bach.jar -Xms32M -Xmx32M Harness -c DacapoBachCallback -n 5 fop
===== DaCapo 9.12 fop starting warmup 1 =====
===== DaCapo 9.12 fop completed warmup 1 in 829 msec =====
===== DaCapo 9.12 fop starting warmup 2 =====
===== DaCapo 9.12 fop completed warmup 2 in 336 msec =====
===== DaCapo 9.12 fop starting warmup 3 =====
===== DaCapo 9.12 fop completed warmup 3 in 308 msec =====
===== DaCapo 9.12 fop starting warmup 4 =====
===== DaCapo 9.12 fop completed warmup 4 in 240 msec =====
===== DaCapo 9.12 fop starting =====
============================ Tabulate Statistics ============================
pauses  time    time.other      time.stw        PERF_COUNT_SW_TASK_CLOCK.other  PERF_COUNT_SW_TASK_CLOCK.stw    PERF_COUNT_HW_CPU_CYCLES.other  PERF_COUNT_HW_CPU_CYCLES.stw    freq.other      freq.stw
48      221     156     65      1027783546      262020313       4251083778      1081637661      4.14    4.13
-------------------------- End Tabulate Statistics --------------------------
===== DaCapo 9.12 fop PASSED in 221 msec =====
```

# Usage
For DaCapo 2006, use the following.
```console
PERF_EVENTS=<events> LD_PRELOAD=`pwd`/libperf_statistics.so java -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:dacapo-2006-10-MR2.jar <jvm_args> Harness -c Dacapo2006Callback -n <iterations> <benchmark>
```

For DaCapo 9.12, use the following.
```console
PERF_EVENTS=<events> LD_PRELOAD=`pwd`/libperf_statistics.so java -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:dacapo-9.12-bach.jar <jvm_args> Harness -c DacapoBachCallback -n <iterations> <benchmark>
```
