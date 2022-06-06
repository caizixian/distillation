# Perfetto Integration
## Prerequisite
- Android 12 (S)
- Android SDK Platform Tools
- (Optional) enable perf events collection `adb shell setprop persist.traced_perf.enable 1`

## Collect traces
```
./trace.sh
```
To visualize the trace, use https://ui.perfetto.dev/