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
