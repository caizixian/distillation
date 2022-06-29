#!/usr/bin/env python3
# Copyright 2022 Google
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import bcc
from bcc import BPF
import enum
import multiprocessing

class EventType(enum.Enum):
    NEWTASK = 0
    RENAME = 1
    EXEC = 2

bpf_text = """
#include <linux/sched.h>

enum event_type {
    ENTER_GC,
    EXIT_GC
};

struct data_t {
    u32 pid;
    u32 cpu;
    char comm[TASK_COMM_LEN];
    enum event_type tag;
};
BPF_PERF_OUTPUT(events);

// We use kernel terminology throughout
// Kernel process vs userspace thread
// Kernel thread group vs userspace process

BPF_HASH(process_in_gc, u32, bool, 8192);
BPF_PERF_ARRAY(cycle_events, NUM_CPUS);
BPF_ARRAY(system_cycles_start, u64, NUM_CPUS);
BPF_ARRAY(system_cycles_total, u64, NUM_CPUS);
BPF_ARRAY(gc_cycles_start, u64, NUM_CPUS);
BPF_ARRAY(gc_cycles_total, u64, NUM_CPUS);

static bool get_in_gc(u32 pid) {
    bool *val;
    val = process_in_gc.lookup(&pid);
    if (!val) {
        return false;
    }
    return *val;
}

static void set_in_gc(u32 pid, bool val) {
    if (val) {
        process_in_gc.update(&pid, &val);
    } else {
        process_in_gc.delete(&pid);
    }
}

static void add_gc_cycles(u32 cpu, u64 cnt) {
    u64* cnt_prev = gc_cycles_start.lookup(&cpu);
    if (cnt_prev) {
        u64 diff = cnt - *cnt_prev;
        gc_cycles_total.atomic_increment(cpu, diff);
    }
}

static void add_sys_cycles(u32 cpu, u64 cnt) {
    u64* cnt_prev = system_cycles_start.lookup(&cpu);
    if (cnt_prev) {
        u64 diff = cnt - *cnt_prev;
        system_cycles_total.atomic_increment(cpu, diff);
    }
}

static void process_enter_gc(u32 pid) {
    u32 cpu = bpf_get_smp_processor_id();
    set_in_gc(pid, true);
    u64 cnt = cycle_events.perf_read(cpu);
    gc_cycles_start.update(&cpu, &cnt);
}

static void process_exit_gc(u32 pid) {
    u32 cpu = bpf_get_smp_processor_id();
    set_in_gc(pid, false);
    u64 cnt = cycle_events.perf_read(cpu);
    add_gc_cycles(cpu, cnt);
}

int gc_run(struct pt_regs *ctx) {
    u32 cpu = bpf_get_smp_processor_id();
    process_enter_gc(cpu);
    return 0;
}

int gc_run_ret(struct pt_regs *ctx) {
    u32 cpu = bpf_get_smp_processor_id();
    process_exit_gc(cpu);
    return 0;
}

int sched_switch(struct pt_regs *ctx, struct task_struct *prev){
    u32 pid = bpf_get_current_pid_tgid();
    u32 cpu = bpf_get_smp_processor_id();
    u64 cnt = cycle_events.perf_read(cpu);
    u32 prev_pid = prev->pid;
    if (prev_pid == 0) {
        // idle -> running
        system_cycles_start.update(&cpu, &cnt);
        if (get_in_gc(pid)) {
            gc_cycles_start.update(&cpu, &cnt);
        }
    } else {
        add_sys_cycles(cpu, cnt);
        if (get_in_gc(prev_pid)) {
            add_gc_cycles(cpu, cnt);
        }
    }
    return 0;
}
"""

cpus = multiprocessing.cpu_count()

art_so = "/apex/com.android.art/lib64/libart.so"
gc_sym = "_ZN3art2gc9collector16GarbageCollector3RunENS0_7GcCauseEb"

b = BPF(text=bpf_text, cflags=["-DNUM_CPUS={}".format(cpus)])
cycle_events = b["cycle_events"]
cycle_events.open_perf_event(bcc.PerfType.HARDWARE, bcc.PerfHWConfig.CPU_CYCLES)
b.attach_kprobe(event_re="^finish_task_switch$|^finish_task_switch\.isra\.\d$", fn_name="sched_switch")
b.attach_uprobe(name = art_so, sym=gc_sym, fn_name="gc_run")
b.attach_uretprobe(name = art_so, sym=gc_sym, fn_name="gc_run_ret")

while True:
    try:
        b.perf_buffer_poll()
    except KeyboardInterrupt:
        break

del cycle_events

system_cycles_total_arr = b["system_cycles_total"]
for cpu in range(cpus):
    cycles = system_cycles_total_arr[cpu].value
    print("System cycles CPU {}: {:,}".format(cpu, cycles))

gc_cycles_total_arr = b["gc_cycles_total"]
for cpu in range(cpus):
    cycles = gc_cycles_total_arr[cpu].value
    print("GC cycles CPU {}: {:,}".format(cpu, cycles))
