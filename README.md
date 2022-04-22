# Distilling the Real Cost of Production Garbage Collectors
The artifact to reproduce the results in the ISPASS 2022 paper *Distilling the Real Cost of Production Garbage Collectors*.

This artifact is archived on Zenodo.
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.6476821.svg)](https://doi.org/10.5281/zenodo.6476821)


## Prerequisite
- [libpfm4](https://sourceforge.net/projects/perfmon2/files/libpfm4/). On Debian-like systems, you can install it via `apt-get install libpfm4 libpfm4-dev`.
- Download the DaCapo Benchmarks from the Zenodo archive.
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.6475255.svg)](https://doi.org/10.5281/zenodo.6475255)

## Build
Please adjust the definitions of `JDK` and `DACAPOCHOPINJAR` in `Makefile` to point to the appropriate paths on your system.

To build, simple run `make`.
To verify that the artifact is working, please run `make test`.
The expected output should look like this.
```console
PERF_EVENTS=PERF_COUNT_HW_CPU_CYCLES LD_PRELOAD=`pwd`/libperf_statistics.so /usr/lib/jvm/temurin-17-jdk-amd64/bin/java -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:/usr/share/benchmarks/dacapo/dacapo-evaluation-git-29a657f.jar -Xms32M -Xmx32M Harness -c DacapoChopinCallback -n 5 fop
--------------------------------------------------------------------------------
IMPORTANT NOTICE:  This is NOT a release build of the DaCapo suite.
Since it is not an official release of the DaCapo suite, care must be taken when
using the suite, and any use of the build must be sure to note that it is not an
offical release, and should note the relevant git hash.

Feedback is greatly appreciated.   The preferred mode of feedback is via github.
Please use our github page to create an issue or a pull request.
    https://github.com/dacapobench/dacapobench.
--------------------------------------------------------------------------------

===== DaCapo evaluation-git-29a657f fop starting warmup 1 =====
===== DaCapo evaluation-git-29a657f fop completed warmup 1 in 2252 msec =====
===== DaCapo evaluation-git-29a657f fop starting warmup 2 =====
===== DaCapo evaluation-git-29a657f fop completed warmup 2 in 1190 msec =====
===== DaCapo evaluation-git-29a657f fop starting warmup 3 =====
===== DaCapo evaluation-git-29a657f fop completed warmup 3 in 1028 msec =====
===== DaCapo evaluation-git-29a657f fop starting warmup 4 =====
===== DaCapo evaluation-git-29a657f fop completed warmup 4 in 972 msec =====
===== DaCapo evaluation-git-29a657f fop starting =====
============================ Tabulate Statistics ============================
pauses  time    time.other      time.stw        PERF_COUNT_SW_TASK_CLOCK.other  PERF_COUNT_SW_TASK_CLOCK.stw    PERF_COUNT_HW_CPU_CYCLES.other  PERF_COUNT_HW_CPU_CYCLES.stw freq.other      freq.stw
67      900     796     104     1826203059      285619075       7747951292      1190821677      4.24    4.17
-------------------------- End Tabulate Statistics --------------------------
===== DaCapo evaluation-git-29a657f fop PASSED in 899 msec =====
```

## Usage
```console
PERF_EVENTS=<events> LD_PRELOAD=`pwd`/libperf_statistics.so java -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:dacapo-evaluation-git-29a657f.jar <jvm_args> Harness -c DacapoChopinCallback -n <iterations> <benchmark>
```

`<events>` is a comma-separated list of performance counters to be measured.
Please refer to the `libpfm4` documentation for more details.
For example, to measure the cycle count and the instruction count, you can use `PERF_COUNT_HW_CPU_CYCLES,PERF_COUNT_HW_INSTRUCTIONS`.

## License
Copyright 2021 Zixian Cai

Licensed under the Apache License, Version 2.0. A copy of the license is provided [here](./LICENSE).
