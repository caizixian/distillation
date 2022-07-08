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
import os
import signal
from threading import Event
import bcc
from bcc import BPF
import enum
import multiprocessing
import sys
from pathlib import Path

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

struct cycles_t {
    u64 cycles[NUM_CPUS];
};

BPF_HASH(process_in_gc, u32, bool, 8192);
BPF_PERF_ARRAY(cycle_events, NUM_CPUS);

BPF_ARRAY(system_cycles_start, u64, NUM_CPUS);
BPF_ARRAY(gc_cycles_start, u64, NUM_CPUS);

BPF_HASH(thread_group_cycles_total, u32, struct cycles_t, 8192);
BPF_HASH(gc_cycles_total, u32, struct cycles_t, 8192);

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

static void add_gc_cycles(u32 tgid, u32 cpu, u64 cnt) {
    u64* cnt_prev = gc_cycles_start.lookup(&cpu);
    if (cnt_prev) {
        u64 diff = cnt - *cnt_prev;
        struct cycles_t zero = {};
        struct cycles_t* prev = gc_cycles_total.lookup_or_try_init(&tgid, &zero);
        if (prev != NULL && cpu >= 0 && cpu < NUM_CPUS) {
            prev->cycles[cpu] += diff;
            gc_cycles_total.update(&tgid, prev);
        }
    }
}

static void add_thread_group_cycles(u32 tgid, u32 cpu, u64 cnt) {
    u64* cnt_prev = system_cycles_start.lookup(&cpu);
    if (cnt_prev) {
        u64 diff = cnt - *cnt_prev;
        struct cycles_t zero = {};
        struct cycles_t* prev = thread_group_cycles_total.lookup_or_try_init(&tgid, &zero);
        if (prev != NULL && cpu >= 0 && cpu < NUM_CPUS) {
            prev->cycles[cpu] += diff;
            thread_group_cycles_total.update(&tgid, prev);
        }
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
    u32 tgid = bpf_get_current_pid_tgid() >> 32;
    add_gc_cycles(tgid, cpu, cnt);
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
    u32 prev_tgid = prev->tgid;
    if (prev_pid != 0) {
        // from the previous switch until now, we weren't idling
        // we attribute the delta to the previous tgid/pid
        add_thread_group_cycles(prev_tgid, cpu, cnt);
        if (get_in_gc(prev_pid)) {
            add_gc_cycles(prev_tgid, cpu, cnt);
        }
    }
    if (pid != 0) {
        // we are not going into idle, so we need to set the initial values
        system_cycles_start.update(&cpu, &cnt);
        if (get_in_gc(pid)) {
            gc_cycles_start.update(&cpu, &cnt);
        }
    }
    return 0;
}

TRACEPOINT_PROBE(sched, sched_process_exit) {
    //    field:unsigned short common_type;       offset:0;       size:2; signed:0;
    //    field:unsigned char common_flags;       offset:2;       size:1; signed:0;
    //    field:unsigned char common_preempt_count;       offset:3;       size:1; signed:0;
    //    field:int common_pid;   offset:4;       size:4; signed:1;

    //    field:char comm[TASK_COMM_LEN]; offset:8;       size:16;        signed:1;
    //    field:pid_t pid;        offset:24;      size:4; signed:1;
    //    field:int prio; offset:28;      size:4; signed:1;
    return 0;
}

"""

def render_tgid(pid: int) -> str:
    p = Path("/proc") / str(pid) / "comm"
    if p.exists():
        return p.read_text().strip()
    else:
        return str(pid)


def main():
    cpus = multiprocessing.cpu_count()

    art_so = "/apex/com.android.art/lib64/libart.so"
    gc_sym = "_ZN3art2gc9collector16GarbageCollector3RunENS0_7GcCauseEb"

    b = BPF(text=bpf_text, cflags=["-DNUM_CPUS={}".format(cpus)])
    cycle_events = b["cycle_events"]
    cycle_events.open_perf_event(bcc.PerfType.HARDWARE, bcc.PerfHWConfig.CPU_CYCLES)
    b.attach_kprobe(event_re="^finish_task_switch$|^finish_task_switch\.isra\.\d$", fn_name="sched_switch")
    # b.attach_uprobe(name = art_so, sym=gc_sym, fn_name="gc_run")
    # b.attach_uretprobe(name = art_so, sym=gc_sym, fn_name="gc_run_ret")

    def print_stats(fd = None):
        if not fd:
            fd = sys.stdout

        nonlocal b
        nonlocal cycle_events
        del cycle_events

        thread_group_cycles_total_hash = b["thread_group_cycles_total"]
        for tgid, cycles in sorted(thread_group_cycles_total_hash.items(), key=lambda x: x[0].value):
            for cpu in range(cpus):
                cycle = cycles.cycles[cpu]
                print("thread_group_cycles,{},{},{}".format(render_tgid(tgid.value), cpu, cycle), file=fd)

        gc_cycles_total_hash = b["gc_cycles_total"]
        for tgid, cycles in sorted(gc_cycles_total_hash.items(), key=lambda x: x[0].value):
            for cpu in range(cpus):
                cycle = cycles.cycles[cpu]
                print("gc_cycles,{},{},{}".format(render_tgid(tgid.value), cpu, cycle), file=fd)


    def finish_up(*_args):
        if len(sys.argv) >= 2:
            log_path = Path(sys.argv[1])
            with log_path.open("w") as fd:
                print_stats(fd)
            symlink = log_path.resolve().parent / "latest.out"
            if symlink.is_symlink():
                symlink.unlink()
            # Make symlink point to log_path
            # Note that Path.link_to has completely opposite semantics
            symlink.symlink_to(log_path)
        else:
            print_stats()
        exit(0)
        

    signal.signal(signal.SIGTERM, finish_up)
    signal.signal(signal.SIGINT, finish_up)

    print(os.getpid())
    evt = Event()

    while True:
        # Yield to not unnecessarily burn CPU cycles in the background
        evt.wait(60)

if __name__ == "__main__":
    main()
