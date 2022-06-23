# Perfetto Integration
## Prerequisite
- Android 12 (S)
- Android SDK Platform Tools
- (Optional) enable perf events collection `adb shell setprop persist.traced_perf.enable 1`

## Collect traces
```bash
./trace.sh
```
To visualize the trace, use the [web UI](https://ui.perfetto.dev).
If the UI crashes, disablle perf sample flamegraph in the [flags](https://ui.perfetto.dev/#!/flags).

## References
- JVM profiling [slides](https://www.usenix.org/sites/default/files/conference/protected-files/srecon18americas_slides_goldshtein.pdf) [video](https://www.youtube.com/watch?v=M54gbffeFhs) [video](https://www.youtube.com/watch?v=0qI31tdlV-k)
- [bpftrace reference guide](https://github.com/iovisor/bpftrace/blob/master/docs/reference_guide.md)
- [JEP 167: Event-based JVM tracing](https://openjdk.org/jeps/167)
- [Profiling with Java Flight Recorder](https://www.youtube.com/watch?v=wwgvDDuJwtk)
- [OpenJDK USDT probes](https://github.com/openjdk/jdk/blob/master/src/hotspot/os/posix/dtrace/hotspot.d)

## License
Copyright 2022 Google

Licensed under the Apache License, Version 2.0. A copy of the license is provided [here](./LICENSE).
