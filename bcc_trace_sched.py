#!/usr/bin/env python3
import bcc
import multiprocessing
import time

def main():
    text = """
#include <linux/sched.h>
BPF_PERF_ARRAY(cycle_events, NUM_CPUS);
BPF_ARRAY(cycles, u64, NUM_CPUS);

int sched_switch(struct pt_regs *ctx, struct task_struct *prev){
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 tgid = pid_tgid >> 32, pid = pid_tgid;
    u32 cpu = bpf_get_smp_processor_id();
    u64 val = cycle_events.perf_read(cpu);
    u32 prev_pid = prev->pid;
    u32 prev_tgid = prev->tgid;

    bpf_trace_printk("ZC perf cpu %d current pid %d, tgid %d", cpu, pid, tgid);
    bpf_trace_printk("ZC perf prev pid %d, tgid %d", prev_pid, prev_pid);
    bpf_trace_printk("ZC perf cycle %llu", val);

    return 0;
}
"""
    b = bcc.BPF(text=text, debug=0,
            cflags=["-DNUM_CPUS=%d" % multiprocessing.cpu_count()])
    b.attach_kprobe(event_re="^finish_task_switch$|^finish_task_switch\.isra\.\d$", fn_name="sched_switch")
    cycle_events = b["cycle_events"]
    try:
        cycle_events.open_perf_event(bcc.PerfType.HARDWARE, bcc.PerfHWConfig.CPU_CYCLES)
        time.sleep(100000)
    except:
        print("hardware events unsupported")

if __name__ == "__main__":
    main()
