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
import argparse
import enum
import multiprocessing

class EventType(enum.Enum):
    NEWTASK = 0
    RENAME = 1
    EXEC = 2

bpf_text = """
#include <linux/sched.h>

#define DECLARE_EQUAL_TO(s) static inline bool equal_to_##s(char *str) { \
    char comparand[sizeof(#s)]; \
    bpf_probe_read(&comparand, sizeof(comparand), str); \
    char compare[] = #s; \
    for (int i = 0; i < sizeof(comparand); ++i) \
        if (compare[i] != comparand[i]) \
            return false; \
    return true; \
} \

#define IS_EQUAL_TO(str, s) equal_to_##s(str)

DECLARE_EQUAL_TO(java)

enum event_type {
    NEWTASK,
    RENAME,
    EXEC
};

struct data_t {
    u32 tid;
    char comm[TASK_COMM_LEN];
    char old_comm[TASK_COMM_LEN];
    enum event_type tag;
};
BPF_PERF_OUTPUT(events);

BPF_ARRAY(java_pid, u32, 1);
BPF_PERF_ARRAY(cycle_events, NUM_CPUS);
BPF_ARRAY(cycles_start, u64, NUM_CPUS);
BPF_ARRAY(cycles_total, u64, NUM_CPUS);
BPF_ARRAY(track_cpu, bool, NUM_CPUS);

static bool match_pid(u32 pid) {
    int key = 0;
    int *val;
    val = java_pid.lookup(&key);
    if (!val) {
        return false;
    }
    return *val != 0 && *val == pid;
}

static bool get_track_cpu(int cpu) {
    bool* val = track_cpu.lookup(&cpu);
    if (!val) {
        return false;
    }
    return *val;
}

static void set_track_cpu(int cpu, bool val) {
    track_cpu.update(&cpu, &val);
}

TRACEPOINT_PROBE(task, task_newtask) {
    struct data_t data = {};
    bool value = true;
    u64 parent_pid_tgid = bpf_get_current_pid_tgid();
    // the userspace pid of the process creating the task
    u32 parent_tgid = parent_pid_tgid >> 32;
    if (!match_pid(parent_tgid)) {
        return 0;
    }
    // userspace tid of the new task
    data.tid = args->pid;
    bpf_probe_read_kernel(&data.comm, sizeof(data.comm), args->comm);
    data.tag = NEWTASK;
    // https://github.com/iovisor/bcc/issues/1251
    // use args in place of ctx
    events.perf_submit(args, &data, sizeof(data));
    return 0;
}

TRACEPOINT_PROBE(task, task_rename) {
    struct data_t data = {};
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 tgid = pid_tgid >> 32;
    // do want to want to track this rename?
    if (!match_pid(tgid)) {
        return 0;
    }
    data.tid = args->pid;
    bpf_probe_read_kernel(&data.comm, sizeof(data.comm), args->newcomm);
    bpf_probe_read_kernel(&data.old_comm, sizeof(data.old_comm), args->oldcomm);
    data.tag = RENAME;
    // use args in place of ctx
    events.perf_submit(args, &data, sizeof(data));
    return 0;
}

TRACEPOINT_PROBE(sched, sched_process_exec) {
    struct data_t data = {};
    int key = 0;
    bool value = true;
    // current comm is the comm of the new process
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    if (IS_EQUAL_TO(data.comm, java)) {
        data.tid = args->pid; // the userspace pid of the new process
        java_pid.update(&key, &data.tid);
    } else {
        return 0;
    }
    data.tag = EXEC;
    events.perf_submit(args, &data, sizeof(data));
    return 0;
}

int sched_switch(struct pt_regs *ctx, struct task_struct *prev){
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u64 tgid = pid_tgid >> 32;
    u32 cpu = bpf_get_smp_processor_id();
    u64 val = cycle_events.perf_read(cpu);
    u64 *prev_cycle;
    u64 diff;
    if (match_pid(tgid)) {
        // We should but haven't tracked this CPU
        if (!get_track_cpu(cpu)) {
            cycles_start.update(&cpu, &val);
            set_track_cpu(cpu, true);
        }
    } else if (get_track_cpu(cpu)) {
        prev_cycle = cycles_start.lookup(&cpu);
        if (prev_cycle) {
            diff = val - *prev_cycle;
            cycles_total.atomic_increment(cpu, diff);
        }
        set_track_cpu(cpu, false);
    }
    return 0;
}
"""

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--pid")
args = parser.parse_args()

if args.pid:
    bpf_text = bpf_text.replace("PID_FILTER", "if (tgid != {}) { return 0; }".format(args.pid))
else:
    bpf_text = bpf_text.replace("PID_FILTER", "")

def print_event(cpu, data, size):
    event = b["events"].event(data)
    print(EventType(event.tag), event.tid, event.comm)

cpus = multiprocessing.cpu_count()

b = BPF(text=bpf_text, cflags=["-DNUM_CPUS={}".format(cpus)])
b["events"].open_perf_buffer(print_event)
cycle_events = b["cycle_events"]
cycle_events.open_perf_event(bcc.PerfType.HARDWARE, bcc.PerfHWConfig.CPU_CYCLES)
b.attach_kprobe(event_re="^finish_task_switch$|^finish_task_switch\.isra\.\d$", fn_name="sched_switch")

while True:
    try:
        b.perf_buffer_poll()
    except KeyboardInterrupt:
        break

cycles_total_arr = b["cycles_total"]
total_cycles = 0
for cpu in range(cpus):
    cycles = cycles_total_arr[cpu].value
    print("CPU {}: {:,}".format(cpu, cycles))
    total_cycles += cycles
print("Total cycles: {:,}".format(total_cycles))
del cycle_events
